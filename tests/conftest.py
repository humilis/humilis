#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests fixtures shared across test modules."""

import os

import pytest
import uuid
from boto3facade.cloudformation import Cloudformation
from boto3facade.ec2 import Ec2

from humilis.config import config
from humilis.environment import Environment
from humilis.layer import Layer


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


@pytest.yield_fixture(scope="module")
def test_environment(environment_definition_path, test_config):
    """A humilis environment based on the sample environment definition."""
    env = Environment(environment_definition_path)
    yield env
    env.delete()


@pytest.yield_fixture(scope="module")
def test_vpc_layer(cf, test_environment):
    """The VPC layer from the sample environment."""
    layer = [l for l in test_environment.layers if l.name == 'vpc'][0]
    yield layer
    cf.delete_stack(layer.name)


@pytest.yield_fixture(scope="module")
def test_streams_layer(cf, test_environment):
    """The Streams layer from the sample environment"""
    layer = Layer(test_environment, 'streams')
    yield layer
    cf.delete_stack(layer.cf_name)


@pytest.yield_fixture(scope="module")
def test_streams_roles_layer(cf, test_environment):
    """The streams-roles layer from the sample environment"""
    layer = Layer(test_environment, 'streams-roles')
    yield layer
    cf.delete_stack(layer.cf_name)


@pytest.yield_fixture(scope="module")
def test_instance_layer(cf, test_environment, test_keypair):
    layer = Layer(test_environment, 'instance', keyname=test_keypair)
    yield layer
    cf.delete_stack(layer.cf_name)


@pytest.yield_fixture(scope="module")
def test_named_instance_layer(cf, test_environment, test_keypair):
    layer = Layer(test_environment, 'namedinstance',
                  keyname=test_keypair)
    yield layer
    cf.delete_stack(layer.cf_name)


@pytest.yield_fixture(scope='function')
def test_roles_layer(cf, test_environment):
    layer = Layer(test_environment, 'lambda-role')
    yield layer
    cf.delete_stack(layer.cf_name)


@pytest.yield_fixture(scope='function')
def test_lambda_template_layer(cf, test_environment):
    layer = Layer(test_environment, 'lambda-template')
    yield layer
    cf.delete_stack(layer.cf_name)


@pytest.yield_fixture(scope='function')
def test_lambda_template_2_layer(cf, test_environment):
    layer = Layer(test_environment, 'lambda-template-2')
    yield layer
    cf.delete_stack(layer.cf_name)
