# preprocessor:jinja2
from __future__ import print_function


def lambda_handler(event, context):
    print("Hello from layer '{{_layer.name}}' of stage '{{_env.stage}}' of "
          "environment '{{_env.name}}'!")
