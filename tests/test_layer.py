#!/usr/bin/env python
# -*- coding: utf-8 -*-


import pytest

import humilis.utils as utils
from humilis.exceptions import CloudformationError


def test_create_layer_object(test_environment, test_vpc_layer):
    layer = test_vpc_layer
    assert layer.name == 'vpc'
    assert layer.cf_name == utils.get_cf_name(
        layer.env_name,
        layer.name,
        stage=layer.env_stage)
    assert len(layer.yaml_params) == 2
    assert layer.yaml_params['vpc_cidr']['value'] == '10.0.0.0/16'
    assert layer.tags.get('humilis-layer') == layer.name
    assert layer.tags.get('humilis-environment') == test_environment.name


def test_get_section_files(test_vpc_layer):
    assert len(test_vpc_layer.loader.get_section_files('resources')) == 2
    assert len(test_vpc_layer.loader.get_section_files('meta')) == 1
    assert len(test_vpc_layer.loader.get_section_files('invalid')) == 0


def test_create_and_delete_layer(cf, test_roles_layer):
    # Make sure the stack wasn't there already
    assert not cf.stack_exists(test_roles_layer.cf_name)

    # Create the stack, and make sure it has been pushed to CF
    cf_template = test_roles_layer.create()
    assert isinstance(cf_template, dict)
    assert cf.stack_ok(test_roles_layer.cf_name)

    # Delete the stack
    test_roles_layer.delete()
    assert not cf.stack_exists(test_roles_layer.cf_name)


def test_load_section(test_vpc_layer):
    files = test_vpc_layer.loader.get_section_files('resources')
    data = test_vpc_layer.loader.load_section('resources', files)
    assert all(res in data for res in ['AttachGateway', 'Subnet'])


def test_compile_template(test_vpc_layer):
    cf_template = test_vpc_layer.compile()
    assert 'VPC' in cf_template['Resources'] and \
           'InternetGateway' in cf_template['Resources'] and \
           'Description' in cf_template and \
           len(cf_template['Description']) > 0


def test_create_layer_lacking_dependencies(cf, test_streams_roles_layer,
                                           test_streams_layer):
    """Attempts to create a stack lacking dependencies: exception"""
    test_streams_layer.delete()
    assert not cf.stack_exists(test_streams_roles_layer.cf_name)
    assert not cf.stack_exists(test_streams_layer.cf_name)
    # Should simply skip the layer since dependencies are not met
    test_streams_roles_layer.create()
    assert not cf.stack_exists(test_streams_roles_layer.cf_name)


def test_create_layer_absent_section_dirs(cf, test_streams_layer):
    """Attempts to create a layer without section directories"""
    test_streams_layer.create()
    assert cf.stack_exists(test_streams_layer.cf_name)


def test_create_dependant_layer(cf, test_vpc_layer, test_instance_layer):
    """Creates two stacks, the second depending on the first"""
    test_vpc_layer.create()
    assert cf.stack_ok(test_vpc_layer.cf_name)
    test_instance_layer.create()
    assert cf.stack_ok(test_instance_layer.cf_name)
    test_instance_layer.delete()
    assert not cf.stack_exists(test_instance_layer.cf_name)
    test_vpc_layer.delete()
    assert not cf.stack_exists(test_vpc_layer.cf_name)


def test_create_namedinstance_stack(cf, test_vpc_layer,
                                    test_named_instance_layer):
    """Referring to AMIs using their tags"""
    test_vpc_layer.create()
    assert cf.stack_ok(test_vpc_layer.cf_name)
    test_named_instance_layer.create()
    assert cf.stack_ok(test_named_instance_layer.cf_name)
    test_named_instance_layer.delete()
    assert not cf.stack_exists(test_named_instance_layer.cf_name)
    test_vpc_layer.delete()
    assert not cf.stack_exists(test_vpc_layer.cf_name)


def test_get_outputs_from_nondeployed_layer(cf, test_vpc_layer):
    """Tries to get outputs from a layer thas has not been deployed: error"""
    with pytest.raises(CloudformationError):
        test_vpc_layer.outputs


def test_get_outputs_from_layer_without_outputs(cf, test_vpc_layer):
    """Gets outputs from a layer without outputs"""
    test_vpc_layer.create()
    assert test_vpc_layer.outputs is None
    test_vpc_layer.delete()


def test_get_outputs_from_layer(cf, test_streams_layer):
    """Gets outputs from a layer that does produce outputs"""
    test_streams_layer.create()
    ly = test_streams_layer.outputs
    assert isinstance(ly, dict)
    # The names of the 4 Kinesis streams in the layer
    assert len(ly) == 4
