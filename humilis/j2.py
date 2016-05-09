"""Jinja2 custom functions and filters."""


import uuid


def uuid4(*args, **kwargs):
    return repr(uuid.uuid4())
