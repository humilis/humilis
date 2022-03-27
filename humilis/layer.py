"""Humilis Layer."""

import itertools
import os
import os.path
import re
import logging
import time
import uuid
from humilis.config import config
from humilis.utils import DirTreeBackedObject, get_cf_name
from humilis.exceptions import (ReferenceError, CloudformationError,
                                MissingPluginError)
import boto3
from boto3facade.s3 import S3
from boto3facade.ec2 import Ec2
from boto3facade.cloudformation import Cloudformation
from boto3facade.exceptions import NoUpdatesError
import json
import yaml
import datetime
from uuid import uuid4


def _is_legacy_reference(value):
    """True if a parameter value is a reference using legacy syntax."""
    return isinstance(value, dict) and 'ref' in value and \
        'parser' in value["ref"]


def _is_reference(value):
    """True if a parameter value is a reference."""
    return isinstance(value, dict) and len(value) == 1 and \
        list(value.keys())[0][0] == '$'


class Layer:
    """A layer of infrastructure that translates into a single CF stack"""
    def __init__(self, __env, __name, layer_type=None, logger=None,
                 loader=None, humilis_profile=None, **user_params):
        self.__environment_repr = repr(__env)
        self.environment = __env
        if not humilis_profile:
            self.cf = self.environment.cf
        else:
            config.boto_config.activate_profile(humilis_profile)
            self.cf = Cloudformation(config.boto_config)
        if logger is None:
            self.logger = logging.getLogger(__name__)
            # To prevent warnings
            self.logger.addHandler(logging.NullHandler())
        else:
            self.logger = logger
        self.name = __name
        self.env_name = self.environment.name
        self.env_stage = self.environment.stage
        self.env_basedir = self.environment.basedir
        self.depends_on = []
        self.section = {}
        self.type = layer_type
        self.s3_prefix = "{base}{env}/{stage}/{layer}/".format(
            base=config.boto_config.profile.get("s3prefix"),
            env=self.environment.name,
            stage=self.environment.stage,
            layer=__name)

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

        # These param set will be sent to the template compiler and will be
        # populated once the layers this layer depend on have been created.
        self.params = {}

        # the parameters that will be used to compile meta.yaml
        self.meta = {}
        meta_params = {p[0]: p[1] for p
                       in itertools.chain(self.loader_params.items(),
                                          user_params.items())}
        self.meta = self.loader.load_section('meta', params=meta_params)
        self.sns_topic_arn = self.environment.sns_topic_arn
        self.tags = {
            'humilis:environment': self.env_name,
            'humilis:layer': self.name,
            'humilis:stage': self.env_stage,
            'humilis:created': str(datetime.datetime.now())}
        for tagname, tagvalue in self.environment.tags.items():
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
    def termination_protection(self):
        """Is termination protection set for this layer?."""
        return self.meta.get('parameters', {}).get(
            'termination_protection', {}).get('value', False)

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

        # For backwards compatibility, to be deprecated
        params = {k: v['value'] for k, v in self.params.items()
                  if 'value' in v}

        params["__vars"] = dict(params)

        # For backwards compatibility, to be deprecated
        params['_env'] = {'stage': self.env_stage, 'name': self.env_name,
                          'basedir': self.env_basedir}
        params['_os_env'] = os.environ
        params['_layer'] = {'name': self.name}
        params['env'] = os.environ

        # The new format:
        params['__env'] = os.environ
        params['__context'] = {
            'environment': {
                'name': self.env_name,
                'basedir': self.env_basedir,
                'tags': self.environment.tags
            },
            'stage': self.env_stage,
            'layer': {
                'name': self.name,
                'basedir': self.basedir
            },
            'aws': {
                'account_id': boto3.client('sts').get_caller_identity().get('Account')
            }
        }

        # For backwards compatibility
        params["context"] = params["__context"]
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
    def ok(self):
        """Layer is fully deployed in CF and ready for use"""
        return self.cf.stack_ok(self.cf_name)

    @property
    def outputs(self):
        """Layer CF outputs."""
        ly = self.cf.stack_outputs.get(self.cf_name)
        if ly:
            ly = {o['OutputKey']: o['OutputValue'] for o in ly}
        return ly

    @property
    def resources(self):
        """Layer CF resources."""
        ly = self.cf.get_stack_resources(self.cf_name)
        if ly:
            ly = {o.logical_id: o.physical_resource_id for o in ly}
        return ly

    def compile(self):
        """Loads all files associated to a layer."""
        # Some templates may refer to params, so populate them first
        self.populate_params()

        # Load all files with layer contents
        for section in config.LAYER_SECTIONS:
            self.section[section] = self.loader.load_section(
                section, params=self.loader_params)

        # Package the layer as a CF template
        default_description = "{}-{} ({})".format(
            self.environment.name, self.name, self.environment.stage)
        description = self.params.get('description', {}).get('value') or \
                self.environment.meta['description'] or \
                self.meta.get('description') or \
                default_description
        cf_template = {
            'AWSTemplateFormatVersion': str(config.CF_TEMPLATE_VERSION),
            'Description': description,
            'Mappings': self.section.get('mappings', {}),
            'Parameters': self.section.get('parameters', {}),
            'Resources': self.section.get('resources', {}),
            'Outputs': self.section.get('outputs', {})
        }
        if self.section.get('transform', {}).get('value', {}):
            cf_template['Transform'] = self.section['transform']['value']
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
            return [self._parse_param_value(_) for _ in pval]
        elif _is_reference(pval):
            return self._resolve_ref(
                list(pval.keys())[0][1:], list(pval.values())[0])
        elif _is_legacy_reference(pval):
            return self._resolve_ref(
                pval['ref']['parser'], pval['ref'].get('parameters', {}))
        elif isinstance(pval, dict):
            return {k: self._parse_param_value(v) for k, v in pval.items()}
        else:
            return pval

    def _resolve_ref(self, parsername, parameters):
        """Resolves references."""
        parser = config.reference_parsers.get(parsername)
        if not parser:
            msg = "Invalid reference parser '{}' in layer '{}'".format(
                parsername, self.cf_name)
            raise ReferenceError(ref, msg, logger=self.logger)
        result = parser(self, config.boto_config, **parameters)
        return result

    def delete(self):
        """Deletes a stack in CF."""
        msg = "Deleting stack {} from CF".format(self.cf_name)
        self.logger.info(msg)
        self.cf.delete_stack(self.cf_name)

    def create(self, update=False, debug=False):
        """Deploys a layer as a CF stack."""
        msg = "Starting checks for layer {}".format(self.name)
        self.logger.info(msg)
        cf_template = None

        # CAPABILITY_IAM is needed only for layers that contain certain
        # resources, but we add it  always for simplicity.
        if not self.in_cf:
            self.logger.info("Creating layer '{}' (CF stack '{}')".format(
                self.name, self.cf_name))

            cf_template = self.compile()
            try:
                self.create_with_changeset(cf_template)
            except Exception:
                self.logger.error(
                    "Error deploying stack '{}'".format(self.cf_name))
                self.logger.error("Stack template: {}".format(
                    json.dumps(cf_template, indent=4)))
                raise
        elif update:
            cf_template = self.compile()
            try:
                self.create_with_changeset(cf_template, update)
            except NoUpdatesError:
                msg = "Nothing to update on stack '{}'".format(self.cf_name)
                self.logger.warning(msg)
            except Exception:
                self.logger.error(
                    "Error deploying stack '{}'".format(self.cf_name))
                self.logger.error("Stack template: {}".format(
                    json.dumps(cf_template, indent=4)))
                raise
        else:
            msg = "Layer '{}' already in CF: not creating".format(self.name)
            self.logger.info(msg)

        if debug and cf_template:
            directory = os.path.join(self.env_basedir, "debug_output")
            if not os.path.exists(directory):
                os.makedirs(directory)
            with open(os.path.join(directory, self.name + ".yaml"), "w") as f:
                yaml.dump(cf_template, f, default_flow_style=False)

        return self.outputs

    def _upload_cf_template(self, cf_template):
        """Upload CF template to S3."""
        bucket = config.boto_config.profile.get('bucket')
        key = "{}{}-{}.json".format(
            self.s3_prefix, round(time.time()), str(uuid.uuid4()))
        cf_template = json.dumps(cf_template).encode()
        S3().resource.Bucket(bucket).put_object(Key=key, Body=cf_template)
        return "https://s3-{}.amazonaws.com/{}/{}".format(
            config.boto_config.profile['aws_region'], bucket, key)

    def create_with_changeset(self, cf_template, update=False):
        """Use a changeset to create a stack."""
        changeset_type = "CREATE"
        if update:
            changeset_type = "UPDATE"
        changeset_name = self.cf_name + str(uuid4())
        template_url = self._upload_cf_template(cf_template)
        self.cf.client.create_change_set(
            StackName=self.cf_name,
            TemplateURL=template_url,
            Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
            NotificationARNs=self.sns_topic_arn,
            Tags=[{"Key": k, "Value": v} for k, v in self.tags.items()],
            ChangeSetName=changeset_name,
            ChangeSetType=changeset_type)
        self.wait_for_status_change()
        self.wait_changeset_creation(changeset_name)
        if update:
            changeset = self.cf.client.describe_change_set(
                ChangeSetName=changeset_name,
                StackName=self.cf_name)
            if not changeset["Changes"]:
                raise NoUpdatesError("Nothing to update")
        self.cf.client.execute_change_set(ChangeSetName=changeset_name,
                                          StackName=self.cf_name)
        self.wait_for_status_change()

    @staticmethod
    def _is_bad_status(status):
        """True if a stack status is not healthy."""
        return status is None \
                or status not in {"CREATE_COMPLETE", "UPDATE_COMPLETE",
                                  "REVIEW_IN_PROGRESS",
                                  "UPDATE_ROLLBACK_COMPLETE"}

    def _print_events(self, already_seen=None):
        """Prints the events reported by AWS."""
        if already_seen is None:
            already_seen = set()

        events = self.cf.get_stack_events(self.cf_name)
        new_events = [ev for ev in events if ev.id not in already_seen]
        cm = config.EVENT_STATUS_COLOR_MAP
        for event in new_events:
            self.logger.info(
                "{color}{status}\033[0m {restype} {logid} "
                "{reason}".format(
                    color=cm.get(event.resource_status, ''),
                    status=event.resource_status,
                    restype=event.resource_type,
                    logid=event.logical_resource_id,
                    reason=event.resource_status_reason or "",
                ))
            already_seen.add(event.id)

        return already_seen

    def wait_for_status_change(self):
        """Wait for the status deployment state to change."""
        status, seen_events = self.watch_events()
        if self._is_bad_status(status):
            # One retry, also to flush all events
            status, seen_events = self.watch_events(already_seen=seen_events)
            if self._is_bad_status(status):
                # One retry
                msg = "Unable to deploy layer '{}': status is {}".format(
                    self.name, status)
                raise CloudformationError(msg, logger=self.logger)
        return status

    def watch_events(self,
                     progress_status={'CREATE_IN_PROGRESS',
                                      'UPDATE_IN_PROGRESS',
                                      'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS'},
                     already_seen=None):
        """Watches CF events during stack creation."""
        stack_status = self.cf.get_stack_status(self.cf_name)
        if already_seen is None:
            already_seen = set()
        while (stack_status is None) or (stack_status in progress_status):
            already_seen = self._print_events(already_seen)
            time.sleep(5)
            stack_status = self.cf.get_stack_status(self.cf_name)

        return stack_status, already_seen

    def wait_changeset_creation(self, changeset_name,
                                progress_status={"CREATE_PENDING",
                                                 "CREATE_IN_PROGRESS"}):
        """Wait for a changeset to be in the right status to be executed."""
        status = self.cf.client.describe_change_set(
            ChangeSetName=changeset_name, StackName=self.cf_name)["Status"]
        while (status is None) or (status in progress_status):
            status = self.cf.client.describe_change_set(
                ChangeSetName=changeset_name, StackName=self.cf_name)["Status"]
            time.sleep(5)
        if status != "CREATE_COMPLETE":
            msg = "Unable to deploy layer '{}': changeset status is {}".format(
                self.name, status)
            raise CloudformationError(msg, logger=self.logger)
        return status

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
