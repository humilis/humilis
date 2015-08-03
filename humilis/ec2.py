import boto.ec2
import os


import humilis.config as config
import logging
from humilis.exceptions import CloudFormationError


class EC2:
    """
    A proxy to AWS EC2 service
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

        self.connection = boto.ec2.connect_to_region(
            self.region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key)

    def create_key_pair(self, key_name):
        if not self.key_pair_exists(key_name):
            key = self.connection.create_key_pair(key_name)
            self.save_key_pair(key)
            return True
        else:
            msg = "Key {} already exists: skipping key creation".format(
                key_name)
            self.logger.info(msg)
            return False

    def save_key_pair(self, key):
        target_file = os.path.join(config.keys_dir, key.name)
        if os.path.isfile(target_file):
            msg = "File {} already exists: will not be overwritten".format(
                key.name)
            self.logger.info(msg)
        with open(target_file, 'a') as f:
            print(key.material, file=f)

    def delete_key_pair(self, key_name, key_path):
        if not self.key_pair_exists(key_name):
            msg = "Key {} does not exist: cannot delete it".format(key_name)
            self.logger.info(msg)
            return False
        else:
            success = self.connection.delete_key_pair(key_name)
            if not success:
                msg = "CF failed to create key {}".format(key_name)
                raise CloudFormationError(msg, logger=self.logger)
            return True

    def key_pair_exists(self, key_name):
        return key_name in [k.name for k
                            in self.connection.get_all_key_pairs()]

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "EC2(region='{}')".format(self.region)

    def __getattr__(self, name):
        return getattr(self.connection, name)
