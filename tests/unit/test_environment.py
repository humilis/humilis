"""Test Environment class."""

import uuid
import yaml

import pytest

from humilis.environment import Environment
from humilis.exceptions import RequiresVaultError


def test_set_get_delete_secret(test_environment):
    """Tests setting and getting a secret for an environment."""
    plaintext = str(uuid.uuid4())
    key = str(uuid.uuid4())
    with pytest.raises(RequiresVaultError):
        test_environment.set_secret(key, plaintext)

    with pytest.raises(RequiresVaultError):
        test_environment.get_secret(key)

    with pytest.raises(RequiresVaultError):
        test_environment.delete_secret(key)
