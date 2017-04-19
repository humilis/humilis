"""A dummy module for testing purposes."""

import json
import os
import time
from user_agents import parse


def echo(event, context):
    """Echo handler."""
    event["ts"] = time.time()
    event["os.environ"] = dict(os.environ)
    return event


def uaparse(event, context):
    """Echo handler."""
    ua = event["parameters"]["header"]["User-Agent"]
    return {"device": str(parse(ua)), "os.environ": dict(os.environ)}
