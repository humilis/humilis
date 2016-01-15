# -*- coding: utf-8 -*-

"""Built-in reference parsers."""


import os
import importlib

import boto3facade
from boto3facade.s3 import S3
from boto3facade.cloudformation import Cloudformation

from humilis.exceptions import ReferenceError
from humilis.utils import reference_parser


@reference_parser
def file(layer, config, path=None):
    """Uploads a local file to S3 and returns the corresponding S3 path.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param path: Path to the file, relative to the location of meta.yaml.
    """
    full_path = os.path.join(layer.basedir, path)
    s3key = "{base_prefix}{env_name}/{layer_name}/{file_name}".format(
        base_prefix=config.profile.get('s3prefix', ''),
        env_name=layer.env_name,
        layer_name=layer.relname,
        file_name=os.path.basename(full_path))
    s3bucket = config.profile.get('bucket')
    s3 = S3(config)
    s3.cp(full_path, s3bucket, s3key)
    return {'s3bucket': s3bucket, 's3key': s3key}


@reference_parser
def layer(layer, config, layer_name=None, resource_name=None):
    """Gets the logical ID of a resource in an already deployed layer.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param layer_name: The name of the layer that contains the target resource.
    :param resource_name: The logical name of the target resource.
    """
    stack_name = "{}-{}".format(layer.env_name, layer_name)
    cf = Cloudformation(config)
    resource = cf.get_stack_resource(stack_name, resource_name)

    if len(resource) < 1:
        all_stack_resources = [x.logical_resource_id for x
                               in cf.get_stack_resources(stack_name)]
        msg = "{} does not exist in stack {} (with resources {}).".format(
            resource_name, stack_name, all_stack_resources)
        raise ReferenceError(resource_name, msg, logger=layer.logger)

    return resource[0].physical_resource_id


@reference_parser
def output(layer, config, layer_name=None, output_name=None):
    """Gets the value of an output produced by an already deployed layer.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param layer_name: The logical name of the layer that produced the output.
    :param output_name: The logical name of the output parameter.
    """
    stack_name = "{}-{}".format(layer.env_name, layer_name)
    cf = Cloudformation(config)
    output = cf.get_stack_output(stack_name, output_name)
    if len(output) < 1:
        all_stack_outputs = list(cf.stack_outputs(layer_name).keys())
        msg = ("{} output does not exist for stack {} "
               "(with outputs {}).").format(output_name,
                                            stack_name,
                                            all_stack_outputs)
        ref = "output ({}/{})".format(layer_name, output_name)
        raise ReferenceError(ref, msg, logger=layer.logger)
    return output[0]


@reference_parser
def boto3(layer, config, service=None, call=None, output_attribute=None,
          output_key=None):
    """Calls a boto3facade method.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param service: The name of the AWS service.
    :param call: A dict with two keys: method, and parameters.
    """
    facade_name = service.title()
    if not hasattr(boto3facade, service):
        ref = "boto3facade.{}.{}.{}: {}".format(service, facade_name,
                                                call['method'],
                                                call['parameters'])
        msg = "Service {} not supported".format(service)
        raise ReferenceError(ref, msg, logger=layer.logger)

    module = importlib.import_module("boto3facade.{}".format(service))
    facade_cls = getattr(module, facade_name)
    facade = facade_cls(config)
    method = getattr(facade, call['method'])
    args = call.get('args', [])
    kwargs = call.get('kwargs', {})
    result = method(*args, **kwargs)
    # If the result is a sequence, we return just the first item
    if hasattr(result, '__iter__'):
        result = list(result)[0]

    if output_attribute is not None:
        return getattr(result, output_attribute)
    elif output_key is not None:
        return result.get(output_key)
    else:
        return result
