"""Setuptools entry point."""

import os
import codecs
from setuptools import setup, find_packages

import humilis

dirname = os.path.dirname(__file__)

try:
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError, RuntimeError):
    if os.path.isfile("README.md"):
        long_description = codecs.open(os.path.join(dirname, "README.md"),
                                       encoding="utf-8").read()
    else:
        long_description = "AWS cloudformation-based deployment framework"

setup(
    name="humilis",
    version=humilis.__version__,
    author="German Gomez-Herrero",
    author_email="german@findhotel.net",
    url="http://github.com/humilis/humilis",
    license="MIT",
    description="AWS cloudformation-based deployment framework",
    long_description=long_description,
    packages=find_packages(),
    install_requires=[
        "PyYAML<=5.2",
        "six",
        "Click",
        "s3keyring>=0.2.3",
        "boto3facade>=0.5.9",
        "jinja2"],
    classifiers=[
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3"],
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
            "layer_output=humilis.reference:layer",
            "output=humilis.reference:output",           # For backwards compat
            "environment_resource=humilis.reference:environment",
            "environment_output=humilis.reference:environment",
            "environment=humilis.reference:environment",
            "boto3=humilis.reference:boto3",
            "j2_template=humilis.reference:j2_template"],
        "humilis.jinja2_filters": [
            "password=humilis.j2:password",
            "is_list=humilis.j2:is_list",
            "uuid=humilis.j2:uuid4",
            "timestamp=humilis.j2:timestamp",
            "iso_timestamp=humilis.j2:iso_timestamp",
            "uuid4=humilis.j2:uuid4"],
        "humilis.layers": []}
)
