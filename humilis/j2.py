"""Jinja2 custom functions and filters."""

import string
import random
import uuid


def uuid4(*args, **kwargs):
    """Generate a random UUID string."""
    return str(uuid.uuid4())


def password(size, **kwargs):
    """Generate a random password string."""
    chars = string.ascii_letters + string.digits + \
        ''.join(set(string.punctuation).difference(set("@\"/'\\")))
    pwd = ''.join(random.choice(chars) for _ in range(size))
    return pwd


def is_list(obj, **kwargs):
    return isinstance(obj, list)
