import sys
from setuptools import setup, find_packages

CURRENT_PYTHON = sys.version_info[:2]
REQUIRED_PYTHON = (3, 6)

# This check and everything above must remain compatible with Python 2.7.
if CURRENT_PYTHON < REQUIRED_PYTHON:
    sys.stderr.write("""
==========================
Unsupported Python version
==========================
This version of hkex-lib requires Python {}.{}, but you're trying to
install it on Python {}.{}.
This may be because you are using a version of pip that doesn't
understand the python_requires classifier. Make sure you
have pip >= 9.0 and setuptools >= 24.2, then try again:
    $ python -m pip install --upgrade pip setuptools
    $ python -m pip install pip3 install git+ssh://git@gitlab.com/hkex-vep/hkex-api.git#egg=hkex
""".format(*(REQUIRED_PYTHON + CURRENT_PYTHON)))
    sys.exit(1)

setup(name="pygdrive", 
      version='0.2.1',
      packages=find_packages(),
      python_requires='>={}.{}'.format(*REQUIRED_PYTHON),
      install_requires=[
          'google-auth-oauthlib',
          'google-api-python-client',
          'google-auth-oauthlib',
          'python-magic'
      ],
      tests_require=[
          'pytest>=5.0.0',
      ]
)