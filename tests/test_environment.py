#!/usr/bin/env python
# -*- coding: utf-8 -*-


import pytest
import os
from humilis.environment import Environment
from humilis.cloudformation import CloudFormation
from humilis.ec2 import EC2
import humilis.config as config


@pytest.yield_fixture(scope="module")
def cf():
    yield CloudFormation()


@pytest.yield_fixture(scope="module")
def ec2():
    yield EC2()


@pytest.yield_fixture(scope="module")
def humilis_example_environment():
    yield os.path.join('examples', 'example-environment.yml')


@pytest.yield_fixture(scope="module")
def humilis_environment(humilis_example_environment):
    env = Environment(humilis_example_environment)
    yield env
    for layer in env.layers:
        cf.delete_stack(layer.name)


def test_create_environment_object(humilis_environment):
    env = humilis_environment
    assert env.name == 'example-environment'
    assert env.region == config.region
    assert isinstance(env.cf, CloudFormation)
    assert env.tags.get('humilis-environment') == env.name
