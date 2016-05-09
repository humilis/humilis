#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import humilis.metadata as metadata
import os

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError, RuntimeError):
    if os.path.isfile("README.md"):
        long_description = open("README.md").read()
    else:
        long_description = metadata.description

setup(
    name=metadata.project,
    version=metadata.version,
    author=metadata.authors[0],
    author_email=metadata.emails[0],
    url=metadata.url,
    license=metadata.license,
    description=metadata.description,
    long_description=long_description,
    packages=find_packages(),
    install_requires=[
        "PyYAML",
        "Click",
        "boto3",
        "boto3facade>=0.2.1",
        "keyring",
        "jinja2"],
    classifiers=[
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3"],
    # Allow tests to be run with `python setup.py test'.
    tests_require=[
        "pytest>=2.5.1",
        "mock>=1.0.1",
        "flake8>=2.1.0"
    ],
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "humilis=humilis.cli:main"],
        "humilis.reference_parsers": [
            "secret=humilis.reference:secret",
            "file=humilis.reference:file",
            "lambda=humilis.reference:lambda_ref",
            "layer=humilis.reference:layer",             # For backwards compat
            "layer_resource=humilis.reference:layer",
            "output=humilis.reference:output",           # For backwards compat
            "environment_resource=humilis.reference:environment",
            "layer_output=humilis.reference:output",
            "boto3=humilis.reference:boto3"],
        "humilis.jinja2_filters": [
            "uuid=humilis.j2:uuid"],
        "humilis.layers": []}
)
