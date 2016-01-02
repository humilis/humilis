#!/usr/bin/env python
# -*- coding: utf-8 -*-


# For Python 2.x compatibility
from __future__ import print_function
import boto3
import humilis.config as config
import logging
from botocore.exceptions import ClientError


class S3:
    """A proxy to the AWS S3 service"""
    def __init__(self, logger=None):
        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger
        region = config.aws_region
        if region is not None:
            # If the AWS region is in the environment then override the local
            # AWS CLI config files. This is useful e.g. when running in test
            # environments that don't have those config files.
            session = boto3.session.Session(region_name=region)
        else:
            # Otherwise use the CLI AWS config files
            session = boto3.session.Session()
        self.client = session.client('s3')

    def cp(self, local_path, s3_bucket, s3_key):
        """Uploads a local file to a S3 bucket"""
        try:
            return self.client.upload_file(local_path, s3_bucket, s3_key)
        except ClientError:
            msg = "Error uploading {} to {}/{}".format(
                local_path, s3_bucket, s3_key)
            self.logger.error(msg)
            raise

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "S3()"

    def __getattr__(self, name):
        return getattr(self.client, name)
