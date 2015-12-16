#!/usr/bin/env python
# -*- coding: utf-8 -*-


# For Python 2.x compatibility
from __future__ import print_function
import boto3
import os
import humilis.config as config
import logging
from humilis.exceptions import CloudformationError


class EC2:
    """
    A proxy to AWS EC2 service
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
        self.client = session.client('ec2')

    def create_key_pair(self, key_name):
        """Creates a keypair in AWS EC2, if it doesn't exist already"""
        if not self.key_pair_exists(key_name):
            key = self.client.create_key_pair(key_name)
            self.save_key_pair(key)
            return True
        else:
            msg = "Key {} already exists: skipping key creation".format(
                key_name)
            self.logger.info(msg)
            return False

    def save_key_pair(self, key):
        """Saves an AWS keypair to a local directory"""
        target_file = os.path.join(config.keys_dir, key.name)
        if os.path.isfile(target_file):
            msg = "File {} already exists: will not be overwritten".format(
                key.name)
            self.logger.info(msg)
        with open(target_file, 'a') as f:
            print(key.material, file=f)

    def delete_key_pair(self, key_name):
        """Deletes a keypair by name"""
        if not self.key_pair_exists(key_name):
            msg = "Key {} does not exist: cannot delete it".format(key_name)
            self.logger.info(msg)
            return False
        else:
            success = self.client.delete_key_pair(key_name)
            if not success:
                msg = "CF failed to create key {}".format(key_name)
                raise CloudformationError(msg, logger=self.logger)
            return True

    def key_pair_exists(self, key_name):
        """Returns True if a key exists in AWS"""
        return key_name in [
            k['KeyName'] for k
            in self.client.describe_key_pairs().get('KeyPairs')]

    def get_ami_by_tag(self, tags):
        """Gets a list of AMIs that have the specified tags and corresp. values
        """
        imgs = self.client.get_all_images(owners='self')
        sel_imgs = []
        for img in imgs:
            matched = True
            for k, v in tags.items():
                if k not in img.tags or v != img.tags[k]:
                    matched = False
            if matched:
                sel_imgs.append(img)
        return sel_imgs

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "EC2(region='{}')".format(self.region)

    def __getattr__(self, name):
        return getattr(self.client, name)
