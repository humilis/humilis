"""Tests fixtures shared across test modules."""

import os

import pytest
import uuid
from boto3facade.cloudformation import Cloudformation
from boto3facade.ec2 import Ec2

from humilis.config import config
from humilis.environment import Environment


@pytest.fixture(scope="session")
def test_config():
    config.boto_config.activate_profile("test")


@pytest.fixture(scope="session")
def randomstr():
    """Produces a random string (an UUID4)."""
    return str(uuid.uuid4())


@pytest.yield_fixture(scope="session")
def cf():
    """Create a Cloudformation facade object"""
    yield Cloudformation(config.boto_config)


@pytest.yield_fixture(scope="session")
def ec2():
    """Create an Ec2 facade object."""
    yield Ec2(config.boto_config)


@pytest.yield_fixture(scope="session")
def test_keypair(ec2, randomstr):
    """ Create a temporary keypair in AWS."""
    key_name = "humilis-testkey-{}".format(randomstr)
    created = ec2.create_key_pair(key_name)
    yield key_name
    if created:
        ec2.delete_key_pair(key_name)


@pytest.yield_fixture(scope="session")
def environment_definition_path():
    """Path to a sample environment definition yaml file."""
    yield os.path.join('examples', 'example-environment.yml')


@pytest.yield_fixture(scope="session")
def environment_definition_j2_path():
    """Path to a sample environment parameters file."""
    yield os.path.join('examples', 'example-environment.yml.j2')


@pytest.yield_fixture(scope="session")
def environment_params_path():
    """Path to a sample environment definition yaml.j2 file."""
    yield os.path.join('examples', 'parameters.yaml')


@pytest.fixture(scope="module")
def test_environment(environment_definition_path, test_config):
    """A humilis environment based on the sample environment definition."""
    return Environment(environment_definition_path)


@pytest.fixture(scope="module")
def test_vpc_layer(cf, test_environment):
    """The VPC layer from the sample environment."""
    return [l for l in test_environment.layers if l.name == 'vpc'][0]
