#!/usr/bin/env python
# -*- coding: utf-8 -*-


from click.testing import CliRunner
import humilis
import humilis.cli
import pytest


ENV_ACTIONS = ['create', 'delete', 'update']
LOG_LEVELS = ['critical', 'error', 'warning', 'info', 'debug']


@pytest.yield_fixture(scope="module")
def runner():
    yield CliRunner()


@pytest.mark.parametrize("action", ENV_ACTIONS)
def test_env_actions(action, runner, environment_definition_path):
    result = runner.invoke(humilis.cli.main, [action, '--pretend',
                                              environment_definition_path])
    assert result.exit_code == 0


def test_configure_action(runner):
    result = runner.invoke(humilis.cli.main, ['configure', '--no-ask'])
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


@pytest.mark.parametrize('level', LOG_LEVELS)
def test_valid_log_level(level, runner, environment_definition_path):
    result = runner.invoke(humilis.cli.main, ['--log', level, 'create',
                                              environment_definition_path,
                                              '--pretend'])
    assert result.exit_code == 0


def test_output(runner, environment_definition_path):
    result = runner.invoke(humilis.cli.create, [environment_definition_path,
                                                '--output', 'filename',
                                                '--pretend'])
    assert result.exit_code == 0


def test_invalid_option(runner, environment_definition_path):
    result = runner.invoke(humilis.cli.create, [environment_definition_path,
                                                '--invalid_option', 'whatever'
                                                '--pretend'])
    assert result.exit_code > 0


def test_stage(runner, environment_definition_path):
    result = runner.invoke(humilis.cli.create, [environment_definition_path,
                                                '--stage', 'production',
                                                '--pretend'])
    assert result.exit_code == 0
