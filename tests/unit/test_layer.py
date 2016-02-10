# -*- coding: utf-8 -*-
"""Tests the interface of the Layer object."""


def test_meta_template_parameters(test_vpc_layer):
    """Tests passing parameters to meta.yaml.j2 from the env file."""
    assert test_vpc_layer.user_params.get('template_parameter') is not None
    assert test_vpc_layer.meta['parameters']['dummy_parameter']['value'] ==\
        test_vpc_layer.user_params['template_parameter']
