#!/usr/bin/env python
# -*- coding: utf-8 -*-


import boto.cloudformation
import os
import time
from humilis.exceptions import TakesTooLongError, CloudformationError
import humilis.config as config
import logging


class CloudFormation:
    """
    A proxy to AWS CloudFormation service
    """
    def __init__(self, region=config.region, aws_access_key_id=None,
                 aws_secret_access_key=None, logger=None):
        self.region = region
        if aws_access_key_id is None:
            aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        if aws_secret_access_key is None:
            aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')

        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger

        self.connection = boto.cloudformation.connect_to_region(
            self.region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key)

    @property
    def stacks(self):
        """Produces a list of CF stack description objects"""
        return list(self.connection.describe_stacks())

    @property
    def stack_statuses(self):
        """Returns a dict with the status of every stack in CF"""
        statuses = {s.stack_name: s.stack_status for s
                    in self.connection.describe_stacks()}
        return statuses

    def delete_stack(self, stack_name, wait=config.default_wait):
        """Deletes a CF stack, if it exists in CF"""
        stack_status = self.stack_statuses.get(stack_name)
        if not stack_status or stack_status in \
                {'DELETE_COMPLETE', 'DELETE_IN_PROGRESS'}:
            stack_status = ('not in CF', stack_status)[stack_status is None]
            msg = "Stack {} is {}: skipping".format(stack_name, stack_status)
            self.logger.info(msg)
            return

        self.connection.delete_stack(stack_name)
        self.wait_for_status_change(stack_name, 'DELETE_IN_PROGRESS',
                                    nb_seconds=wait)
        stack_status = self.stack_statuses.get(stack_name)
        if stack_status and stack_status.find('FAILED') > -1:
            msg = "Failed to delete stack {}. Stack status is {}.".format(
                stack_name, stack_status)
            raise CloudformationError(msg, logger=self.logger)

    def create_stack(self, stack_name, **kwargs):
        """Creates a CF stack, unless it already exists"""
        stack_status = self.stack_statuses.get(stack_name)
        if stack_status in {'CREATE_COMPLETE', 'CREATE_IN_PROGRESS'}:
            msg = "Stack {} already in status {}: skipping".format(
                stack_name, stack_status)
            self.logger.info(msg)
            self.wait_for_status_change(stack_name, 'CREATE_IN_PROGRESS')
            return

        self.connection.create_stack(stack_name, **kwargs)
        self.wait_for_status_change(stack_name, 'CREATE_IN_PROGRESS')
        stack_status = self.stack_statuses.get(stack_name)
        if stack_status.find('FAILED') > -1:
            msg = "Failed to create stack {}. Stack status is {}.".format(
                stack_name, stack_status)
            raise CloudformationError(msg, logger=self.logger)

    def stack_exists(self, stack_name):
        """Checks whether a stack exists in CF"""
        return stack_name in self.stack_statuses

    def stack_ok(self, stack_name):
        """Checks whether a stack is operational"""
        return self.stack_exists(stack_name) and \
            self.stack_statuses.get(stack_name) \
            in {'UPDATE_COMPLETE', 'CREATE_COMPLETE'}

    def wait_for_status_change(self, stack_name, status,
                               nb_seconds=config.default_wait):
        """Waits for a stack status to change"""
        counter = 0
        curr_status = status
        time.sleep(1)
        while curr_status and curr_status == status:
            time.sleep(1)
            counter += 1
            curr_status = self.stack_statuses.get(stack_name)
            if counter >= nb_seconds:
                msg = ("Stack {stack_name} has stayed over {nb_seconds} "
                       "seconds in status {status}").format(
                    stack_name=stack_name,
                    nb_seconds=nb_seconds,
                    status=status)
                raise TakesTooLongError(msg, logger=self.logger)

    def get_stack(self, stack_name):
        """Retrieves a stack object using the stack name"""
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
