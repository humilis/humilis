#!/usr/bin/env python
# -*- coding: utf-8 -*-


from boto3facade.config import Config
import os
import logging


__version__ = '0.4'


CONFIG_FILE = os.path.join(os.path.expanduser('~'), '.humilis')


CONFIG = Config(
    logger=logging.getLogger('humilis'),
    env_prefix='HUMILIS_',
    config_file=CONFIG_FILE)
