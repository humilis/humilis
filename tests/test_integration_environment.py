#!/usr/bin/env python
# -*- coding: utf-8 -*-


def test_create_environment_object(test_environment):
    """Creates an Environment objects and queries its properties."""
    env = test_environment
    assert env.name == 'example-environment'
    assert env.tags.get('humilis-environment') == env.name


def test_environment_not_already_in_aws(test_environment):
    """Ensures that the test environment is not already in CF."""
    test_environment.delete()
    assert not test_environment.in_cf


def test_create_environment(test_environment):
    """Creates a test environment in CF."""
    test_environment.create()
    assert test_environment.in_cf
    test_environment.delete()
    assert not test_environment.in_cf
