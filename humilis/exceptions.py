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


class FileFormatError(LoggedException):
    def __init__(self, filename, msg=None, *args, **kwargs):
        message = "Wrongly formatted file {}".format(filename)
        if msg is not None:
            message = msg + " : " + msg
        super().__init__(message, *args, **kwargs)


class ReferenceError(LoggedException):
    def __init__(self, ref, msg, *args, **kwargs):
        msg = "Can't parse reference {}: {}".format(ref, msg)
        super().__init__(msg, *args, **kwargs)


class CloudformationError(LoggedException):
    def __init__(self, msg, cf_exception=None, **kwargs):
        if cf_exception is None:
            msg = "{}".format(msg)
        else:
            msg = "{}: {}".format(msg, cf_exception)
        super().__init__(msg, **kwargs)
