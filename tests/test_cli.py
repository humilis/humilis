#!/usr/bin/env python
# -*- coding: utf-8 -*-


from click.testing import CliRunner
import humilis.cli
import pytest


ENV_ACTIONS = ['create', 'delete']
LOG_LEVELS = ['critical', 'error', 'warning', 'info', 'debug']


@pytest.yield_fixture(scope="module")
def runner():
    yield CliRunner()


def test_actions(runner):
    for action in ENV_ACTIONS:
        result = runner.invoke(humilis.cli.main, [action, 'testenv'])
        assert result.exit_code == 0


def test_actions_with_missing_environment(runner):
    for action in ENV_ACTIONS:
        result = runner.invoke(humilis.cli.main, [action])
        assert result.exit_code > 0
        assert isinstance(result.exception, SystemExit)


def test_invalid_log_level(runner):
    result = runner.invoke(humilis.cli.main, ['--log', 'invalid'])
    assert result.exit_code > 0
    assert isinstance(result.exception, SystemExit)


def test_valid_log_level(runner):
    for level in ['critical', 'error', 'warning', 'info', 'debug']:
        result = runner.invoke(humilis.cli.main, ['--log', level, 'create',
                                                  'testenv'])
        assert result.exit_code == 0


def test_invalid_botolog_level(runner):
    result = runner.invoke(humilis.cli.main, ['--log', 'invalid', 'create',
                                              'testenv'])
    assert result.exit_code > 0
    assert isinstance(result.exception, SystemExit)


def test_valid_botolog_level(runner):
    for level in LOG_LEVELS:
        result = runner.invoke(humilis.cli.main, ['--log', level, 'create',
                                                  'testenv'])
        assert result.exit_code == 0
