#!/usr/bin/env python
# -*- coding: utf-8 -*-


import click

LOG_LEVELS = ['critical', 'error', 'warning', 'info', 'debug']


def validate_log_level(ctx, param, value):
    value = value.lower()
    if value not in LOG_LEVELS:
        raise click.BadParameter('Should one of %s' % LOG_LEVELS)


@click.command()
@click.option('--log', default='info', help='Log level: CRITICAL, ERROR, '
              'WARNING, INFO or DEBUG', callback=validate_log_level)
@click.option('--botolog', default='info', help='Boto log level: CRITICAL, '
              'ERROR, WARNING, INFO or DEBUG', callback=validate_log_level)
@click.argument('environment')
def main(environment, log, botolog):
    print("environment={}, log={}, botolog={}".format(environment, log,
                                                      botolog))


if __name__ == '__main__':
    main()
