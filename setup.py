#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name="humilis",
    version="0.4",
    author="Innovative Travel Ltd.",
    author_email='german@innovativetravel.eu',
    url='http://github.com/germangh/humilis',
    license='Apache Software License 2.0',
    description='Helps you deploy AWS CloudFormation stacks',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'PyYAML',
        'Click',
        'boto3',
        'boto3facade==0.0.2',
        'jinja2'],
    classifiers=[
        "Programming Language :: Python :: 3"],
    entry_points={
        'console_scripts': [
            'humilis=humilis.cli:main']}
)
