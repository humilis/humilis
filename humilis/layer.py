#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import os.path
import re
import logging
import humilis.config as config
from humilis.utils import DirTreeBackedObject
from humilis.exceptions import ReferenceError, CloudformationError
from humilis.ec2 import EC2
from boto3.session import Session
import json
import time
import datetime


class Layer():
    """A layer of infrastructure that translates into a single CF stack"""
    def __init__(self, environment, name, logger=None, loader=None,
                 **user_params):
        self.__environment_repr = repr(environment)
        self.cf = environment.cf
        if logger is None:
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger
        self.name = "{}-{}".format(environment.name, name)
        self.relname = name
        self.env_name = environment.name
        self.env_basedir = environment.basedir
        self.depends_on = []
        self.section = {}
        if loader is None:
            loader = DirTreeBackedObject(self.basedir, self.logger)
        self.loader = loader
        self.children = set()

        self.meta = self.loader.load_section('meta')
        for dep in self.meta.get('dependencies', []):
            self.depends_on.append("{}-{}".format(environment.name, dep))

        self.sns_topic_arn = environment.sns_topic_arn
        self.tags = {
            'humilis-layer': self.name,
            'humilis-created-on': str(datetime.datetime.now())}
        for tagname, tagvalue in environment.tags.items():
            self.tags[tagname] = tagvalue

        for tagname, tagvalue in self.meta.get('tags', {}).items():
            self.tags[tagname] = tagvalue

        self.yaml_params = self.meta.get('parameters', {})

        # User params override what is in the layer definition file
        self.user_params = user_params
        for pname, pvalue in user_params.items():
            if pname not in self.yaml_params:
                msg = "Unknown parameter {pname} for layer {layer}: ignored"\
                    .format(pname=pname, layer=self.relname)
                self.logger.warning(msg)
            else:
                self.yaml_params[pname]['value'] = pvalue

        # These param set will be sent to the template compiler and will be
        # populated once the layers this layer depend on have been created.
        self.params = {}

        self.__ec2 = None

    @property
    def basedir(self):
        return os.path.join(self.env_basedir, 'layers', self.relname)

    @property
    def already_in_cf(self):
        """Returns true if the layer has been already deployed to CF
        """
        return self.name in {stk['StackName'] for stk in self.cf.stacks}

    @property
    def ec2(self):
        """Connection to AWS EC2 service"""
        if self.__ec2 is None:
            self.__ec2 = EC2()
        return self.__ec2

    @property
    def children_in_cf(self):
        """List of (already created) children layers"""
        if self.already_in_cf:
            clist = self.cf.get_stack(self.name).tags.get('humilis-children')
            if len(clist) > 0:
                return clist.split(',')

    @property
    def ok(self):
        """Layer is fully deployed in CF and ready for use"""
        return self.cf.stack_ok(self.name)

    @property
    def outputs(self):
        """Layer outputs. Throws an exception if layer is not ok."""
        if not self.ok:
            msg = ("Attempting to read outputs from a layer that has not "
                   "been fully deployed yet")
            raise CloudformationError(msg, logger=self.logger)
        ly = self.cf.stack_outputs[self.name]
        if ly is not None:
            ly = {o['OutputKey']: o['OutputValue'] for o in ly}
        return ly

    @property
    def dependencies_met(self):
        """Checks whether stacks this layer depends on exist in Cloudformation
        """
        current_cf_stack_names = {stack.get('StackName') for stack
                                  in self.cf.stacks}
        for dep in self.depends_on:
            if dep not in current_cf_stack_names:
                return False
        return True

    def add_child(self, child_name):
        """Adds a child to this layer"""
        self.children.add(child_name)
        self.tags['humilis-children'] = ','.join(self.children)

    def compile(self):
        """Loads all files associated to a layer"""
        # Some templates may refer to params, so populate them first
        self.populate_params()
        self.loader.params = self.params

        # Load all files with layer contents
        for section in config.layer_sections:
            self.section[section] = self.loader.load_section(section)

        # Package the layer as a CF template
        cf_template = {
            'AWSTemplateFormatVersion': str(config.cf_template_version),
            'Description': self.meta.get('description', ''),
            'Mappings': self.section.get('mappings', {}),
            'Parameters': self.section.get('parameters', {}),
            'Resources': self.section.get('resources', {}),
            'Outputs': self.section.get('outputs', {})
        }
        return cf_template

    def populate_params(self):
        """Populates parameters in a layer by resolving references if necessary
        """
        if len(self.yaml_params) < 1:
            return
        for pname, param in self.yaml_params.items():
            self.params[pname] = {}
            self.params[pname]['description'] = param.get('description', None)
            self.params[pname]['value'] = self._parse_param_value(
                param['value'])

        # The humilis param contains humilis-specific info such as config
        # options and the name of the current layer
        humilis = {'layer_name': self.name, 'config': config}
        self.params['humilis'] = {'value': humilis}

    def print_params(self):
        """Prints the params used during layer creation"""
        if len(self.params) < 1:
            print("No parameters. Did you forget to run populate_params()?")
            return
        print("Parameters for layer {}:".format(self.name))
        for pname, param in self.params.items():
            pval = param.get('value', None)
            if len(pval) > 30:
                pval = pval[0:30]
            print("{pname:<15}: {pval:>30}".format(pname=pname, pval=pval))

    def _parse_param_value(self, pval):
        """Parses yaml parameters"""
        if isinstance(pval, list):
            # A list of values: parse each one individually
            return [self._parse_param_value(_) for _ in pval]
        elif isinstance(pval, dict) and 'ref' in pval:
            # Reference to a physical resource in another layer, or to a
            # resource already deployed to AWS
            return self._resolve_ref(pval['ref'])
        elif isinstance(pval, dict) and 'envvar' in pval:
            # An environment variable
            return os.environ(pval['envvar'])
        elif isinstance(pval, dict):
            return {k: self._parse_param_value(v) for k, v in pval.items()}
        else:
            return pval

    def _resolve_ref(self, ref):
        """
        Resolves a reference to an existing stack component or to a resource
        that currently lives in AWS but that has been deployed independently.
        The latter is only possible for EC2 instances at the moment.
        """
        try:
            ref_name, selection = ref.split('/')
        except ValueError:
            raise ReferenceError(ref, ValueError, self.logger)

        if ref_name[0] == ':':
            # Custom references to AWS or local resources
            _, ref_type, *ref_name = ref_name.split(':')  # noqa
            ref_name = ':'.join(ref_name)
            if ref_type == 'aws':
                return self._resolve_boto_ref(ref_name, selection)
            elif ref_type == 'file':
                return self._resolve_file_ref(selection)
            else:
                msg = "Unknown reference type {}".format(ref_type)
                raise ReferenceError(ref, msg, self.logger)
        else:
            return self._resolve_layer_ref(ref_name, selection)

    def _resolve_file_ref(self, selection):
        """Resolves a reference to a local file"""
        file_path = os.path.join(self.basedir, selection)
        # Upload the file to S3

        with open(file_path, 'r') as f:
            return f.read()

    def _resolve_boto_ref(self, resource_type, selection):
        """Resolves a reference to an existing AWS resource that has been
        deployed independently.
        """
        ref = ':' + resource_type + '/' + selection
        if resource_type == 'ec2:ami':
            tags = selection.split(';')
            tag_dict = {}
            for tag in tags:
                k, v = tag.split('=')
                tag_dict[k] = v
            amis = self.ec2.get_ami_by_tag(tag_dict)
            if len(amis) == 0:
                msg = "No AMIs with tags {} were found".format(tag_dict)
                raise ReferenceError(ref, msg, logger=self.logger)
            elif len(amis) > 1:
                msg = "Ambiguous AMI selection. I found {} AMIs with tags {}".\
                    format(len(amis), tag_dict)
                raise ReferenceError(ref, msg, logger=self.logger)
            else:
                return amis[0]['ImageId']
        else:
            msg = "Unsupported resource type: {}".format(resource_type)
            raise ReferenceError(ref, msg, logger=self._logger)

    def _resolve_layer_ref(self, layer_name, resource_name):
        """Resolves a reference to an existing stack component"""
        stack_name = "{}-{}".format(self.env_name, layer_name)
        resource = self.cf.get_stack_resource(stack_name, resource_name)

        if len(resource) != 1:
            all_stack_resources = [x.logical_resource_id for x
                                   in self.cf.get_stack_resources(stack_name)]
            msg = "{} does not exist in stack {} (with resources {})".format(
                resource_name, stack_name, all_stack_resources)
            raise ReferenceError(stack_name + '/' + resource_name,
                                 msg, logger=self.logger)
        else:
            resource = resource[0]

        return resource.physical_resource_id

    def delete(self):
        """Deletes a stack in CF"""
        msg = "Deleting stack {} from CF".format(self.name)
        self.logger.info(msg)
        if self.children:
            msg = "Layer {} has dependencies ({}) : will not be deleted".\
                format(self.name, self.children)
            self.logger.info(msg)
        else:
            self.cf.delete_stack(self.name)

    def create(self):
        """Creates a stack in CF"""
        msg = "Starting checks for creation of layer {}".format(self.name)
        self.logger.info(msg)

        if not self.dependencies_met:
            msg = "Dependencies for layer {layer} are not met, skipping"\
                .format(layer=self.name)
            self.logger.critical(msg)
            return

        cf_template = self.compile()
        # CAPABILITY_IAM is needed only for layers that contain certain
        # resources, but we add it  always for simplicity.
        try:
            self.cf.create_stack(
                self.name,
                json.dumps(cf_template, indent=4),
                self.sns_topic_arn,
                self.tags)
            # Try getting the output params of the stack
        except Exception as exception:
                raise CloudformationError(msg, exception, logger=self.logger)

        status = self.watch_events()
        if status != 'CREATE_COMPLETE':
            msg = "Layer could not be created, status is {}".format(status)
            raise CloudformationError(msg, logger=self.logger)

        return cf_template

    def watch_events(self, progress_status='CREATE_IN_PROGRESS'):
        """Watches CF events during stack creation"""
        if not self.already_in_cf:
            self.logger.warning("Layer {} has not been deployed to CF: "
                                "nothing to watch".format(self.name))
            return
        stack_status = self.cf.get_stack_status(self.name)
        already_seen = set()
        cm = config.event_status_color_map
        while stack_status == progress_status:
            events = self.cf.get_stack_events(self.name)
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

            stack_status = self.cf.get_stack_status(self.name)
            time.sleep(3)
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
            env=self.__environment_repr, name=self.relname, args=args)
