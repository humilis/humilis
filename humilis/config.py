"""Humilis configuration."""

import datetime
import pkg_resources
import os
import logging
from configparser import ConfigParser

import boto3facade.config


def _get_config_file():
    project_config = os.path.join(os.path.curdir, '.humilis.ini')
    if os.path.isfile(project_config):
        return project_config
    user_config = os.path.expanduser('~/.humilis.ini')
    return user_config

CONFIG_FILE = _get_config_file()
# The setuptools entry point group for reference parsers
REFPARSERS_GROUP = "humilis.reference_parsers"
# Entry point for jinja2 custom functions
J2_FILTERS_GROUP = "humilis.jinja2_filters"
# The setuptools entry point group for layers
LAYERS_GROUP = "humilis.layers"


class Config():
    """Base configuration.

    Default values used by all configuration profiles.
    """
    KEYS_DIR = os.path.join(os.path.expanduser('~'), '.ssh')
    # Default amount of time to wait for CF to carry out an operation
    CF_TEMPLATE_VERSION = datetime.date(2010, 9, 9)
    LAYER_SECTIONS = ['parameters', 'mappings', 'resources', 'outputs']
    LOG_LEVEL = 'info'

    # Coloring for the events' messages
    COLORS = {
        'blue': '\033[0;34m',
        'red': '\033[0;31m',
        'bred': '\033[1;31m',
        'green': '\033[0;32m',
        'bgreen': '\033[1;32m',
        'yellow': '\033[0;33m',
    }

    EVENT_STATUS_COLOR_MAP = {
        'CREATE_IN_PROGRESS': COLORS['blue'],
        'CREATE_FAILED': COLORS['bred'],
        'CREATE_COMPLETE': COLORS['green'],
        'ROLLBACK_IN_PROGRESS': COLORS['red'],
        'ROLLBACK_FAILED': COLORS['bred'],
        'ROLLBACK_COMPLETE': COLORS['yellow'],
        'DELETE_IN_PROGRESS': COLORS['red'],
        'DELETE_FAILED': COLORS['bred'],
        'DELETE_COMPLETE': COLORS['yellow'],
        'UPDATE_IN_PROGRESS': COLORS['blue'],
        'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS': COLORS['blue'],
        'UPDATE_COMPLETE': COLORS['bgreen'],
        'UPDATE_ROLLBACK_IN_PROGRESS': COLORS['red'],
        'UPDATE_ROLLBACK_FAILED': COLORS['bred'],
        'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS': COLORS['red'],
        'UPDATE_ROLLBACK_COMPLETE': COLORS['yellow'],
        'UPDATE_FAILED': COLORS['bred'],
    }

    # Will take care of creating the .ini file and filling it with the options
    # relevant for the boto3facade module
    LOGGER_NAME = 'humilis'
    ENVAR_PREFIX = 'HUMILIS_'
    DEFAULT_BOTO_PROFILE = 'default'

    def __init__(self, section_name):
        self.from_ini_file(section_name)

        # Configuration keys that will go to the .ini file and that the user
        # can easily customize:
        #
        # s3prefix: A base prefix for any file that humilis uploads to S3
        keys = boto3facade.config.DEFAULT_KEYS + ['s3prefix']
        required_keys = boto3facade.config.DEFAULT_REQUIRED_KEYS

        # Set up logging
        logger = logging.getLogger(self.LOGGER_NAME)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        self.boto_config = boto3facade.config.Config(
            env_prefix=self.ENVAR_PREFIX,
            config_file=CONFIG_FILE,
            active_profile=self.DEFAULT_BOTO_PROFILE,
            keys=keys,
            required_keys=required_keys,
            logger=logger,
            fallback={'s3prefix': 'humilis'})
        self.reference_parsers = self.find_reference_parsers()
        self.layers = self.find_layer_paths()
        self.jinja2_filters = self.find_jinja2_filters()

    def find_reference_parsers(self):
        """Registers all plugin reference parsers."""
        reference_parsers = {}
        for ep in pkg_resources.iter_entry_points(group=REFPARSERS_GROUP):
            reference_parsers[ep.name] = ep.load()
        return reference_parsers

    def find_jinja2_filters(self):
        """Registers all Jinja2 custom functions."""
        funcs = {}
        for func in pkg_resources.iter_entry_points(group=J2_FILTERS_GROUP):
            funcs[func.name] = func.load()
        return funcs

    def find_layer_paths(self):
        """Register the paths to all available layer types."""
        paths = {}
        for ep in pkg_resources.iter_entry_points(group=LAYERS_GROUP):
            paths[ep.name] = ep.load()()
        return paths

    def from_ini_file(self, section_name):
        """Load configuration overrides from :data:`GLOBAL_CONFIG_FILE`.

        :param section_name: Name of the section in the ``*.ini`` file to load.
        """
        if not CONFIG_FILE:
            return
        parser = ConfigParser()
        parser.read(CONFIG_FILE)
        if parser.has_section(section_name):
            for name, value in parser.items(section_name):
                setattr(self, name.upper(), value)


config = Config('default')
