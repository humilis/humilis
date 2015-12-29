#!/usr/bin/env python
# -*- coding: utf-8 -*-


import datetime
import os


# The name of the keypair to use for testing purposes. If this key does not
# exist already in AWS, it will be automatically created when running the
# test suite. If you change the name of the testkey remember to modify
# accordingly the default parameters of the instance layer. Otherwise the test
# suite will break.
test_key = 'humilis-testkey'

# The local directory where SSH key pairs should be saved to
keys_dir = os.path.join(os.path.expanduser('~'), '.ssh')

# The S3 bucket where layer artifacts will be stored (e.g. lambda functions)
s3bucket = 'innovativetravel-code'
# Artifacts will be stored under [s3prefix]/[layer_name]
s3prefix = 'humilis/'

# Default amount of time to wait for CF to carry out an operation
default_wait = 10*60

cf_template_version = datetime.date(2010, 9, 9)
layer_sections = ['parameters', 'mappings', 'resources', 'outputs']

# Default logging levels
botolog = 'info'
log = 'info'

# Coloring for the events' messages
colors = {
    'blue': '\033[0;34m',
    'red': '\033[0;31m',
    'bred': '\033[1;31m',
    'green': '\033[0;32m',
    'bgreen': '\033[1;32m',
    'yellow': '\033[0;33m',
}

event_status_color_map = {
    'CREATE_IN_PROGRESS': colors['blue'],
    'CREATE_FAILED': colors['bred'],
    'CREATE_COMPLETE': colors['green'],
    'ROLLBACK_IN_PROGRESS': colors['red'],
    'ROLLBACK_FAILED': colors['bred'],
    'ROLLBACK_COMPLETE': colors['yellow'],
    'DELETE_IN_PROGRESS': colors['red'],
    'DELETE_FAILED': colors['bred'],
    'DELETE_COMPLETE': colors['yellow'],
    'UPDATE_IN_PROGRESS': colors['blue'],
    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS': colors['blue'],
    'UPDATE_COMPLETE': colors['bgreen'],
    'UPDATE_ROLLBACK_IN_PROGRESS': colors['red'],
    'UPDATE_ROLLBACK_FAILED': colors['bred'],
    'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS': colors['red'],
    'UPDATE_ROLLBACK_COMPLETE': colors['yellow'],
    'UPDATE_FAILED': colors['bred'],
}
