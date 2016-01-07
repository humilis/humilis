#!/usr/bin/env python
# -*- coding: utf-8 -*-


def test_create_environment_object(humilis_environment):
    """Creates an Environment objects and queries its properties"""
    env = humilis_environment
    assert env.name == 'example-environment'
    assert env.tags.get('humilis-environment') == env.name


def test_environment_not_already_in_aws(humilis_environment):
    """Ensures tha the test environment is not already in CF"""
    assert not humilis_environment.already_in_cf


def test_create_environment(humilis_environment):
    """Creates a test environment in CF"""
    humilis_environment.create()
    assert humilis_environment.already_in_cf
