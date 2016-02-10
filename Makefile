# create virtual environment
.env:
	virtualenv .env -p python3

# install all needed for development
develop: .env
	.env/bin/pip install -r requirements.txt
	.env/bin/pip install -e .

# run unit tests
test: develop
	.env/bin/py.test -x tests/unit/

# clean the development envrironment
clean:
	-rm -rf .env

pypi:
	.env/bin/python setup.py sdist upload
