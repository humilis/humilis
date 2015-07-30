#!/usr/bin/env python
# -*- coding: utf-8 -*-


import datetime


cf_template_version = datetime.date(2010, 9, 9)
layer_sections = ['parameters', 'mappings', 'resources']
region = 'eu-west-1'

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
