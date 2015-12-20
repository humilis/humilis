#!/usr/bin/env python
# -*- coding: utf-8 -*-


import boto3
import time
from humilis.exceptions import TakesTooLongError, CloudformationError
import humilis.config as config
import humilis.utils as utils
import logging
import os


class CloudFormation:
    """
    A proxy to AWS CloudFormation service
    """
    def __init__(self, logger=None):
        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger

        region = os.environ.get('AWS_REGION')
        if region is not None:
            # If the AWS region is in the environment then override the local
            # AWS CLI config files. This is useful e.g. when running in test
            # environments that don't have those config files.
            session = boto3.session.Session(region_name=region)
        else:
            # Otherwise use the CLI AWS config files
            session = boto3.session.Session()
        self.client = session.client('cloudformation')
        self.resource = session.resource('cloudformation')

    @property
    def stacks(self):
        """Produces a list of CF stack description objects"""
        return self.client.describe_stacks().get('Stacks')

    @property
    def stack_statuses(self):
        """Returns a dict with the status of every stack in CF"""
        return self._get_stack_property('StackStatus')

    @property
    def stack_outputs(self):
        """Returns a dict with the outputs for every stack in CF"""
        return self._get_stack_property('Outputs')

    def _get_stack_property(self, property_name):
        """Gets the value of certain stack property for every stack in CF"""
        return {s.get('StackName'): s.get(property_name) for s
                in self.client.describe_stacks().get('Stacks', [])}

    def delete_stack(self, stack_name, wait=config.default_wait):
        """Deletes a CF stack, if it exists in CF"""
        stack_status = self.stack_statuses.get(stack_name)
        if not stack_status or stack_status in \
                {'DELETE_COMPLETE', 'DELETE_IN_PROGRESS'}:
            stack_status = ('not in CF', stack_status)[stack_status is None]
            msg = "Stack {} is {}: skipping".format(stack_name, stack_status)
            self.logger.info(msg)
            return

        self.client.delete_stack(StackName=stack_name)
        self.wait_for_status_change(stack_name, 'DELETE_IN_PROGRESS',
                                    nb_seconds=wait)
        stack_status = self.stack_statuses.get(stack_name)
        if stack_status and stack_status.find('FAILED') > -1:
            msg = "Failed to delete stack {}. Stack status is {}.".format(
                stack_name, stack_status)
            raise CloudformationError(msg, logger=self.logger)

    def create_stack(self, stack_name, template_body, notification_arns, tags,
                     wait=False):
        """Creates a CF stack, unless it already exists"""
        stack_status = self.stack_statuses.get(stack_name)
        if stack_status in {'CREATE_COMPLETE', 'CREATE_IN_PROGRESS'}:
            msg = "Stack {} already in status {}: skipping".format(
                stack_name, stack_status)
            self.logger.info(msg)
            self.wait_for_status_change(stack_name, 'CREATE_IN_PROGRESS')
            return

        self.client.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Capabilities=['CAPABILITY_IAM'],
            NotificationARNs=notification_arns,
            Tags=utils.roll_tags(tags))
        if wait:
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
             if stack['StackName'] == stack_name]
        if len(y) > 0:
            return self.resource.Stack(y[0]['StackName'])

    def get_stack_resource(self, stack_name, resource_name):
        """Retrieves a resource object from a stack"""
        return [res for res in self.get_stack_resources(stack_name)
                if res.logical_resource_id == resource_name]

    def get_stack_resources(self, stack_name):
        """Retrieves all resources for a stack"""
        stack = self.get_stack(stack_name)
        return stack.resource_summaries.all()

    def get_stack_status(self, stack_name):
        """Gets the current status of a CF stack"""
        stack = self.get_stack(stack_name)
        return stack.stack_status

    def get_stack_events(self, stack_name):
        """Gets a list of stack events sorted by timestamp"""
        stack = self.get_stack(stack_name)
        return sorted(stack.events.all(), key=lambda ev: ev.timestamp)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "CloudFormation()"

    def __getattr__(self, name):
        return getattr(self.client, name)
