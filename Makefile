PIP := .env/bin/pip
TOX := .env/bin/tox
PYTHON := .env/bin/python
TWINE := .env/bin/twine

# create Python virtualenv
.env:
	virtualenv .env -p python3

# install all needed for development
develop: .env
	$(PIP) install -r requirements-dev.txt tox

# run unit tests
test: .env
	$(PIP) install tox
	$(TOX)

# run integration tests
testi: .env
	$(PIP) install tox
	$(TOX) -e integration

# clean the development envrironment
clean:
	rm -rf .env .tox
	rm -rf tests/__pycache__ tests/unit/__pycache__ tests/integration/__pycache__
	rm -rf humilis/__pycache__
	rm -rf .pytest_cache


pypi: develop
	$(PYTHON) setup.py sdist
	$(TWINE) upload dist/*
