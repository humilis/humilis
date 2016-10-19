"""Command line interface."""

import logging

import click
import yaml

from humilis.config import config
from humilis.environment import Environment

LOG_LEVELS = ["critical", "error", "warning", "info", "debug"]


def validate_log_level(ctx, param, value):
    value = value.lower()
    if value not in LOG_LEVELS:
        raise click.BadParameter("Should one of {}".format(LOG_LEVELS))
    return value.upper()


@click.group()
@click.option("--log", default='info', help="Log level: {}".format(LOG_LEVELS),
              callback=validate_log_level, metavar="LEVEL")
@click.option("--profile", default='default', metavar='NAME',
              help="The name of configuration profile.")
def main(log, profile):
    logger = logging.getLogger("humilis")
    logger.setLevel(getattr(logging, log))
    config.boto_config.activate_profile(profile)


@main.command()
@click.argument("environment")
@click.option("--stage", help="Deployment stage, e.g. PRODUCTION, or DEV",
              default=None, metavar='STAGE')
@click.option("--output", help="Store environment outputs in a yaml file",
              default=None, metavar="FILE")
@click.option("--pretend/--no-pretend", default=False)
@click.option("--parameters", help="Deployment parameters", default=None,
              metavar="YAML_FILE")
def create(environment, stage, output, pretend, parameters):
    """Creates an environment."""
    if parameters:
        with open(parameters, "r") as f:
            parameters = _ensure_defaults(yaml.load(f.read()))

    env = Environment(environment, stage=stage, parameters=parameters)
    if not pretend:
        env.create(output_file=output, update=False)


@main.command(name="set-secret")
@click.argument("environment")
@click.argument("key")
@click.argument("value")
@click.option("--stage", help="Deployment stage, e.g. PRODUCTION, or DEV",
              default=None, metavar="STAGE")
@click.option("--pretend/--no-pretend", default=False)
def set_secret(environment, key, value, stage, pretend):
    """Stores a secret in the vault."""
    env = Environment(environment, stage=stage)
    if not pretend:
        env.set_secret(key, value)


@main.command(name="get-secret")
@click.argument("environment")
@click.argument("key")
@click.option("--stage", help="Deployment stage, e.g. PRODUCTION, or DEV",
              default=None, metavar="STAGE")
@click.option("--pretend/--no-pretend", default=False)
def get_secret(environment, key, stage, pretend):
    """Gets a secret from the vault."""
    env = Environment(environment, stage=stage)
    if not pretend:
        resp = env.get_secret(key)
        print(resp)


@main.command()
@click.argument("environment")
@click.option("--stage", help="Deployment stage, e.g. PRODUCTION, or DEV",
              default=None, metavar="STAGE")
@click.option("--output", help="Store environment outputs in a yaml file",
              default=None, metavar='FILE')
@click.option("--pretend/--no-pretend", default=False)
@click.option("--parameters", help="Deployment parameters", default=None,
              metavar="YAML_FILE")
def update(environment, stage, output, pretend, parameters):
    """Updates (or creates) an environment."""
    if parameters:
        with open(parameters, "r") as f:
            parameters = yaml.load(f.read())
    env = Environment(environment, stage=stage, parameters=parameters)
    if not pretend:
        env.create(output_file=output, update=True)


@main.command()
@click.argument("environment")
@click.option("--stage", help="Deployment stage, e.g. PRODUCTION, or DEV",
              default=None, metavar='STAGE')
@click.option("--pretend/--no-pretend", default=False)
@click.option("--parameters", help="Deployment parameters", default=None,
              metavar="YAML_FILE")
def delete(environment, stage, pretend, parameters):
    """Deletes an environment that has been deployed to CF."""
    if parameters:
        with open(parameters, "r") as f:
            parameters = yaml.load(f.read())

    env = Environment(environment, stage=stage, parameters=parameters)
    if not pretend:
        env.delete()


@main.command()
@click.option("--ask/--no-ask", default=True)
@click.option("--local/--no-local",
              help="Save configuration in a file under the current directory",
              default=False)
def configure(ask, local):
    """Configure humilis."""
    config.boto_config.configure(ask=ask, local=local)


def _ensure_defaults(parameters):
    """Apply default values to unspecified stage parameters."""
    if "_default" in parameters:
        for stage, stage_params in parameters.items():
            for pname, pvalue in parameters["_default"].items():
                stage_params[pname] = stage_params.get(pname, pvalue)

    return parameters


if __name__ == '__main__':
    main()
