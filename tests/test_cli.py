#!/usr/bin/env python
# -*- coding: utf-8 -*-


from click.testing import CliRunner
import humilis.cli
import pytest


@pytest.yield_fixture(scope="module")
def runner():
    yield CliRunner()


def test_basic(runner):
    result = runner.invoke(humilis.cli.main, ['testenv'])
    assert result.exit_code == 0


def test_invalid_log_level(runner):
    result = runner.invoke(humilis.cli.main, ['--log', 'invalid'])
    assert result.exit_code > 0
    assert isinstance(result.exception, SystemExit)


def test_valid_log_level(runner):
    for level in ['critical', 'error', 'warning', 'info', 'debug']:
        result = runner.invoke(humilis.cli.main, ['testenv', '--log', level])
        assert result.exit_code == 0


def test_invalid_botolog_level(runner):
    result = runner.invoke(humilis.cli.main, ['--log', 'invalid'])
    assert result.exit_code > 0
    assert isinstance(result.exception, SystemExit)


def test_valid_botolog_level(runner):
    for level in ['critical', 'error', 'warning', 'info', 'debug']:
        result = runner.invoke(humilis.cli.main, ['testenv', '--log', level])
        assert result.exit_code == 0
