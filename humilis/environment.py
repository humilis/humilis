#!/usr/bin/env python
# -*- coding: utf-8 -*-


import logging
import os
import humilis.config as config
from humilis.layer import Layer
from humilis.cloudformation import CloudFormation
from humilis.exceptions import FileFormatError
import yaml


class Environment():
    """
    An environment represents a collection of infrastructure layers serving
    a common purpose.
    """
    def __init__(self, yml_path, logger=None):
        if logger is None:
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger
        self.__yml_path = yml_path
        self.name = os.path.splitext(os.path.split(yml_path)[1])[0]
        self.basedir = os.path.split(yml_path)[0]
        with open(yml_path, 'r') as f:
            self.meta = yaml.load(f).get(self.name)

        if len(self.meta) == 0:
            raise FileFormatError(yml_path, logger=self.logger)

        self.region = self.meta.get('region', config.region)
        self.cf = CloudFormation(region=self.region)
        self.sns_topic_arn = self.meta.get('sns-topic-arn', [])
        self.tags = self.meta.get('tags', {})
        self.tags['humilis-environment'] = self.name

        self.layers = []
        for layer in self.meta.get('layers', []):
            layer_name = layer.get('layer', None)
            if layer_name is None:
                msg = "Wrongly formatted layer: {}".format(layer)
                raise FileFormatError(yml_path, msg)
            if layer.get('disable', False):
                message = ("Layer {} is disabled by configuration. "
                           "Skipping.".format(layer.get('layer')))
                self.logger.warning(message)
                continue

            # Get the layer params provided in the environment spec
            layer_params = {k: v for k, v in layer.items() if k != 'layer'}
            layer_obj = Layer(self, layer_name, **layer_params)
            self.layers.append(layer_obj)

    def create(self):
        """
        Creates all layers in the environment
        """
        self.populate_hierarchy()
        for layer in self.layers:
            layer.create()

    def populate_hierarchy(self):
        """
        Adds tags to the layers indicating parent-child dependencies
        """
        for layer in self.layers:
            if layer.depends_on and len(layer.depends_on) > 0:
                for parent_name in layer.depends_on:
                    layer = self.get_layer(parent_name).add_child(layer.name)

    def get_layer(self, layer_name):
        """
        Gets a layer by name
        """
        sel_layer = [layer for layer in self.layers
                     if layer.name == layer_name]
        if len(sel_layer) > 0:
            return sel_layer[0]

    def delete(self):
        """
        Deletes all layers in an environment
        """
        for layer in reversed(self.layers):
            layer.delete()

    @property
    def already_in_cf(self):
        """
        Returns true if the environment has been already deployed to CF
        """
        return self.name in {stk.tags.get('humilis-environment')
                             for stk in self.cf.stacks}

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Environment('{}')".format(self.__yml_path)
