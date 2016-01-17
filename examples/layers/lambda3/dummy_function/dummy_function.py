from __future__ import print_function


import requests


def lambda_handler(event, context):
    r = requests.get('http://yahoo.com')
    print("And the response is ... {}".format(r.status_code))
