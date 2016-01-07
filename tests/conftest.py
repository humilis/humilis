#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests fixtures shared across test modules."""

import pytest
import humilis.config as config
import os
from humilis.cloudformation import CloudFormation
from boto3facade.ec2 import Ec2
from humilis.environment import Environment
from humilis.layer import Layer


@pytest.yield_fixture(scope="session")
def cf():
    """Create a Cloudformation facade object"""
    yield CloudFormation()


@pytest.yield_fixture(scope="session")
def ec2():
    """Create an Ec2 facade object."""
    yield Ec2()


@pytest.yield_fixture(scope="session")
def test_keypair(ec2):
    """ Create a temporary keypair in AWS."""
    created = ec2.create_key_pair(config.test_key)
    yield config.test_key
    if created:
        ec2.delete_key_pair(config.test_key)


@pytest.yield_fixture(scope="module")
def environment_definition_path():
    """Path to a sample environment definition yaml file."""
    yield os.path.join('examples', 'example-environment.yml')


@pytest.yield_fixture(scope="module")
def test_environment(environment_definition_path):
    """A humilis environment based on the sample environment definition."""
    yield Environment(environment_definition_path)


@pytest.yield_fixture(scope="module")
def test_vpc_layer(cf, test_environment):
    """The VPC layer from the sample environment."""
    layer = Layer(test_environment, 'vpc')
    yield layer
    cf.delete_stack(layer.name)


@pytest.yield_fixture(scope="module")
def test_streams_layer(cf, test_environment):
    """The Streams layer from the sample environment"""
    layer = Layer(test_environment, 'streams-roles')
    yield layer
    cf.delete_stack(layer.name)


@pytest.yield_fixture(scope="module")
def test_streams_roles_layer(cf, test_environment):
    """The streams-roles layer from the sample environment"""
    layer = Layer(test_environment, 'streams')
    yield layer
    cf.delete_stack(layer.name)


@pytest.yield_fixture(scope="module")
def test_instance_layer(cf, test_environment, test_keypair):
    layer = Layer(test_environment, 'instance', keyname=test_keypair)
    yield layer
    cf.delete_stack(layer.name)


@pytest.yield_fixture(scope="module")
def test_named_instance_layer(cf, test_environment, test_keypair):
    layer = Layer(test_environment, 'namedinstance',
                  keyname=test_keypair)
    yield layer
    cf.delete_stack(layer.name)


@pytest.yield_fixture(scope='function')
def test_roles_layer(cf, test_environment):
    layer = Layer(test_environment, 'lambda-role')
    yield layer
    cf.delete_stack(layer.name)
