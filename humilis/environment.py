#!/usr/bin/env python
# -*- coding: utf-8 -*-


import os
import humilis.config as config
from humilis.layer import Layer
from humilis.cloudformation import CloudFormation
import yaml


class Environment():
    """
    An environment represents a collection of infrastructure layers serving
    a common purpose.
    """
    def __init__(self, yml_path):
        self.__yml_path = yml_path
        self.name = os.path.splitext(os.path.split(yml_path)[1])[0]
        self.basedir = os.path.split(yml_path)[0]
        with open(yml_path, 'r') as f:
            self.meta = yaml.load(f)

        self.region = self.meta.get('region', config.region)
        self.cf = CloudFormation(region=self.region)
        self.sns_topic_arn = self.meta.get('sns-topic-arn', [])
        self.tags = self.meta.get('tags', {})
        self.tags['humilis-environment'] = self.name

        self.layers = []
        for layer in self.meta.get('layers', []):
            layer_name = layer.get('layer', None)
            if layer_name is None:
                self.logger.critical(
                    "Wrongly formatted layer: {}".format(layer))
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
        for layer in self.layers:
            layer.create()

    def delete(self):
        """
        Deletes all layers in an environment
        """
        for layer in reversed(self.layers):
            layer.delete()

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Environment('{}')".format(self.__yml_path)
