#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import humilis.metadata as metadata

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError):
    long_description = open('README.md').read()

setup(
    name=metadata.project,
    version=metadata.version,
    author=metadata.authors[0],
    author_email=metadata.emails[0],
    url=metadata.url,
    license=metadata.license,
    description=metadata.description,
    packages=find_packages(),
    package_data={'humilis': ['*.yaml', '*.ini', '*.yml', '*.zip',
                              '*.json']},
    include_package_data=True,
    install_requires=[
        'PyYAML',
        'Click',
        'boto3',
        'boto3facade==0.0.8',
        'jinja2'],
    classifiers=[
        "Programming Language :: Python :: 3"],
    # Allow tests to be run with `python setup.py test'.
    tests_require=[
        'pytest>=2.5.1',
        'mock>=1.0.1',
        'flake8>=2.1.0'
    ],
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'humilis=humilis.cli:main']}
)
