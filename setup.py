#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name="humilis",
    version="0.3a0",
    author="German Gomez-Herrero",
    author_email='g@germangh.com',
    url='http://github.com/germangh/humilis',
    license='Apache Software License 2.0',
    description='Manages AWS Cloudformation stacks',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'PyYAML',
        'Click',
        'boto',
        'jinja2'],
    classifiers=[
        "Programming Language :: Python :: 3"],
    entry_points={
        'console_scripts': [
            'humilis=humilis.cli:main']}
)
