#!/usr/bin/env python
# -*- coding: utf-8 -*-


import click
from humilis.environment import Environment
import humilis.config as config
import boto.ec2

LOG_LEVELS = ['critical', 'error', 'warning', 'info', 'debug']


def validate_log_level(ctx, param, value):
    value = value.lower()
    if value not in LOG_LEVELS:
        raise click.BadParameter("Should one of {}".format(LOG_LEVELS))


class RegionValidator:
    def __init__(self):
        self.__valid_regions = None

    @property
    def valid_regions(self):
        if self.__valid_regions is None:
            self.__valid_regions = [reg.name for reg in boto.ec2.regions()]
        return self.__valid_regions

    def __call__(self, ctx, param, value):
        value = value.lower()
        if value not in self.valid_regions:
            raise click.BadParameter("Should be one of {}".format(
                self.valid_regions))


@click.group()
@click.option('--log', default='info', help='Log level: CRITICAL, ERROR, '
              'WARNING, INFO or DEBUG', callback=validate_log_level)
@click.option('--botolog', default='info', help='Boto log level: CRITICAL, '
              'ERROR, WARNING, INFO or DEBUG', callback=validate_log_level)
@click.option('--region', default=config.region, help='The AWS region',
              callback=RegionValidator())
def main(log, botolog, region):
    pass


@main.command()
@click.argument('environment')
@click.option('--pretend/--no-pretend', default=True)
def create(environment, pretend):
    env = Environment(environment)
    if not pretend:
        env.create()


@main.command()
@click.argument('environment')
@click.option('--pretend/--no-pretend', default=True)
def delete(environment, pretend):
    env = Environment(environment)
    if not pretend:
        env.delete()


if __name__ == '__main__':
    main()
