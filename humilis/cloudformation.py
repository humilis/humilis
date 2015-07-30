#!/usr/bin/env python
# -*- coding: utf-8 -*-


import boto.cloudformation
import os


class CloudFormation:
    """
    A proxy to AWS CloudFormation service
    """
    def __init__(self, region, aws_access_key=None,
                 aws_secret_access_key=None):
        self.region = region
        if aws_access_key is None:
            aws_access_key = os.environ.get('AWS_ACCESS_KEY')
        if aws_secret_access_key is None:
            aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')

        self.connection = boto.cloudformation.connect_to_region(
            self.region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_access_key)

    @property
    def stacks(self):
        return list(self.connection.describe_stacks())

    def get_stack(self, stack_name):
        y = [stack for stack in self.stacks
             if stack.stack_name == stack_name]
        if len(y) > 0:
            return y[0]

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "CloudFormation(region='{}')".format(self.region)

    def __getattr__(self, name):
        return getattr(self.connection, name)
