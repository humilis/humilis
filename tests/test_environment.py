#!/usr/bin/env python
# -*- coding: utf-8 -*-


import pytest
import os
from humilis.environment import Environment
from humilis.cloudformation import CloudFormation
from boto3facade.ec2 import Ec2
import humilis.config as config


@pytest.yield_fixture(scope="module")
def cf():
    yield CloudFormation()


@pytest.yield_fixture(scope="module")
def ec2():
    yield Ec2()


@pytest.yield_fixture(scope="module")
def humilis_example_environment():
    yield os.path.join('examples', 'example-environment.yml')


@pytest.yield_fixture(scope="module")
def humilis_testkey(ec2):
    # Create a keypair used for testing purposes
    created = ec2.create_key_pair(config.test_key)
    yield config.test_key
    if created:
        ec2.delete_key_pair(config.test_key)


@pytest.yield_fixture(scope="module")
def humilis_environment(cf, humilis_example_environment, humilis_testkey):
    env = Environment(humilis_example_environment)
    yield env
    for layer in reversed(env.layers):
        cf.delete_stack(layer.name)


def test_create_environment_object(humilis_environment):
    """Creates an Environment objects and queries its properties"""
    env = humilis_environment
    assert env.name == 'example-environment'
    assert isinstance(env.cf, CloudFormation)
    assert env.tags.get('humilis-environment') == env.name


def test_environment_not_already_in_aws(humilis_environment):
    """Ensures tha the test environment is not already in CF"""
    assert not humilis_environment.already_in_cf


def test_create_environment(humilis_environment):
    """Creates a test environment in CF"""
    humilis_environment.create()
    assert humilis_environment.already_in_cf
