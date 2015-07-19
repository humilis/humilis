#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="humilis",
    version="0.3a0",
    author="German Gomez-Herrero",
    author_email='g@germangh.com',
    license='Apache Software License 2.0',
    description='Manages AWS Cloudformation stacks',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'PyYAML',
        'Click',
        'boto',
        'jinja2'],
    entry_points={
        'console_scripts': [
            'humilis=humilis.cli:main']}
)
