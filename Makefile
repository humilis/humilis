PIP := .env/bin/pip
TOX := .env/bin/detox
PYTHON := .env/bin/python

# create Python virtualenv
.env:
	virtualenv .env -p python3

# install all needed for development
develop: .env
	$(PIP) install -r requirements-dev.txt detox

# run unit tests
test: .env
	$(PIP) install detox
	$(TOX) -e unit --recreate

# clean the development envrironment
clean:
	-rm -rf .env .tox

pypi:
	$(PYTHON) setup.py sdist upload
