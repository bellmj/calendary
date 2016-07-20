#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Update encrypted deploy password in Travis config file
"""


from __future__ import print_function
import base64
import json
import os
from getpass import getpass
import yaml
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15


try:
    from urllib import urlopen
except:
    from urllib.request import urlopen


GITHUB_REPO = 'davidhickman/calendary'
TRAVIS_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '.travis.yml')


def load_key(pubkey):
    """Load public RSA key, with work-around for keys using
    incorrect header/footer format.

    Read more about RSA encryption with cryptography:
    https://cryptography.io/latest/hazmat/primitives/asymmetric/rsa/
    """
    try:
        return load_pem_public_key(pubkey.encode(), default_backend())
    except ValueError:
        # workaround for https://github.com/travis-ci/travis-api/issues/196
        pubkey = pubkey.replace('BEGIN RSA', 'BEGIN').replace('END RSA', 'END')
        return load_pem_public_key(pubkey.encode(), default_backend())


def encrypt(pubkey, password):
    """Encrypt password using given RSA public key and encode it with base64.

    The encrypted password can only be decrypted by someone with the
    private key (in this case, only Travis).
    """
    key = load_key(pubkey)
    encrypted_password = key.encrypt(password, PKCS1v15())
    return base64.b64encode(encrypted_password)


def fetch_public_key(repo):
    """Download RSA public key Travis will use for this repo.

    Travis API docs: http://docs.travis-ci.com/api/#repository-keys
    """
    keyurl = 'https://api.travis-ci.org/repos/{0}/key'.format(repo)
    data = json.loads(urlopen(keyurl).read().decode())
    if 'key' not in data:
        errmsg = "Could not find public key for repo: {}.\n".format(repo)
        errmsg += "Have you already added your GitHub repo to Travis?"
        raise ValueError(errmsg)
    return data['key']


def prepend_line(filepath, line):
    """Rewrite a file adding a line to its beginning.
    """
    with open(filepath) as f:
        lines = f.readlines()

    lines.insert(0, line)

    with open(filepath, 'w') as f:
        f.writelines(lines)


def load_yaml_config(filepath):
    with open(filepath) as f:
        return yaml.load(f)


def save_yaml_config(filepath, config):
    with open(filepath, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)


def update_travis_deploy_password(encrypted_password):
    """Update the deploy section of the .travis.yml file
    to use the given encrypted password.
    """
    config = load_yaml_config(TRAVIS_CONFIG_FILE)

    config['deploy']['password'] = dict(secure=encrypted_password)

    save_yaml_config(TRAVIS_CONFIG_FILE, config)

    line = ('# This file was autogenerated and will overwrite'
            ' each time you run travis_pypi_setup.py\n')
    prepend_line(TRAVIS_CONFIG_FILE, line)


def main(args):
    public_key = fetch_public_key(args.repo)
    password = args.password or getpass('PyPI password: ')
    update_travis_deploy_password(encrypt(public_key, password.encode()))
    print("Wrote encrypted password to .travis.yml -- you're ready to deploy")


if '__main__' == __name__:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default=GITHUB_REPO,
                        help='GitHub repo (default: %s)' % GITHUB_REPO)
    parser.add_argument('--password',
                        help='PyPI password (will prompt if not provided)')

    args = parser.parse_args()
    main(args)
