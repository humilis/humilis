#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import os.path
import re
import yaml
import logging
import humilis.config as config
from sys import exit
import jinja2
import json
import io
import time
import datetime


class FileFormatError(Exception):
    def __init__(self, filename, logger=None):
        message = "Wrongly formatted file: {}".format(filename)
        super().__init__(message)
        if logger:
            logger.critical(message)


class ReferenceError(Exception):
    def __init__(self, ref, msg, logger=None):
        msg = "Can't parse reference {}: {}".format(ref, msg)
        super().__init__(msg)
        if logger:
            logger.critical(msg)


class CloudformationError(Exception):
    def __init__(self, msg, cf_exception, logger=None):
        msg = "{}: {}".format(msg, cf_exception)
        super().__init__(msg)
        if logger:
            logger.critical(msg)


class Layer():
    """
    A layer of infrastructure that translates into a single cloudformation (CF)
    stack.
    """

    def __init__(self, environment, name, **user_params):
        self.__environment_repr = repr(environment)
        self.cf = environment.cf
        self.logger = logging.getLogger(__name__)
        self.name = "{}-{}".format(environment.name, name)
        self.relname = name
        self.env_name = environment.name
        self.env_basedir = environment.basedir
        self.depends_on = []
        self.section = {}

        self.meta = self.load_section('meta', self.get_section_files('meta'))
        for dep in self.meta.get('dependencies', []):
            self.depends_on.append("{}-{}".format(environment.name, dep))

        self.region = environment.region
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

    @property
    def basedir(self):
        return os.path.join(self.env_basedir, 'layers', self.relname)

    @property
    def already_in_cf(self):
        """
        Returns true if the layer has been already deployed to CF
        """
        return self.name in {stk.stack_name for stk in self.cf.stacks}

    def get_section_files(self, section):
        """
        Produces a list of all files associated with a layer section:
        parameters, resources, mappings, meta, etc
        """
        # We read all files within the section dir, and merge them in a dict
        basedir = os.path.join(self.basedir, section)
        section_files = []
        for (dirpath, dirnames, filenames) in os.walk(basedir):
            section_files += [os.path.join(dirpath, fn) for fn in filenames]

        return section_files

    def load_section(self, section, files):
        """
        Reads all files associated with a layer section (parameters, resources,
        mappings, etc)
        """
        data = self.section.get(section, {})

        for filename in files:
            self.logger.info("Loading {}".format(filename))
            with open(filename, 'r') as f:
                this_data = self.load_file(filename, f)
            if this_data is None:
                continue

            if len(this_data) != 1:
                raise FileFormatError(filename, self.logger)

            data_key = list(this_data.keys())[0]
            if data_key.lower() != section.lower():
                self.logger.critical("Error parsing %s: %s was expected but "
                                     "%s was found" %
                                     (filename, section.title(), data_key))
                exit(1)
            for k, v in list(this_data.values())[0].items():
                data[k] = v

        return data

    def load_file(self, filename, f):
        filename, file_ext = os.path.splitext(filename)
        if file_ext in {'.yml', '.yaml'}:
            data = yaml.load(f)
        elif file_ext == '.json':
            data = json.load(f)
        elif file_ext == '.j2':
            template = jinja2.Template(f.read())
            params = {pname: p['value'] for pname, p in self.params.items()}
            data = template.render(**params)
            data = self.load_file(filename, io.StringIO(data))
        else:
            self.logger.critical("Error loading %s: unknown file "
                                 "extension %s" % filename, file_ext)
            exit(1)

        return data

    def compile(self):
        """Loads all files associated to a layer"""
        # Some templates may refer to params, so populate them first
        self.populate_params()

        # Load all files with layer contents
        for section in config.layer_sections:
            section_files = self.get_section_files(section)
            self.section[section] = self.load_section(section, section_files)

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

    @property
    def dependencies_met(self):
        """
        Checks whether stacks this layer depends on exist in Cloudformation
        """
        current_cf_stack_names = {stack.stack_name for stack in self.cf.stacks}
        for dep in self.depends_on:
            if dep not in current_cf_stack_names:
                return False
        return True

    def populate_params(self):
        """
        Populates parameters in a layer by resolving references if necessary
        """
        if len(self.yaml_params) < 1:
            return
        for pname, param in self.yaml_params.items():
            self.params[pname] = {}
            self.params[pname]['description'] = param.get('description', None)
            self.params[pname]['value'] = self._parse_param_value(
                param['value'])

    def print_params(self):
        """
        Prints the params used during layer creation.
        """
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
        """
        Parses yaml parameters
        """
        if isinstance(pval, list):
            return [self._parse_param_value(_) for _ in pval]
        elif isinstance(pval, dict) and 'ref' in pval:
            return self._resolve_ref(pval['ref'])
        else:
            return pval

    def _resolve_ref(self, ref):
        """
        Resolves a reference to an existing stack component
        """
        try:
            layer_name, resource_name = ref.split('/')
        except ValueError:
            raise ReferenceError(ref, ValueError, self.logger)
        stack_name = "{}-{}".format(self.env_name, layer_name)
        stack = self.cf.get_stack(stack_name)
        resource = [x for x in stack.describe_resources()
                    if x.logical_resource_id == resource_name]
        if len(resource) != 1:
            all_stack_resources = [x.logical_resource_id for x
                                   in stack.describe_resources()]
            msg = "{} does not exist in stack {} (with resources {})".format(
                resource_name, stack_name, all_stack_resources)
            raise ReferenceError(ref, msg, self.logger)
        else:
            resource = resource[0]

        return resource.physical_resource_id

    def delete(self):
        """Deletes a stack in CF"""
        msg = "Deleting stack {} from CF".format(self.name)
        self.logger.info(msg)
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
                template_body=json.dumps(cf_template, indent=4),
                capabilities=['CAPABILITY_IAM'],
                notification_arns=self.sns_topic_arn,
                tags=self.tags)
        except Exception as exception:
                raise CloudformationError(msg, exception)

        return cf_template

    def watch_events(self, progress_status='CREATE_IN_PROGRESS'):
        """Watches CF events during stack creation"""
        if not self.already_in_cf:
            self.logger.warning("Layer {} has not been deployed to CF: "
                                "nothing to watch".format(self.name))
            return
        stack = self.cf.describe_stacks(self.name)[0]
        already_seen = {}
        cm = self.config.status_color_map
        while stack.status == progress_status:
            events = sorted(self.cf.describe_stack_events(self.name),
                            key=lambda ev: ev.timestamp)
            new_events = [ev for ev in events
                          if (ev.timestamp, ev.logical_resource_id)
                          not in already_seen]
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
                already_seen.add((event.timestamp, event.logical_resource_id))

            stack.update()
            time.sleep(3)
        return stack.status

    def __repr__(self):
        return str(self)

    def __str__(self):
        args = re.sub(r'\'(\w+)\'\s*:\s*', r'\1=', str(self.user_params))[1:-1]
        return "Layer({env}, '{name}', {args})".format(
            env=self.__environment_repr, name=self.relname, args=args)
