#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

import click

from humilis.config import config
from humilis.environment import Environment

LOG_LEVELS = ['critical', 'error', 'warning', 'info', 'debug']


def validate_log_level(ctx, param, value):
    value = value.lower()
    if value not in LOG_LEVELS:
        raise click.BadParameter("Should one of {}".format(LOG_LEVELS))
    return value.upper()


@click.group()
@click.option('--log', default='info', help="Log level: {}".format(LOG_LEVELS),
              callback=validate_log_level, metavar='LEVEL')
@click.option('--profile', default='default', metavar='NAME')
def main(log, profile):
    logging.basicConfig(level=getattr(logging, log))
    config.boto_config.activate_profile(profile)


@main.command()
@click.argument('environment')
@click.option('--stage', help="Deployment stage, e.g. PRODUCTION, or DEV",
              default=None, metavar='STAGE')
@click.option('--output', help="Store environment outputs in a yaml file",
              default=None, metavar='FILE')
@click.option('--pretend/--no-pretend', default=False)
def create(environment, stage, output, pretend):
    """Creates an environment."""
    env = Environment(environment, stage=stage)
    if not pretend:
        env.create(output_file=output, update=False)


@main.command()
@click.argument('environment')
@click.option('--stage', help="Deployment stage, e.g. PRODUCTION, or DEV",
              default=None, metavar='STAGE')
@click.option('--output', help="Store environment outputs in a yaml file",
              default=None, metavar='FILE')
@click.option('--pretend/--no-pretend', default=False)
def update(environment, stage, output, pretend):
    """Updates (or creates) an environment."""
    env = Environment(environment, stage=stage)
    if not pretend:
        env.create(update=True)


@main.command()
@click.argument('environment')
@click.option('--stage', help="Deployment stage, e.g. PRODUCTION, or DEV",
              default=None, metavar='STAGE')
@click.option('--pretend/--no-pretend', default=False)
def delete(environment, stage, pretend):
    """Deletes an environment that has been deployed to CF."""
    env = Environment(environment, stage=stage)
    if not pretend:
        env.delete()


@main.command()
@click.option('--ask/--no-ask', default=True)
def configure(ask):
    """Configure humilis."""
    config.boto_config.configure(ask=ask)


if __name__ == '__main__':
    main()
