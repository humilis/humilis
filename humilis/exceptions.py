"""Humilis exceptions."""


class LoggedException(Exception):
    """Logs an exception message as a critical event"""
    def __init__(self, msg, logger=None):
        if logger:
            logger.critical(msg)
        super(LoggedException, self).__init__(msg)


class MissingParentLayerError(LoggedException):
    """A layer refers to a parent that cannot be found."""
    pass


class MissingPluginError(LoggedException):
    """A plug-in needs to be installed."""
    pass


class TakesTooLongError(LoggedException):
    """It has taken too long for AWS to do something"""
    pass


class FileFormatError(LoggedException):
    """Error when parsing a layer or environment file."""
    def __init__(self, filename, msg=None, *args, **kwargs):
        message = "Wrongly formatted file {}".format(filename)
        if msg is not None:
            message = msg + " : " + msg
        super(FileFormatError, self).__init__(message, *args, **kwargs)


class RequiresVaultError(LoggedException):
    """Requires a secrets-vault layer in the same environment."""
    def __init__(self, msg=None, *args, **kwargs):
        message = "Requires a secrets-vault layer in the environment"
        if msg is not None:
            message = msg + " : " + msg
        super(RequiresVaultError, self).__init__(message, *args, **kwargs)


class ReferenceError(LoggedException):
    """Error when trying to parse a template reference."""
    def __init__(self, ref, msg, *args, **kwargs):
        msg = "Can't parse reference {}: {}".format(ref, msg)
        super(ReferenceError, self).__init__(msg, *args, **kwargs)


class InvalidLambdaDependencyError(LoggedException):
    """Error when trying to install a Lambda dependency."""
    def __init__(self, ref, msg, *args, **kwargs):
        msg = "Can't parse reference {}: {}".format(ref, msg)
        super(InvalidLambdaDependencyError, self).__init__(msg, *args,
                                                           **kwargs)


class AlreadyInCfError(LoggedException):
    """Trying to re-deploy a layer or environment to CF."""
    pass


class CloudformationError(LoggedException):
    """An error internal to the Cloudformation service."""
    def __init__(self, msg, cf_exception=None, **kwargs):
        if cf_exception is None:
            msg = "{}".format(msg)
        else:
            msg = "{}: {}".format(msg, cf_exception)
        super(CloudformationError, self).__init__(msg, **kwargs)
