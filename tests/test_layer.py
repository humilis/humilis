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
def humilis_vpc_layer(humilis_environment, cf_connection):
    layer = Layer(humilis_environment, 'vpc')
    yield layer
    delete_layer(cf_connection, layer)


@pytest.yield_fixture(scope="module")
def humilis_instance_layer(humilis_environment, cf_connection):
    layer = Layer(humilis_environment, 'instance')
    yield layer
    delete_layer(cf_connection, layer)


@pytest.yield_fixture(scope="module")
def cf_connection():
    yield boto.cloudformation.connect_to_region(
        config.region,
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))


@pytest.yield_fixture(scope="module")
def cf_stacks(cf_connection):
    yield cf_connection.describe_stacks()


@pytest.yield_fixture(scope="function")
def newly_created_cf_stack(humilis_vpc_layer):
    yield humilis_vpc_layer.create()
    time.sleep(5)
    humilis_vpc_layer.delete()


def get_cf_statuses(cf_connection):
    conn = boto.cloudformation.connect_to_region(config.region)
    stacks = {s.stack_name: s.stack_status for s in conn.describe_stacks()}
    return stacks


def delete_layer(cfc, layer):
    statuses = get_cf_statuses(cfc)
    if layer.name in statuses and \
            not statuses[layer.name].startswith('DELETE'):
        cfc.delete_stack(layer.name)


def wait_for_status_change(cfc, layer, status, nb_seconds=2):
    counter = 0
    curr_status = status
    time.sleep(1)
    while curr_status and curr_status == status:
        time.sleep(1)
        counter += 1
        statuses = get_cf_statuses(cfc)
        curr_status = statuses.get(layer.name)
        if counter >= nb_seconds:
            break


def test_create_environment_object(humilis_environment):
    env = humilis_environment
    assert env.name == 'example-environment'
    assert env.region == config.region
    assert isinstance(env.cf, CloudFormation)
    assert env.tags.get('humilis-environment') == env.name


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


def test_create_and_delete_stack(humilis_vpc_layer):
    """Creates a sample stack in CF"""
    # Make sure the stack wasn't there already
    statuses = get_cf_statuses(cf_connection)
    assert humilis_vpc_layer.name not in statuses

    # Create the stack, and make sure it has been pushed to CF
    cf_template = humilis_vpc_layer.create()
    assert isinstance(cf_template, dict)
    time.sleep(2)
    statuses = get_cf_statuses(cf_connection)
    assert humilis_vpc_layer.name in statuses

    # Delete the stack
    humilis_vpc_layer.delete()
    wait_for_status_change(cf_connection, humilis_vpc_layer,
                           'DELETE_IN_PROGRESS', 40)
    statuses = get_cf_statuses(cf_connection)
    assert humilis_vpc_layer.name not in statuses


def test_create_stack_lacking_dependencies(humilis_instance_layer):
    """Attempts to create a stack lacking dependencies: exception"""
    statuses = get_cf_statuses(cf_connection)
    assert humilis_instance_layer.name not in statuses
    # Should simply skip the layer since dependencies are not met
    humilis_instance_layer.create()
    time.sleep(2)
    statuses = get_cf_statuses(cf_connection)
    assert humilis_instance_layer.name not in statuses


def test_create_dependant_stack(humilis_vpc_layer, humilis_instance_layer):
    """Creates two stacks, the second depending on the first"""
    statuses = get_cf_statuses(cf_connection)
    assert humilis_vpc_layer.name not in statuses
    wait_for_status_change(cf_connection, humilis_vpc_layer,
                           'CREATE_IN_PROGRESS')
