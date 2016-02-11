# create virtual environment
.env:
	virtualenv .env -p python3

# install all needed for development
develop: .env
	.env/bin/pip install -e . -r requirements.txt

# run unit tests
test: develop
	.env/bin/tox

# clean the development envrironment
clean:
	-rm -rf .env .tox

pypi:
	.env/bin/python setup.py sdist upload
