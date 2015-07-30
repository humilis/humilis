#!/usr/bin/env python
# -*- coding: utf-8 -*-


import pytest
import os
from humilis.environment import Environment


@pytest.yield_fixture(scope="module")
def humilis_example_environment():
    yield os.path.join('examples', 'example-environment.yml')


@pytest.yield_fixture(scope="module")
def humilis_environment(humilis_example_environment):
    yield Environment(humilis_example_environment)
