humilis
==========

[![Circle CI](https://circleci.com/gh/InnovativeTravel/humilis.svg?style=svg)](https://circleci.com/gh/InnovativeTravel/humilis)
[![PyPI](https://img.shields.io/pypi/v/humilis.svg?style=flat)](https://pypi.python.org/pypi/humilis)

Helps you deploy AWS infrastructure with [Cloudformation][cf].

[cf]: https://aws.amazon.com/cloudformation/

This project is originally based on the
[cumulus](https://github.com/germangh/cumulus/blob/master/cumulus/__init__.py).
project. See [CUMULUS_LICENSE][cumulus_license] for license information.

[cumulus]: https://github.com/cotdsa/cumulus
[cumulus_license]: https://github.com/germangh/humilis/blob/master/CUMULUS_LICENSE


# Installation

To install the latest "stable" version:

```
pip install humilis
```

To install the development version:

````
pip install git+https://github.com/germangh/humilis
````

After installation you need to configure humilis. To configure globally for 
your system:

```
humilis configure
```

The command above will store and read the configuration options from
`~/.humilis.ini`. You can also store the configuration in a `.humilis.ini` file
stored in your current working directory by using:

```
humilis configure --local
```

`humilis` will always read the configuration first from a `.humilis.ini` file
under your current work directory. If it is not found then it will read it from
your system global config file `~/.humilis`.


# Development environment

Assuming you have [virtualenv][venv] installed:

[venv]: https://virtualenv.readthedocs.org/en/latest/

```
make develop

. .env/bin/activate
```


# Testing

At the moment, most tests are integration tests with the AWS SDK. This means
that you will need to [set up your system][aws-setup] to access AWS resources
if you want to run the test suite.

[aws-setup]: http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html

```
py.test tests
```


# Quickstart

Define your infrastructure environment following the examples in the 
[examples directory][examples-dir]. Then to create the environment:

[examples-dir]: https://github.com/germangh/humilis/tree/master/examples


````
humilis create example-environment.yml
````


And to delete it:

````
humilis delete example-environment.yml
````

For now you can't use humilis to update existing environments.


# Humilis environments

A `humilis` environment is just a collection of cloudformation stacks that
are required for an application. Instead of having a monolytic CF template for
your complete application, `humilis` allows you to define infrastructure
_layers_ that are combined into an _environment_. Each `humilis` layer 
translates exactly into one CF template (therefore into one CF stack after
the layer is deployed).

Breaking a complex infrastructure environment into smaller layers has at least
two obvious advantages:

* __Easier to maintain__. It's easier to maintain a simple layer that contains
  just a bunch of [CF resources][cf-resource] than serve a well-defined
  purpose.

* __Easier to reuse__. You should strive to define your infrastructure
  layers in such a way that you can reuse them across various environments. For
  instance, many projects may require a base layer that defines a VPC, a few
  subnets, a gateway and some routing tables, and maybe a (managed) NAT. You
  can define a humilis layer with those resources and have a set of layer
  parameters (e.g. the VPC CIDR) that will allow you to easily reuse it across
  environments.

[cf-resource]: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-template-resource-type-ref.html


## Environment anatomy

An environment _definition file_ is a [yaml][yaml] document that specifies the
list of layers that form your enviroment. The file should be named as your 
environment. That is, for environment `my-app-environment` the environment 
description file should be called `my-app-environment.yaml`. The contents of 
the environment definition should be organized as follows:

[yaml]: https://en.wikipedia.org/wiki/YAML

```yaml
---
my-app-environment:
    description:
        A description of what this environment is for
    layers:
        # The layers that you environment requires. They will be deployed in the
        # same order as you list them. Note that you can also pass parameters 
        # to a layer (more on that later).
        - {layer: name_of_first_layer, layer_param: layer_value}
        - {layer: name_of_second_layer}
        - {layer: name_of_third_layer}
```

## Layer anatomy

Anything associated to a given layer must be stored in a directory with the
same name as the layer, within the same directory where the environment
_definition file_ is located. If we consider the `my-app-environment` 
environment we used above then your directory tree should look like this:

```bash
.
├── my-app-environment.yaml
├── name_of_first_layer
│   ├── meta.yaml
│   └── resources.yaml
├── name_of_second_layer
│   ├── meta.json
│   └── meta.yaml
└── name_of_third_layer
    ├── resources.json.j2
    └── resources.yaml.j2
```

A layer must contain at least two files: 

* `meta.yaml`: Meta information about the layer such as a description,
  dependencies with other layers, and layer parameters.
* `resources.yaml`: Basically a CF template with the resources that the layer
   contains.

Those two files can also be in `.json` format (`meta.json` and 
`resources.json`). Or you can add the extension `.j2` if you want the files to
be pre-processed with the [Jinja2][jinja2] template compiler.

[jinja2]: http://jinja.pocoo.org/

Below an example of how a layer `meta.yaml` may look like:

```yaml
---
meta:
    description:
        Creates a VPC, that's it
    parameters:
        vpc_cidr:
            description: The CIDR block of the VPC
            value: 10.0.0.0/16
```

Above we declare only one layer parameter: `vpc_cidr`. `humilis` will make pass
that parameter to Jinja2 when compiling any template contained in the layer. So
the `resources.yaml.j2` for that same layer may look like this:

```yaml
---
resources:
    VPC:
        Type: "AWS::EC2::VPC"
        Properties:
            CidrBlock: {{ vpc_cidr }}
```


# References

You can use references in your `meta.yaml` files to refer to thing other than
resources within the same layer (to refer to resources within a layer you can
simply use Cloudformation's [Ref][cf-ref] or [GetAtt][cf-getatt] functions).
Humilis references are used by setting the value of a layer parameter to a dict
that has a `ref` key. Below an a `meta.yaml` that refers to a resource (with
a logical name `VPC`) that is contained in another layer (called `vpc_layer`):

```yaml
---
meta:
    description:
        Creates an EC2 instance in the vpc created by the vpc layer
    dependencies:
        - vpc
    parameters:
        vpc:
            description: Physical ID of the VPC where the instance will be created
            value:
                ref: 
                    parser: layer
                    parameters:
                        layer_name: vpc_layer
                        resource_name: VPC
```

Every reference must have a `parser` key that identifies the parser that
should be used to parse the reference. The optional key `parameters` allows
you to pass parameters to the reference parser. You can pass either named
parameters (as a dict) or positional arguments (as a list). More information
on reference parsers below.


[cf-ref]: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-ref.html
[cf-getatt]: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html


## Available reference parsers

### `layer` references

`layer` references allow you to refer to the physical ID of a resource that is 
part of another layer. For instance, consider the following environment
definition:

```yaml
---
my-environment:
    description:
        Creates a VPC with a NAT in the public subnet
    layers:
        - {layer: vpc}
        - {layer: nat}
```

Obviously the `nat` layer that takes care of deploying the NAT in the public
subnet will need to know the physical ID of that subnet. You achieve this by
declaring a `layer` reference in the `meta.yaml` for the  `nat` layer:

```yaml
---
meta:
    description:
        Creates a managed NAT in the public subnet of the NAT layer
    parameters:
        subnet_id:
            description:
                The physical ID of the subnet where the NAT will be placed
            value:
                ref:
                    parser: layer
                    parameters:
                        layer_name: vpc
                        # The logical name of the subnet in the vpc layer
                        resource_name: PublicSubnet
```

When parsing `meta.yaml` humilis will replace this:

```yaml
ref:
    parser: layer
    parameters:
        layer_name: vpc
        # The logical name of the subnet in the vpc layer
        resource_name: PublicSubnet
```

with the physical ID you need (something like `subnet-bafa90cd`). You can then
use this physical ID in the `resources.yaml.j2` section of the `nat` layer:

```jinja2
{# Pseudo-content of layers/nat/resources.yaml.j2 #}
resources:
    {# An Elastic IP reservation that will be associated to the NAT #}
    NatEip:
      Type: 'AWS::EC2::EIP'
      Properties: {}
    {# Custom resource deploying the NAT #}
    NatGateway:
      Type: 'Custom::NatGateway',
      Properties:
        {# The ARN of the Lambda function backing the custom resource #}
        ServiceToken: 'arn:aws:lambda:eu-west-1:XXXX:function:CreateNatGateway'
        {# Here we use the subnet_id reference defined in meta.yaml #}
        SubnetId: {{subnet_id}}
        AllocationId:
            Ref: NatEip
```


### `output` references

`output` references allow you to refer to outputs produced by another layer. 

__Parameters__:

* `layer_name`: The name of the layer you are referring to
* `output_name`: The logical name of the output parameter

In general you should prefer using `output` references over `layer` references.
The output parameters produced by a layer define an informal _layer interface_
that is more likely to remain constant than the logical names of resources
within a layer.

### `boto3` references

`boto3` references define arbitrary calls to [boto3facade][boto3facade]. The 
latter is just a simpler facade interface on top of [boto3][boto3].

[boto3]: https://github.com/boto/boto3
[boto3facade]: https://github.com/InnovativeTravel/boto3facade


__Parameters__:

* `service`: The AWS service, e.g. `ec2` or `cloudformation`. Note that only
  only AWS services that have a facade in [boto3facade][boto3facade] are 
  supported.
* `call`: The corresponding facade method, e.g. `get_ami_by_name`. The value of
  this parameter must be a dictionary with a `method` key (the name of the
  facade method to invoke) and an optional `args` key (the parameters to pass to
  the facade method). Best to look at the example below to understand how this
  works.
* `output_attribute`: Optional. If provided the reference parser will return the
  value of this attribute from the object returned by the facade method.

Below an example of a layer that uses a `boto3` reference:

```yaml
---
meta:
    description:
        Creates an EC2 instance using a named AMI
    # More stuff omitted for brevity
    ami:
        description: The AMI to use when launching the EC2 instance
        value:
            ref:
                parser: boto3
                parameters:
                    service: ec2
                    call:
                        method: get_ami_by_name
                        args:
                            - test-ami
                    output_attribute: id
```

`humilis` will parse the reference using this code:

```python
# Import the Ec2 facade
from boto3facade.ec2 import Ec2

# Create a facade object
ec2_facade = Ec2()

# Make the call
ami = ec2_facade.get_ami_by_name('test-ami')

# Extract the requested attribute
ref_value = ami.id
```


## `file` references

`file` references allow you to refer to a local file. The file will be uploaded
to S3 and the reference will evaluate to the corresponding S3 path.

__Parameters__:

* `path`: The path to the file, relative to the layer root directory.


### `lambda` references

`lambda` references allow you to refer to some Python code in your local 
machine. If your code follows some simple conventions `humilis` will take care
of building a [deployment package][aws-lambda-deploy] for you, uploading it
to S3, and the reference will evaluate to the S3 path of the deployment 
package.

[aws-lambda-deploy]: http://docs.aws.amazon.com/lambda/latest/dg/lambda-python-how-to-create-deployment-package.html

__Parameters__:

* `path`: Path to either a completely self-contained `.py` file, or to the root
  directory of your lambda code. In the latter case your code needs to follow
  some simple conventions for this to work. More information below.


__Example__:

```yaml
ref: 
    parser: lambda
    parameters:
        # Path to the root directory containing your lambda code
        path: dummy_function
```

which will evaluate to a S3 path such as:

```
s3://[bucket_name]/[environment_name]/[stage_name]/[func_name]-[commithash].zip
```


__Code conventions__:

Following the example above, the contents of the layer responsible of deploying
the `dummy_function` lambda may look like this:

```
.
├── dummy_function
│   ├── dummy_function.py
│   └── setup.py
├── meta.yaml
├── outputs.yaml.j2
└── resources.yaml.j2
```

Basically all your code needs to be included under directory `dummy_function`.
In this case there is only one file: `dummy_function.py`. External dependencies
need to be specified in your `setup.py`.
