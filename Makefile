PIP := .env/bin/pip
TOX := .env/bin/tox
PYTHON := .env/bin/python

# create Python virtualenv
.env:
	virtualenv .env -p python3

# install all needed for development
develop: .env
	$(PIP) install -r requirements-dev.txt tox

# run unit tests
test: .env
	$(PIP) install tox
	$(TOX) -e unit

# run integration tests
testi: .env
	$(PIP) install tox
	$(TOX) -e integration

# clean the development envrironment
clean:
	-rm -rf .env .tox

pypi:
	$(PYTHON) setup.py sdist upload
