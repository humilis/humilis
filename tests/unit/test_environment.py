# -*- coding: utf-8 -*-


import uuid
import yaml

from humilis.environment import Environment


def test_environment_params(environment_definition_j2_path,
                            environment_params_path,
                            test_environment):
    """Tests using a params file in combination with an env def file."""
    with open(environment_params_path, "r") as f:
        params = yaml.load(f.read())
    env = Environment(environment_definition_j2_path, parameters=params)

    layer_params = env.layers[0].meta["parameters"]
    assert layer_params["vpc_cidr"]["value"] == params["vpc_cidr"]


def test_set_get_delete_secret(test_environment):
    """Tests setting and getting a secret for an environment."""
    plaintext = str(uuid.uuid4())
    key = str(uuid.uuid4())
    test_environment.set_secret(key, plaintext)
    retrieved_plaintext = test_environment.get_secret(key)
    assert retrieved_plaintext == plaintext
    test_environment.delete_secret(key)
    assert test_environment.get_secret(key) is None
