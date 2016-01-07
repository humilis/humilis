#!/usr/bin/env python
# -*- coding: utf-8 -*-


import click
import logging
from humilis.environment import Environment
from humilis.config import config

LOG_LEVELS = ['critical', 'error', 'warning', 'info', 'debug']


def validate_log_level(ctx, param, value):
    value = value.lower()
    if value not in LOG_LEVELS:
        raise click.BadParameter("Should one of {}".format(LOG_LEVELS))
    return value.upper()


@click.group()
@click.option('--log', default='info', help="Log level :{}".format(LOG_LEVELS),
              callback=validate_log_level, metavar='LEVEL')
@click.option('--profile', default='default', metavar='NAME')
def main(log, profile):
    logging.basicConfig(level=getattr(logging, log))
    config.boto_config.active_profile = profile


@main.command()
@click.argument('environment')
@click.option('--pretend/--no-pretend', default=False)
@click.option('--output', help="Store environment outputs in a yaml file",
              default=None, metavar='FILE')
def create(environment, pretend, output):
    """Creates an environment."""
    env = Environment(environment)
    if not pretend:
        env.create(output_file=output)


@main.command()
@click.argument('environment')
@click.option('--pretend/--no-pretend', default=False)
def delete(environment, pretend):
    """Deletes an environment that has been deployed to CF."""
    env = Environment(environment)
    if not pretend:
        env.delete()


@main.command()
@click.option('--ask/--no-ask', default=True)
def configure(ask):
    """Configure humilis."""
    config.boto_config.configure(ask=ask)


if __name__ == '__main__':
    main()
