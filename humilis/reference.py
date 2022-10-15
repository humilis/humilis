"""Built-in reference parsers."""

import contextlib
import os
import importlib
import shutil
import subprocess
import sys
import tempfile
import uuid
from zipfile import ZipFile

import boto3facade
from boto3facade.s3 import S3
from boto3facade.cloudformation import Cloudformation
import jinja2
from s3keyring.s3 import S3Keyring

from humilis.exceptions import ReferenceError, InvalidLambdaDependencyError
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


def secret(layer, config, service=None, key=None, group=None, kms_key_id=None):
    """Retrieves a secret stored in a S3 keyring.

    :param service: An alias of group, for backwards compatibility
    :param key: The key used to identify the secret within the server
    :param group: The name of the group of secrets
    :param kms_key_id: The ID of the KMS Key to encrypt the secret

    :returns: The plaintext or encrypted secret
    """
    if not group:
        group = service

    s3keyring_config = os.path.join(layer.env_basedir, ".s3keyring.ini")
    if os.path.isfile(s3keyring_config):
        kr = S3Keyring(config_file=s3keyring_config)
    else:
        kr = S3Keyring()

    secret = kr.get_password(group, key)
    if kms_key_id:
        return boto3.client('kms').encrypt(KeyId=kms_key_id, Plaintext=secret)
    return secret


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
    if layer.type == "sam":
        return os.path.join("s3://", s3bucket, s3key)
    else:
        return {'s3bucket': s3bucket, 's3key': s3key}


def lambda_ref(layer, config, path=None, dependencies=None, **params):
    """Prepares a lambda deployment package and uploads it to S3.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param path: Path to the file, relative to the location of meta.yaml.
    :param dependencies: A list of Python dependencies.

    :returns: S3 path where the deployment package has been uploaded.
    """
    fpath = os.path.abspath(os.path.join(layer.basedir, path))
    logger = layer.logger
    if os.path.isdir(fpath):
        with _deploy_package(fpath, layer, logger, dependencies, params) as fpath:
            s3path = file(layer, config, fpath)
    else:
        path_no_ext, ext = os.path.splitext(fpath)
        if ext == '.zip':
            s3path = file(layer, config, fpath)
        else:
            with _simple_deploy_package(fpath, layer, logger, params) as fpath:
                s3path = file(layer, config, fpath)

    return s3path


def _install_dependencies(layer, path, dependencies):
    """Install Python dependencies under the given path."""
    for dep in dependencies:
        deppath = os.path.abspath(os.path.join(layer.env_basedir, dep))
        targetpath = os.path.join(path, os.path.basename(dep))
        if os.path.isfile(deppath):
            ext = os.path.splitext(dep)[1]
            if ext == ".py":
                # A self-contained Python module
                shutil.copyfile(deppath, targetpath)
            elif ext == ".txt":
                # A requirements file
                subprocess.check_call([sys.executable, '-m', 'pip',
                                       'install', '-r', deppath, '-t', path])
            else:
                raise InvalidLambdaDependencyError(dep)
        elif os.path.isdir(deppath):
            if os.path.isfile(os.path.join(deppath, "setup.py")):
                # A local pip installable
                subprocess.check_call([sys.executable, '-m', 'pip',
                                       'install', deppath, '-t', path])
            else:
                # A self-contained Python package
                shutil.copytree(deppath, targetpath)
        else:
            if dep.find("git+") >= 0:
                # A git repo
                subprocess.check_call([sys.executable, '-m', 'pip',
                                       'install', '-e', dep, '-t', path])
            elif dep.find(":") < 0:
                # A Pypi package
                subprocess.check_call([sys.executable, '-m', 'pip',
                                       'install', dep, '-t', path, '--upgrade'])
            else:
                # A private index package
                index = ":".join(dep.split(":")[:-1])
                subprocess.check_call([
                    sys.executable, '-m', 'pip',
                    'install', '-i', index, dep, '-t', path, '--upgrade'])


@contextlib.contextmanager
def _deploy_package(path, layer, logger, dependencies, params):
    """Creates a deployment package for multi-file lambda with deps."""
    with utils.move_aside(path) as tmppath:
        # removes __* and .* dirs
        _cleanup_dir(tmppath)
        # render Jinja2 templated files
        template_params = layer.loader_params
        template_params.update(params)
        _preprocess_dir(tmppath, template_params)
        setup_file = os.path.join(tmppath, 'setup.py')
        if os.path.isfile(setup_file):
            # Install all depedendencies in the same dir
            subprocess.check_call([sys.executable, '-m', 'pip',
                                   'install', tmppath, '-t', tmppath])
        requirements_file = os.path.join(tmppath, 'requirements.txt')
        if os.path.isfile(requirements_file):
            subprocess.check_call([
                sys.executable, '-m', 'pip',
                'install', '-r', requirements_file, '-t', tmppath])

        if dependencies:
            _install_dependencies(layer, tmppath, dependencies)

        suffix = str(uuid.uuid4())
        tmpdir = tempfile.mkdtemp()
        basename = os.path.basename(path)
        zipfile = os.path.join(tmpdir, "{}{}{}".format(basename, suffix,
                                                       '.zip'))
        with ZipFile(zipfile, 'w') as myzip:
            utils.zipdir(tmppath, myzip)
        yield zipfile
        shutil.rmtree(tmpdir)


def _cleanup_dir(path):
    """Removes __* and .* dirs."""
    to_remove = []
    for root, dirs, files in os.walk(path):
        for dirpath in dirs:
            if dirpath.startswith('__') or dirpath.startswith('.'):
                to_remove.append(os.path.join(root, dirpath))
    for dirpath in to_remove:
        shutil.rmtree(dirpath, ignore_errors=True)


@contextlib.contextmanager
def _simple_deploy_package(path, layer, logger, params):
    """Creates a deployment package for a one-file no-deps lambda."""
    logger.info("Creating deployment package for '{}'".format(path))
    with utils.move_aside(path) as tmppath:
        template_params = layer.loader_params
        template_params.update(params)
        _preprocess_file(tmppath, template_params)
        path_no_ext, ext = os.path.splitext(tmppath)
        basename = os.path.basename(path_no_ext)
        gc = _git_head()
        suffix = ('-' + gc, '')[gc is None]
        tmpdir = tempfile.mkdtemp()
        zipfile = os.path.join(tmpdir,
                               "{}{}{}".format(basename, suffix, '.zip'))
        with ZipFile(zipfile, 'w') as myzip:
            myzip.write(tmppath, arcname=basename + ext)
        yield zipfile
        shutil.rmtree(tmpdir)


def _is_jinja2_template(path):
    """Returns true if a file contains a jinja2 template."""
    _, ext = os.path.splitext(path)
    if ext in {'.pyc'}:
        return False

    result = False
    with open(path, 'r') as f:
        for line in f:
            if line.startswith('#') and line.find('preprocessor:jinja2'):
                result = True
                break
    return result


def _preprocess_file(path, params):
    """Render in place a jinja2 template."""
    if not _is_jinja2_template(path):
        return
    basedir, filename = os.path.split(path)
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(basedir))
    # Add custom functions and filters
    utils.update_jinja2_env(env)
    result = env.get_template(filename).render(params)
    with open(path, 'w') as f:
        f.write(result)


def _preprocess_dir(path, params):
    """Preprocesses all files in a directory using Jinja2."""
    for root, dirs, files in os.walk(path):
        for file in files:
            filepath = os.path.join(root, file)
            _preprocess_file(filepath, params)


def layer(layer, config, layer_name=None, resource_name=None,
          output_name=None):
    """Gets the physical ID of a resource in an already deployed layer.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param layer_name: The name of the layer that contains the target resource.
    :param resource_name: The logical name of the target resource.
    :param output_name: The name of the layer output.

    :returns: The physical ID of the resource.
    """
    if not (resource_name or output_name) or (resource_name and output_name):
        raise ValueError(
            "Exactly one of these two parameters should be provider: either"
            "'resource_name' or 'output_name'")

    if resource_name:
        stack_name = utils.get_cf_name(layer.env_name, layer_name,
                                       stage=layer.env_stage)
        return _get_stack_resource(layer, config, stack_name, resource_name)
    else:
        return output(layer, config, layer_name=layer_name,
                      output_name=output_name)



def environment(layer, config, environment_name=None, stage=None,
                layer_name=None, resource_name=None, output_name=None):
    """Gets the physical ID of a resource in another environment.

    :param layer: The Layer object of the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param layer_name: The name of the layer that contains the target resource.
    :param resource_name: The logical name of the target resource.
    :param output_name: The name of the layer output

    :returns: The physical ID of the resource.
    """

    if not (resource_name or output_name) or (resource_name and output_name):
        raise ValueError(
            "Exactly one of these two parameters should be provider: either"
            "'resource_name' or 'output_name'")
    if resource_name:
        stack_name = utils.get_cf_name(environment_name, layer_name, stage=stage)
        return _get_stack_resource(layer, config, stack_name, resource_name)
    else:
        return output(
            layer, config, layer_name=layer_name, stage=stage,
            environment_name=environment_name, output_name=output_name)



def _get_stack_resource(layer, config, stack_name, resource_name):
    """Gets the physical ID of a resource in a CF Stack.

    :param stack_name: The name of the CF stack.
    :param resource_name: The logical name of the CF resource.

    :returns: The physical ID of the resource.
    """
    cf = Cloudformation(config)
    resource = cf.get_stack_resource(stack_name, resource_name)

    if len(resource) < 1:
        all_stack_resources = [x.logical_resource_id for x
                               in cf.get_stack_resources(stack_name)]
        msg = "{} does not exist in stack {} (with resources {}).".format(
            resource_name, stack_name, all_stack_resources)
        raise ReferenceError(resource_name, msg, logger=layer.logger)

    return resource[0].physical_resource_id


def output(layer, config, layer_name=None, output_name=None,
           environment_name=None, stage=None):
    """Gets the value of an output produced by an already deployed layer.

    :param layer: The Layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param layer_name: The logical name of the layer that produced the output.
    :param output_name: The logical name of the output parameter.
    """
    if not environment_name:
        environment_name = layer.env_name

    if not stage:
        stage = layer.env_stage

    stack_name = utils.get_cf_name(environment_name, layer_name, stage=stage)
    cf = Cloudformation(config)
    try:
        output = cf.get_stack_output(stack_name, output_name)
    except AttributeError:
        msg = "No output '{}' in CF stack '{}'".format(output_name, stack_name)
        ref = "output/{}/{}/{}/{}".format(environment_name, layer_name, stage,
                                          output_name)
        raise ReferenceError(ref, msg)
    if len(output) < 1:
        all_stack_outputs = [x['OutputKey'] for x
                             in cf.stack_outputs[stack_name]]
        msg = ("{} output does not exist for stack {} "
               "(with outputs {}).").format(output_name,
                                            stack_name,
                                            all_stack_outputs)
        ref = "output ({}/{})".format(layer_name, output_name)
        raise ReferenceError(ref, msg, logger=layer.logger)
    return output[0]


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
    if not isinstance(result, str) and not isinstance(result, dict) and \
        hasattr(result, '__iter__'):
            # Convert iterables to lists
            result = list(result)
    if isinstance(result, list):
        if len(result) == 1:
            result = result[0]
        else:
            raise ReferenceError("boto3/{}/{}".format(service, call),
                "Must produce exactly one result but {} were produced".format(
                len(result)))

    if output_attribute is not None:
        result = getattr(result, output_attribute)
    if output_key is not None:
        return result.get(output_key)
    else:
        return result


def j2_template(layer, config, path=None, s3_upload=False, params=None):
    """Render a j2 template and return the local or s3 path of the result.

    :param layer: The layer object for the layer declaring the reference.
    :param config: An object holding humilis configuration options.
    :param path: The path of the j2 template to render. Relative to meta.yml.
    :param s3_upload: Upload the rendered template to s3 or not.
    :param params: A dict containing the values to render the template.

    :returns: The local or s3 path of the rendered template.
    """
    if params is None:
        msg = ("Missing params for j2 rendering in layer '{}' "
               "and env '{}'").format(layer.name, layer.env_name)
        ref = "j2_template '{}')".format(path)
        raise ReferenceError(ref, msg, logger=layer.logger)
    basefile, j2_ext = os.path.splitext(path)
    if j2_ext not in {".j2"}:
        msg = ("The file is not a Jinja2 template. layer : '{}', "
               "env : '{}'".format(layer.name, layer.env_name))
        ref = "j2_template '{}')".format(path)
        raise ReferenceError(ref, msg, logger=layer.logger)

    _, ext = os.path.splitext(basefile)
    _, filename = os.path.split(path)
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(layer.basedir))
    result = env.get_template(filename).render(params)
    output_path = os.path.join(layer.env_basedir, "ref-j2_template_" +
                               str(uuid.uuid4()) + ext)
    with open(output_path, "w") as f:
        f.write(result)
    if s3_upload:
        s3bucket, s3key = _get_s3path(layer, config, output_path)
        s3 = S3(config)
        s3.cp(output_path, s3bucket, s3key)
        layer.logger.info("{} -> {}/{}".format(output_path, s3bucket, s3key))
        return os.path.join("s3://", s3bucket, s3key)

    return output_path
