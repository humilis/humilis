"""Humilis environment."""

import logging
import os

import boto3
from boto3facade.cloudformation import Cloudformation
from boto3facade.dynamodb import Dynamodb
from boto3facade.kms import Kms
import jinja2 as j2
import json
import yaml
import six

from humilis.config import config
from humilis.exceptions import (FileFormatError, RequiresVaultError,
                                MissingParentLayerError, CloudformationError)
from humilis.layer import Layer
import humilis.utils as utils


class Environment():
    """Manages the deployment of a collection of humilis layers."""
    def __init__(self, yml_path, logger=None, stage=None, vault_layer=None,
                 parameters=None):
        if logger is None:
            self.logger = logging.getLogger(__name__)
            # To prevent warnings
            self.logger.addHandler(logging.NullHandler())
        else:
            self.logger = logger

        if stage is None:
            raise ValueError("stage can't be None")

        self.__yml_path = yml_path
        self.stage = stage and stage.upper()
        basedir, envfile = os.path.split(yml_path)
        self.basedir = os.path.abspath(basedir)
        self._j2_env = j2.Environment(
            loader=j2.FileSystemLoader(self.basedir))
        # Add custom functions and filters
        utils.update_jinja2_env(self._j2_env)

        parameters = self._preprocess_parameters(parameters)
        with open(yml_path, 'r') as f:
            if os.path.splitext(yml_path)[1] == ".j2":
                template = self._j2_env.get_template(envfile)
                meta = yaml.load(template.render(
                    stage=stage,    # Backwards compatibility
                    __context={
                        'stage': stage,
                        'aws': {
                            'account_id': boto3.client('sts').get_caller_identity().get('Account')}
                        },
                    __env=os.environ,
                    **parameters), Loader=yaml.FullLoader)
            else:
                meta = yaml.load(f, Loader=yaml.FullLoader)

        self.name = list(meta.keys())[0]
        self.meta = meta.get(self.name)

        if len(self.meta) == 0:
            raise FileFormatError(yml_path, "Error getting environment name ",
                                  logger=self.logger)

        self.cf = Cloudformation(config.boto_config)
        self.sns_topic_arn = self.meta.get('sns-topic-arn', [])
        self.tags = self.meta.get('tags', {})
        self.tags['humilis:environment'] = self.name

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

        self.vault_layer = self.get_layer(vault_layer or 'secrets-vault')
        self.__secrets_table_name = "{}-{}-secrets".format(self.name,
                                                           self.stage)
        self.__keychain_namespace = "{}:{}".format(self.name,
                                                   self.stage.lower())
        self.__dynamodb = None

    def _preprocess_parameters(self, parameters):
        """Apply default values to unspecified stage parameters."""
        if parameters is None:
            return {}
        if isinstance(parameters, six.string_types):
            # A file path
            if os.path.splitext(parameters)[1] == ".j2":
                _, pfile = os.path.split(parameters)
                template = self._j2_env.get_template(pfile)
                parameters = yaml.load(template.render(
                    __context={'stage': self.stage},
                    __env=os.environ), Loader=yaml.FullLoader)
            else:
                with open(parameters, "r") as f:
                    parameters = yaml.load(f.read(), Loader=yaml.FullLoader)
        if self.stage in parameters or "_default" in parameters:
            stage_params = parameters.get("_default", {})
            stage_params.update(parameters.get(self.stage, {}))
        else:
            stage_params = parameters
        return stage_params

    @property
    def outputs(self):
        """Outputs produced by each environment layer."""
        outputs = {}
        self.cf.flush_cache()
        for layer in self.layers:
            try:
                ly = layer.outputs
            except CloudformationError:
                self.logger.error("Could not retrieve outputs for layer"
                                  " '{}'".format(layer.name))
                ly = None
            if ly is not None:
                outputs[layer.name] = ly
        return outputs

    @property
    def resources(self):
        """Resources produced by each environment layer."""
        resources = {}
        for layer in self.layers:
            try:
                ly = layer.resources
            except CloudformationError:
                self.logger.error("Could not retrieve resources for layer"
                                  " '{}'".format(layer.name))
                ly = None
            if ly is not None:
                resources[layer.name] = ly
        return resources

    @property
    def kms_key_id(self):
        """The ID of the KMS Key associated to the environment vault."""
        if not self.vault_layer:
            raise RequiresVaultError("Requires a secrets-vault layer")
        if self.vault_layer:
            return self.outputs[self.vault_layer.name]['KmsKeyId']

    @property
    def dynamodb(self):
        """Connection to AWS DynamoDB."""
        if self.__dynamodb is None:
            self.__dynamodb = Dynamodb(config.boto_config)
        return self.__dynamodb

    def set_secret(self, key, plaintext):
        """Sets and environment secret."""
        if not self.vault_layer:
            msg = "No secrets-vault layer in this environment"
            self.logger.error(msg)
            raise RequiresVaultError(msg)
        else:
            client = Kms(config.boto_config).client
            encrypted = client.encrypt(KeyId=self.kms_key_id,
                                       Plaintext=plaintext)['CiphertextBlob']
            resp = self.dynamodb.client.put_item(
                TableName=self.__secrets_table_name,
                Item={'id': {'S': key}, 'value': {'B': encrypted}})
            return resp

    def get_secret(self, key):
        """Retrieves a secret."""
        if not self.vault_layer:
            msg = "No secrets-vault layer in this environment"
            self.logger.error(msg)
            raise RequiresVaultError(msg)
        else:
            client = Dynamodb(config.boto_config).client
            encrypted = client.get_item(
                TableName=self.__secrets_table_name,
                Key={'id': {'S': key}})['Item']['value']['B']

            # Decrypt using KMS (assuming the secret value is a string)
            client = boto3.client('kms')
            plaintext = client.decrypt(CiphertextBlob=encrypted)['Plaintext']
            return plaintext.decode()

    def delete_secret(self, key):
        """Deletes a secret."""
        if not self.vault_layer:
            msg = "No secrets-vault layer in this environment"
            self.logger.error(msg)
            raise RequiresVaultError(msg)
        else:
            client = Dynamodb(config.boto_config).client
            resp = client.delete_item(
                TableName=self.__secrets_table_name,
                Key={'id': {'S': key}})['Item']['value']['B']

            return resp

    def create(self, output_file=None, update=False, debug=False):
        """Creates or updates an environment."""
        for layer in self.layers:
            layer.create(update=update, debug=debug)
        self.logger.info({"outputs": self.outputs})
        if output_file is not None:
            self.write_outputs(output_file)

    def write_outputs(self, output_file=None):
        """Writes layer outputs to a YAML or JSON file."""
        if output_file is None:
            output_file = "{environment}-{stage}.outputs.yaml"

        output_file = output_file.format(environment=self.name,
                                         stage=self.stage)

        _, ext = os.path.splitext(output_file)
        with open(output_file, "w") as f:
            if ext.lower() == ".yaml":
                f.write(yaml.dump(self.outputs, indent=4,
                                  default_flow_style=False))
            else:
                f.write(json.dumps(self.outputs, indent=4))

    def get_layer(self, layer_name):
        """Gets a layer by name"""
        sel_layer = [layer for layer in self.layers
                     if layer.cf_name == layer_name or
                     layer.name == layer_name]
        if len(sel_layer) > 0:
            return sel_layer[0]

    def delete(self):
        """Deletes the complete environment from CF."""
        for layer in reversed(self.layers):
            if layer.termination_protection:
                self.logger.warning(
                    "Layer '%s' has termination protection set: "
                    "will not be deleted", layer.name)
            else:
                layer.delete()

    @property
    def in_cf(self):
        """Returns true if the environment has been deployed to CF."""
        return self.name in {
            utils.unroll_tags(stk['Tags']).get('humilis:environment')
            for stk in self.cf.stacks}

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Environment('{}')".format(self.__yml_path)
