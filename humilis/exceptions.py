#!/usr/bin/env python
# -*- coding: utf-8 -*-


class LoggedException(Exception):
    """Logs an exception message as a critical event"""
    def __init__(self, msg, logger=None):
        if logger:
            logger.critical(msg)
        super().__init__(msg)


class TakesTooLongError(LoggedException):
    """It has taken too long for AWS to do something"""
    pass


class CloudFormationError(LoggedException):
    """CF failed to perform the requested operation"""
    pass
