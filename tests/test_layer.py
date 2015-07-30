#!/usr/bin/env python
# -*- coding: utf-8 -*-


import pytest
import os
from humilis.layer import Layer
from humilis.environment import Environment
from humilis.cloudformation import CloudFormation
import humilis.config as config
import boto.cloudformation
import time


@pytest.yield_fixture(scope="module")
def humilis_example_environment():
    yield os.path.join('examples', 'example-environment.yml')


@pytest.yield_fixture(scope="module")
def humilis_environment(humilis_example_environment):
    yield Environment(humilis_example_environment)


@pytest.yield_fixture(scope="module")
def humilis_layer(humilis_environment, cf_connection):
    layer = Layer(humilis_environment, 'vpc')
    yield layer
    statuses = get_cf_statuses(cf_connection)
    if layer.name in statuses and \
            not statuses[layer.name].startswith('DELETE'):
        cf_connection.delete_stack(layer.name)


@pytest.yield_fixture(scope="module")
def cf_connection():
    yield boto.cloudformation.connect_to_region(
        config.region,
        aws_access_key=os.environ.get('AWS_ACCESS_KEY'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))


@pytest.yield_fixture(scope="module")
def cf_stacks(cf_connection):
    yield cf_connection.describe_stacks()


@pytest.yield_fixture(scope="function")
def newly_created_cf_stack(humilis_layer):
    yield humilis_layer.create()
    time.sleep(5)
    humilis_layer.delete()


def get_cf_statuses(cf_connection):
    conn = boto.cloudformation.connect_to_region(config.region)
    stacks = {s.stack_name: s.stack_status for s in conn.describe_stacks()}
    return stacks


def test_create_environment_object(humilis_environment):
    env = humilis_environment
    assert env.name == 'example-environment'
    assert env.region == config.region
    assert isinstance(env.cf, CloudFormation)
    assert env.tags.get('humilis-environment') == env.name


def test_create_layer_object(humilis_environment, humilis_layer):
    layer = humilis_layer
    assert layer.relname == 'vpc'
    assert layer.name == "{}-vpc".format(humilis_environment.name)
    assert len(layer.yaml_params) == 2
    assert layer.yaml_params['vpc_cidr']['value'] == '10.0.0.0/16'
    assert layer.tags.get('humilis-layer') == layer.name
    assert layer.tags.get('humilis-environment') == humilis_environment.name


def test_layer_not_already_in_aws(humilis_layer):
    layer = humilis_layer
    assert not layer.already_in_cf


def test_get_section_files(humilis_layer):
    assert len(humilis_layer.get_section_files('resources')) == 2
    assert len(humilis_layer.get_section_files('meta')) == 1
    assert len(humilis_layer.get_section_files('invalid')) == 0


def test_load_section(humilis_layer):
    files = humilis_layer.get_section_files('resources')
    data = humilis_layer.load_section('resources', files)
    assert all(res in data for res in ['AttachGateway', 'Subnet'])


def test_compile_template(humilis_layer):
    cf_template = humilis_layer.compile()
    assert 'VPC' in cf_template['Resources'] and \
           'InternetGateway' in cf_template['Resources'] and \
           'Description' in cf_template and \
           len(cf_template['Description']) > 0


def test_create_and_delete_stack(humilis_layer):
    """Creates a sample stack in CF"""
    # Make sure the stack wasn't there already
    statuses = get_cf_statuses(cf_connection)
    assert humilis_layer.name not in statuses

    # Create the stack, and make sure it has been pushed to CF
    cf_template = humilis_layer.create()
    assert isinstance(cf_template, dict)
    time.sleep(2)
    statuses = get_cf_statuses(cf_connection)
    assert humilis_layer.name in statuses

    # Delete the stack
    humilis_layer.delete()
    time.sleep(2)
    statuses = get_cf_statuses(cf_connection)
    assert humilis_layer.name not in statuses or \
        statuses[humilis_layer.name].startswith('DELETE')
