# humilis
Helps you deploy AWS infrastructure.


Build status
----------------------------------
[![Circle CI](https://circleci.com/gh/germangh/humilis/tree/master.svg?style=svg)](https://circleci.com/gh/germangh/humilis/tree/master)

This project is based on the
[cumulus](https://github.com/germangh/cumulus/blob/master/cumulus/__init__.py).
project. See [CUMULUS_LICENSE][cumulus_license] for license information.

[cumulus]: https://github.com/cotdsa/cumulus
[cumulus_license]: https://github.com/germangh/humilis/blob/master/CUMULUS_LICENSE


Installation
----------------------------------

Run this in a terminal:

````
pip install git+https://github.com/germangh/humilis
````


Quickstart
----------------------------------

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

