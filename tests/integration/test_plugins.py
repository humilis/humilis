"""Create and destroy the test environments for various humilis plugins."""

import os
import pytest

from humilis.environment import Environment


EXAMPLES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "examples"))

EXAMPLE_ENVS = [
    envfile
    for envfile in os.listdir(EXAMPLES_DIR)
    if not os.path.isdir(os.path.join(EXAMPLES_DIR, envfile))]


@pytest.mark.parametrize("envfile", EXAMPLE_ENVS)
def test_plugin(envfile):
    """Create and destroy the test environment of a humilis plugin."""
    envfile_path = os.path.join(EXAMPLES_DIR, envfile)
    env = Environment(envfile_path, stage="TEST")
    try:
        env.create(update=True)
    finally:
        env.delete()
