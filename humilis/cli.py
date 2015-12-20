#!/usr/bin/env python
# -*- coding: utf-8 -*-


import click
import logging
from humilis.environment import Environment

LOG_LEVELS = ['critical', 'error', 'warning', 'info', 'debug']


def validate_log_level(ctx, param, value):
    value = value.lower()
    if value not in LOG_LEVELS:
        raise click.BadParameter("Should one of {}".format(LOG_LEVELS))
    return value.upper()


@click.group()
@click.option('--log', default='info', help='Log level: CRITICAL, ERROR, '
              'WARNING, INFO or DEBUG', callback=validate_log_level)
@click.option('--botolog', default='info', help='Boto log level: CRITICAL, '
              'ERROR, WARNING, INFO or DEBUG', callback=validate_log_level)
def main(log, botolog):
    logging.basicConfig(level=getattr(logging, log))


@main.command()
@click.argument('environment')
@click.option('--pretend/--no-pretend', default=False)
def create(environment, pretend):
    env = Environment(environment)
    if not pretend:
        env.create()


@main.command()
@click.argument('environment')
@click.option('--pretend/--no-pretend', default=False)
def delete(environment, pretend):
    env = Environment(environment)
    if not pretend:
        env.delete()


if __name__ == '__main__':
    main()
