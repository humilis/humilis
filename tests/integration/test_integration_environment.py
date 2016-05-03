#!/usr/bin/env python
# -*- coding: utf-8 -*-


def test_create_environment_object(test_environment, test_environment_pair):
    """Creates an Environment objects and queries its properties."""
    env1, env2 = test_environment_pair
    for i, env in enumerate([test_environment, env1, env2]):
        if i:
            assert env.name == "example-environment-{}".format(i+1)
        else:
            assert env.name == "example-environment"
        assert env.tags.get('humilis:environment') == env.name


def test_create_environment_pair(test_environment_pair):
    """Creates an environment that refers to another environment."""
    env1, env2 = test_environment_pair
    env1.create()
    assert env1.in_cf
    env2.create()
    assert env2.in_cf
    env2.delete()
    assert not env2.in_cf
    env1.delete()
    assert not env1.in_cf


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
