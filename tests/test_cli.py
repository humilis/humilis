#!/usr/bin/env python
# -*- coding: utf-8 -*-


from click.testing import CliRunner
import humilis.cli
import pytest


@pytest.yield_fixture(scope="module")
def runner():
    yield CliRunner()


def test_log_level(runner):
    result = runner.invoke(humilis.cli.main, ['production'])
    assert result.exit_code == 0
