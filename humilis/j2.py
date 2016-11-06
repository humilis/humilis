"""Jinja2 custom functions and filters."""

import string
import random
import time
import uuid


def uuid4(size=32, *args, **kwargs):
    """Generate a random UUID string."""
    return str(uuid.uuid4())[:min(size, 32)]


def timestamp(*args, **kwargs):
    """Generate a Unix timestamp."""
    return time.time()


def password(size, **kwargs):
    """Generate a random password string."""
    chars = string.ascii_letters + string.digits + \
        ''.join(set(string.punctuation).difference(set("@\"/'\\")))
    pwd = ''.join(random.choice(chars) for _ in range(size))
    return pwd


def is_list(obj, **kwargs):
    return isinstance(obj, list)
