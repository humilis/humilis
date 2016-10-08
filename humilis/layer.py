"""Humilis Layer."""

import itertools
import os
import os.path
import re
import logging
from humilis.config import config
from humilis.utils import DirTreeBackedObject, get_cf_name
from humilis.exceptions import (ReferenceError, CloudformationError,
                                MissingPluginError)
from boto3facade.s3 import S3
from boto3facade.ec2 import Ec2
from boto3facade.exceptions import NoUpdatesError
from botocore.exceptions import ClientError
import json
import time
import datetime


class Layer:
    """A layer of infrastructure that translates into a single CF stack"""
    def __init__(self, environment, name, layer_type=None, logger=None,
                 loader=None, **user_params):
        self.__environment_repr = repr(environment)
        self.cf = environment.cf
        if logger is None:
            self.logger = logging.getLogger(__name__)
            # To prevent warnings
            self.logger.addHandler(logging.NullHandler())
        else:
            self.logger = logger
        self.name = name
        self.env_name = environment.name
        self.env_stage = environment.stage
        self.env_basedir = environment.basedir
        self.depends_on = []
        self.section = {}
        self.type = layer_type

        if layer_type is not None:
            basedir = config.layers.get(layer_type)
            if not basedir:
                msg = ("The plugin providing the layer type '{}' is not "
                       "installed in this system. Please install it and "
                       "try again.").format(layer_type)
                raise MissingPluginError(msg)
        else:
            basedir = None

        if basedir is None:
            basedir = os.path.join(self.env_basedir, 'layers', self.name)

        self.basedir = basedir

        if loader is None:
            loader = DirTreeBackedObject(basedir, self.logger)

        self.loader = loader
        self.children = []

        # These param set will be sent to the template compiler and will be
        # populated once the layers this layer depend on have been created.
        self.params = {}

        # the parameters that will be used to compile meta.yaml
        self.meta = {}
        meta_params = {p[0]: p[1] for p
                       in itertools.chain(self.loader_params.items(),
                                          user_params.items())}
        self.meta = self.loader.load_section('meta', params=meta_params)
        for dep in self.meta.get('dependencies', []):
            dep_cf_name = get_cf_name(self.env_name, dep, stage=self.env_stage)
            self.depends_on.append(dep_cf_name)

        self.sns_topic_arn = environment.sns_topic_arn
        self.tags = {
            'humilis:environment': self.env_name,
            'humilis:layer': self.name,
            'humilis:stage': self.env_stage,
            'humilis:created': str(datetime.datetime.now())}
        for tagname, tagvalue in environment.tags.items():
            self.tags[tagname] = tagvalue

        for tagname, tagvalue in self.meta.get('tags', {}).items():
            self.tags[tagname] = tagvalue

        self.yaml_params = self.meta.get('parameters', {})
        for k, v in self.yaml_params.items():
            # Set 1 as default priority for all parameters
            v['priority'] = v.get('priority', 1)

        # User params override what is in the layer definition file
        self.user_params = user_params
        for pname, pvalue in user_params.items():
            if pname in self.yaml_params:
                self.yaml_params[pname]['value'] = pvalue
        self.__ec2 = None
        self.__s3 = None

    @property
    def cf_name(self):
        """The name of the CF stack associated to this layer."""
        return get_cf_name(self.env_name, self.name, stage=self.env_stage)

    @property
    def loader_params(self):
        """Produces a dictionary of parameters to pass to a section loader."""
        # User parameters in the layer meta.yaml
        # Not that some param values may not have been populated when this
        # property is accessed since that may happen during the parsing of
        # some references in the parameter list: thus the if 'value' in v
        params = {k: v['value'] for k, v in self.params.items()
                  if 'value' in v}
        params['_env'] = {'stage': self.env_stage, 'name': self.env_name}
        params['_os_env'] = os.environ
        params['_layer'] = {
            'name': self.name,
            'description': self.meta.get('description', '')}
        return params

    @property
    def in_cf(self):
        """Returns true if the layer has been already deployed to CF."""
        return self.cf_name in {stk['StackName'] for stk in self.cf.stacks}

    @property
    def ec2(self):
        """Connection to AWS EC2 service."""
        if self.__ec2 is None:
            self.__ec2 = Ec2(config.boto_config)
        return self.__ec2

    @property
    def s3(self):
        """Connection to AWS S3."""
        if self.__s3 is None:
            self.__s3 = S3(config.boto_config)
        return self.__s3

    @property
    def children_in_cf(self):
        """List of (already created) children layers."""
        return [x for x in self.children if x.in_cf]

    @property
    def ok(self):
        """Layer is fully deployed in CF and ready for use"""
        return self.cf.stack_ok(self.cf_name)

    @property
    def outputs(self):
        """Layer outputs. Throws an exception if layer is not ok."""
        if not self.ok:
            msg = ("Attempting to read outputs from a layer that has not "
                   "been fully deployed yet")
            raise CloudformationError(msg, logger=self.logger)
        ly = self.cf.stack_outputs[self.cf_name]
        if ly is not None:
            ly = {o['OutputKey']: o['OutputValue'] for o in ly}
        return ly

    @property
    def dependencies_met(self):
        """Checks whether all stack dependencies have been deployed."""
        current_cf_stack_names = {stack.get('StackName') for stack
                                  in self.cf.stacks}
        for dep in self.depends_on:
            if dep not in current_cf_stack_names:
                return False
        return True

    def add_child(self, child):
        """Adds a child layer to this layer."""
        self.children.append(child)
        # Don't use a comma as a separator. For whatever reason CF seems to
        # occasionally break when tag values contain commas.
        self.tags['humilis:children'] = ':'.join((x.name for x
                                                  in self.children))

    def compile(self):
        """Loads all files associated to a layer."""
        # Some templates may refer to params, so populate them first
        self.populate_params()

        # Load all files with layer contents
        for section in config.LAYER_SECTIONS:
            self.section[section] = self.loader.load_section(
                section, params=self.loader_params)

        # Package the layer as a CF template
        cf_template = {
            'AWSTemplateFormatVersion': str(config.CF_TEMPLATE_VERSION),
            'Description': self.meta.get('description', ''),
            'Mappings': self.section.get('mappings', {}),
            'Parameters': self.section.get('parameters', {}),
            'Resources': self.section.get('resources', {}),
            'Outputs': self.section.get('outputs', {})
        }
        return cf_template

    def populate_params(self):
        """Populates parameters in a layer by resolving references."""
        if len(self.yaml_params) < 1:
            return
        for pname, param in sorted(self.yaml_params.items(),
                                   key=lambda t: t[1].get('priority', '1')):
            self.params[pname] = {}
            self.params[pname]['description'] = param.get('description', None)
            try:
                self.params[pname]['value'] = self._parse_param_value(
                    param['value'])
            except:
                self.logger.error("Error parsing layer '{}'".format(self.name))
                raise

    def print_params(self):
        """Prints the params used during layer creation."""
        if len(self.params) < 1:
            print("No parameters. Did you forget to run populate_params()?")
            return
        print("Parameters for layer {}:".format(self.cf_name))
        for pname, param in self.params.items():
            pval = param.get('value', None)
            if len(pval) > 30:
                pval = pval[0:30]
            print("{pname:<15}: {pval:>30}".format(pname=pname, pval=pval))

    def _parse_param_value(self, pval):
        """Parses layer parameter values."""
        if isinstance(pval, list):
            # A list of values: parse each one individually
            return [self._parse_param_value(_) for _ in pval]
        elif isinstance(pval, dict) and 'ref' in pval:
            # A reference
            try:
                return self._resolve_ref(pval['ref'])
            except:
                self.logger.error("Error parsing reference: '{}'".format(
                    pval["ref"]))
                raise
        elif isinstance(pval, dict):
            return {k: self._parse_param_value(v) for k, v in pval.items()}
        else:
            return pval

    def _resolve_ref(self, ref):
        """Resolves references."""
        parser = config.reference_parsers.get(ref.get('parser'))
        if parser is None:
            msg = "Invalid reference in layer {}".format(self.cf_name)
            raise ReferenceError(ref, msg, logger=self.logger)
        parameters = ref.get('parameters', {})
        result = parser(self, config.boto_config, **parameters)
        return result

    def delete(self):
        """Deletes a stack in CF."""
        msg = "Deleting stack {} from CF".format(self.cf_name)
        self.logger.info(msg)
        if len(self.children_in_cf) > 0:
            msg = "Layer {} has dependencies ({}): will not be deleted".\
                format(self.name, [x.name for x in self.children_in_cf])
            self.logger.info(msg)
        else:
            self.cf.delete_stack(self.cf_name)

    def create(self, update=False):
        """Deploys a layer as a CF stack."""
        msg = "Starting checks for layer {}".format(self.name)
        self.logger.info(msg)

        if not self.dependencies_met:
            msg = "Dependencies for layer {layer} are not met, skipping"\
                .format(layer=self.name)
            self.logger.critical(msg)
            return

        # CAPABILITY_IAM is needed only for layers that contain certain
        # resources, but we add it  always for simplicity.
        if not self.in_cf:
            self.logger.info("Creating layer '{}' (CF stack '{}')".format(
                self.name, self.cf_name))

            cf_template = json.dumps(self.compile(), indent=4)
            try:
                self.cf.create_stack(
                    self.cf_name,
                    cf_template,
                    self.sns_topic_arn,
                    self.tags)
            except ClientError:
                self.logger.error(
                    "Error deploying stack '{}'".format(self.cf_name))
                self.logger.error("Stack template: {}".format(cf_template))
                raise
        elif update:
            self.logger.info("Updating layer '{}'".format(self.name))
            try:
                self.cf.update_stack(
                    self.cf_name,
                    json.dumps(self.compile(), indent=4),
                    self.sns_topic_arn)
            except NoUpdatesError:
                msg = "No updates on layer '{}'".format(self.name)
                self.logger.warning(msg)
        else:
            msg = "Layer '{}' already in CF: not creating".format(self.name)
            self.logger.info(msg)

        status = self.watch_events()
        if status is None \
                or status not in {'CREATE_COMPLETE', 'UPDATE_COMPLETE'}:
            msg = "Unable to deploy layer '{}': status is {}".format(
                self.name, status)
            raise CloudformationError(msg, logger=self.logger)

        return self.outputs

    def watch_events(self,
                     progress_status={'CREATE_IN_PROGRESS',
                                      'UPDATE_IN_PROGRESS',
                                      'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS'}):
        """Watches CF events during stack creation."""
        stack_status = self.cf.get_stack_status(self.cf_name)
        already_seen = set()
        cm = config.EVENT_STATUS_COLOR_MAP
        while (stack_status is None) or (stack_status in progress_status):
            events = self.cf.get_stack_events(self.cf_name)
            new_events = [ev for ev in events if ev.id not in already_seen]
            for event in new_events:
                self.logger.info(
                    "{time} {color}{status}\033[0m {restype} {logid} {physid} "
                    "{reason}".format(
                        time=event.timestamp.isoformat(),
                        color=cm.get(event.resource_status, ''),
                        status=event.resource_status,
                        restype=event.resource_type,
                        logid=event.logical_resource_id,
                        physid=event.physical_resource_id,
                        reason=event.resource_status_reason,
                    ))
                already_seen.add(event.id)

            time.sleep(5)
            stack_status = self.cf.get_stack_status(self.cf_name)
        return stack_status

    def __repr__(self):
        return str(self)

    def __str__(self):
        args = re.sub(r'\'(\w+)\'\s*:\s*', r'\1=', str(self.user_params))[1:-1]
        if len(args) > 0:
            basestr = "Layer({env}, '{name}', {args})"
        else:
            basestr = "Layer({env}, '{name}')"
        return basestr.format(
            env=self.__environment_repr, name=self.name, args=args)
