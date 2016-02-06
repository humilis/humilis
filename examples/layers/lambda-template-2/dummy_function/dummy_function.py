# preprocessor:jinja2
from __future__ import print_function


import requests


def lambda_handler(event, context):
    print("Hello from layer '{{_layer.name}}' of stage '{{_env.stage}}' of "
          "environment '{{_env.name}}'!")
    r = requests.get('http://yahoo.com')
    print("And the response is ... {}".format(r.status_code))
