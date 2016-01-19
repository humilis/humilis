# -*- coding: utf-8 -*-

"""Built-in reference parsers."""


import contextlib
import os
import importlib
import pip
import subprocess
from subprocess import CalledProcessError
import tempfile
import shutil
from zipfile import ZipFile

import boto3facade
from boto3facade.s3 import S3
from boto3facade.cloudformation import Cloudformation

from humilis.exceptions import ReferenceError
import humilis.utils as utils


def _get_s3path(layer, config, full_path):
    """Returns the S3 target (bucket, key) for a local file."""
    env_prefix = "{base_prefix}{env_name}/".format(
        base_prefix=config.profile.get('s3prefix', ''),
        env_name=layer.env_name)
    if layer.env_stage is not None:
        env_prefix = "{}{}/".format(env_prefix, layer.env_stage)

    s3key = "{env_prefix}{layer_name}/{file_name}".format(
        env_prefix=env_prefix,
        layer_name=layer.name,
        file_name=os.path.basename(full_path))
    s3bucket = config.profile.get('bucket')
    return (s3bucket, s3key)


def _add_git_commit(basename):
    """Adds the git commit hash to a filename."""
    try:
        c = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode()
        c = c.rstrip()
    except CalledProcessError as err:
        if err.find('Not a git repository') > -1:
            # Lambda not under version control, very bad!
            c = None
        raise

    if c:
        basename = "{}-{}".format(basename, c)
    return basename


@utils.reference_parser()
def file(layer, config, path=None):
    """Uploads a local file to S3 and returns the corresponding S3 path.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param path: Path to the file, relative to the location of meta.yaml.

    :returns: The S3 path where the file has been uploaded.
    """
    full_path = os.path.join(layer.basedir, path)
    s3bucket, s3key = _get_s3path(layer, config, full_path)
    s3 = S3(config)
    s3.cp(full_path, s3bucket, s3key)
    layer.logger.info("{} -> {}/{}".format(full_path, s3bucket, s3key))
    return {'s3bucket': s3bucket, 's3key': s3key}


@utils.reference_parser(name='lambda')
def lambda_ref(layer, config, path=None):
    """Prepares a lambda deployment package and uploads it to S3.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param path: Path to the file, relative to the location of meta.yaml.

    :returns: S3 path where the deployment package has been uploaded.
    """
    full_path = os.path.abspath(os.path.join(layer.basedir, path))
    logger = layer.logger
    if os.path.isdir(full_path):
        with _make_deploy_package(full_path, logger) as full_path:
            s3path = file(layer, config, full_path)
    else:
        path_no_ext, ext = os.path.splitext(full_path)
        if ext == '.zip':
            s3path = file(layer, config, full_path)
        else:
            with _make_simple_deploy_package(full_path, logger) as full_path:
                s3path = file(layer, config, full_path)

    return s3path


@contextlib.contextmanager
def _make_deploy_package(full_path, logger):
    """Creates a deployment package for multi-file lambda with deps."""
    tmpdir = tempfile.mkdtemp()
    basename = os.path.basename(full_path)
    targetdir = os.path.join(tmpdir, basename)
    shutil.copytree(full_path, targetdir, symlinks=True)
    setup_file = os.path.join(targetdir, 'setup.py')
    if os.path.isfile(setup_file):
        # Install all depedendencies in the same dir
        pip.main(['install', targetdir, '-t', targetdir])

    # Adding the commit hash to the file name will force different commits to
    # be associated to different s3 paths. This way CF update will detect that
    # the template has changed.
    basename = _add_git_commit(basename)
    zipfile = os.path.join(tmpdir, basename + '.zip')
    with ZipFile(zipfile, 'w') as myzip:
        utils.zipdir(targetdir, myzip)
    yield zipfile
    shutil.rmtree(tmpdir)


@contextlib.contextmanager
def _make_simple_deploy_package(full_path, logger):
    """Creates a deployment package for a one-file no-deps lambda."""
    logger.info("Creating deployment package for '{}'".format(full_path))
    tmpdir = tempfile.mkdtemp()
    path_no_ext, ext = os.path.splitext(full_path)
    basename = os.path.basename(path_no_ext)
    basename = _add_git_commit(basename)
    zipfile = os.path.join(tmpdir, basename + '.zip')
    with ZipFile(zipfile, 'w') as myzip:
        myzip.write(full_path)
    yield zipfile
    shutil.rmtree(tmpdir)


@utils.reference_parser()
def layer(layer, config, layer_name=None, resource_name=None):
    """Gets the physical ID of a resource in an already deployed layer.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param layer_name: The name of the layer that contains the target resource.
    :param resource_name: The logical name of the target resource.

    :returns: The physical ID of the resource
    """
    stack_name = utils.get_cf_name(layer.env_name, layer_name,
                                   stage=layer.env_stage)
    cf = Cloudformation(config)
    resource = cf.get_stack_resource(stack_name, resource_name)

    if len(resource) < 1:
        all_stack_resources = [x.logical_resource_id for x
                               in cf.get_stack_resources(stack_name)]
        msg = "{} does not exist in stack {} (with resources {}).".format(
            resource_name, stack_name, all_stack_resources)
        raise ReferenceError(resource_name, msg, logger=layer.logger)

    return resource[0].physical_resource_id


@utils.reference_parser()
def output(layer, config, layer_name=None, output_name=None):
    """Gets the value of an output produced by an already deployed layer.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param layer_name: The logical name of the layer that produced the output.
    :param output_name: The logical name of the output parameter.
    """
    stack_name = utils.get_cf_name(layer.env_name, layer_name,
                                   stage=layer.env_stage)
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


@utils.reference_parser()
def boto3(layer, config, service=None, call=None, output_attribute=None,
          output_key=None):
    """Calls a boto3facade method.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param service: The name of the AWS service.
    :param call: A dict with two keys: method, and parameters.
    :param output_attribute: Object attribute to return.
    :param output_key: Dictionary key to return.

    :returns: The call response, or its corresp. attribute or key.
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
