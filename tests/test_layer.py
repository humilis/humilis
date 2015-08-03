#!/usr/bin/env python
# -*- coding: utf-8 -*-


import pytest
import os
from humilis.layer import Layer
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
def humilis_testkey(ec2):
    # Create a keypair used for testing purposes
    created = ec2.create_key_pair(config.test_key)
    yield config.test_key
    if created:
        ec2.delete_key_pair(config.test_key)


@pytest.yield_fixture(scope="module")
def humilis_example_environment():
    yield os.path.join('examples', 'example-environment.yml')


@pytest.yield_fixture(scope="module")
def humilis_environment(humilis_example_environment):
    yield Environment(humilis_example_environment)


@pytest.yield_fixture(scope="module")
def humilis_vpc_layer(cf, humilis_environment):
    layer = Layer(humilis_environment, 'vpc')
    yield layer
    cf.delete_stack(layer.name)


@pytest.yield_fixture(scope="module")
def humilis_instance_layer(cf, humilis_environment, humilis_testkey):
    layer = Layer(humilis_environment, 'instance', keyname=humilis_testkey)
    yield layer
    cf.delete_stack(layer.name)


def test_create_layer_object(humilis_environment, humilis_vpc_layer):
    layer = humilis_vpc_layer
    assert layer.relname == 'vpc'
    assert layer.name == "{}-vpc".format(humilis_environment.name)
    assert len(layer.yaml_params) == 2
    assert layer.yaml_params['vpc_cidr']['value'] == '10.0.0.0/16'
    assert layer.tags.get('humilis-layer') == layer.name
    assert layer.tags.get('humilis-environment') == humilis_environment.name


def test_layer_not_already_in_aws(humilis_vpc_layer):
    layer = humilis_vpc_layer
    assert not layer.already_in_cf


def test_get_section_files(humilis_vpc_layer):
    assert len(humilis_vpc_layer.get_section_files('resources')) == 2
    assert len(humilis_vpc_layer.get_section_files('meta')) == 1
    assert len(humilis_vpc_layer.get_section_files('invalid')) == 0


def test_load_section(humilis_vpc_layer):
    files = humilis_vpc_layer.get_section_files('resources')
    data = humilis_vpc_layer.load_section('resources', files)
    assert all(res in data for res in ['AttachGateway', 'Subnet'])


def test_compile_template(humilis_vpc_layer):
    cf_template = humilis_vpc_layer.compile()
    assert 'VPC' in cf_template['Resources'] and \
           'InternetGateway' in cf_template['Resources'] and \
           'Description' in cf_template and \
           len(cf_template['Description']) > 0


def test_create_and_delete_stack(cf, humilis_vpc_layer):
    """Creates a sample stack in CF"""
    # Make sure the stack wasn't there already
    assert not cf.stack_exists(humilis_vpc_layer.name)

    # Create the stack, and make sure it has been pushed to CF
    cf_template = humilis_vpc_layer.create()
    assert isinstance(cf_template, dict)
    assert cf.stack_ok(humilis_vpc_layer.name)

    # Delete the stack
    humilis_vpc_layer.delete()
    assert not cf.stack_exists(humilis_vpc_layer.name)


def test_create_stack_lacking_dependencies(cf, humilis_instance_layer):
    """Attempts to create a stack lacking dependencies: exception"""
    assert not cf.stack_exists(humilis_instance_layer.name)
    # Should simply skip the layer since dependencies are not met
    humilis_instance_layer.create()
    assert not cf.stack_exists(humilis_instance_layer.name)


def test_create_dependant_stack(cf, humilis_vpc_layer, humilis_instance_layer):
    """Creates two stacks, the second depending on the first"""
    assert not cf.stack_exists(humilis_vpc_layer.name)
    humilis_vpc_layer.create()
    assert cf.stack_ok(humilis_vpc_layer.name)
    humilis_instance_layer.create()
    assert cf.stack_ok(humilis_instance_layer.name)
    humilis_instance_layer.delete()
    assert not cf.stack_exists(humilis_instance_layer.name)
    humilis_vpc_layer.delete()
    assert not cf.stack_exists(humilis_vpc_layer.name)