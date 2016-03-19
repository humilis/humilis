# -*- coding: utf-8 -*-


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
