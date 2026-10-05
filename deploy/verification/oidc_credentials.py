#!/usr/bin/env python3
"""GitHub's job OIDC token -> bounded staging role. No stored AWS access keys."""
import http.client
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.parse


def credentials(environ, request_token=None, command=None):
    account, role = environ['STAGING_ACCOUNT_ID'], environ['STAGING_ROLE_ARN']
    if not re.fullmatch(r'[0-9]{12}', account) or not re.fullmatch('arn:aws:iam::' + account + r':role/[A-Za-z0-9_/+=,.@-]+', role):
        raise ValueError('invalid staging role')
    address = urllib.parse.urlsplit(environ['ACTIONS_ID_TOKEN_REQUEST_URL'])
    if address.scheme != 'https' or address.username or address.fragment or address.port not in (None, 443) or not address.hostname.endswith('.actions.githubusercontent.com'):
        raise ValueError('untrusted job token endpoint')
    query = urllib.parse.parse_qsl(address.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key != 'audience'] + [('audience', 'sts.amazonaws.com')]
    path = address.path + '?' + urllib.parse.urlencode(query)
    if request_token is None:
        connection = http.client.HTTPSConnection(address.hostname, timeout=10)
        try:
            connection.request('GET', path, headers={'Authorization': 'Bearer ' + environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
            response = connection.getresponse()
            raw = response.read(16385)
            if response.status != 200 or len(raw) > 16384:
                raise ValueError('job token denied')
            token = json.loads(raw)['value']
        finally:
            connection.close()
    else:
        token = request_token(path)
    if not isinstance(token, str) or len(token) > 16384 or len(token.split('.')) != 3:
        raise ValueError('invalid job token')
    with tempfile.NamedTemporaryFile(mode='w') as stream:
        os.chmod(stream.name, 0o600)
        stream.write(token); stream.flush()
        args = ['aws', '--region', 'af-south-1', '--no-cli-pager', '--no-sign-request', 'sts', 'assume-role-with-web-identity', '--role-arn', role, '--role-session-name', 'staging-' + environ['GITHUB_RUN_ID'], '--web-identity-token', 'file://' + stream.name, '--duration-seconds', '3600', '--output', 'json']
        if command is None:
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            if result.returncode:
                raise ValueError('staging role denied')
            value = json.loads(result.stdout)
        else:
            value = command(args)
    if value['AssumedRoleUser']['Arn'].split(':')[4] != account:
        raise ValueError('assumed wrong account')
    result = { 'AWS_ACCESS_KEY_ID': value['Credentials']['AccessKeyId'], 'AWS_SECRET_ACCESS_KEY': value['Credentials']['SecretAccessKey'], 'AWS_SESSION_TOKEN': value['Credentials']['SessionToken'], 'AWS_REGION': 'af-south-1', 'AWS_DEFAULT_REGION': 'af-south-1' }
    if any(not isinstance(item, str) or '\n' in item or '\r' in item for item in result.values()):
        raise ValueError('invalid credentials')
    return result


def main():
    if os.environ.get('GITHUB_REF') != 'refs/heads/main' or os.environ.get('GITHUB_REPOSITORY') != 'baobab-platform/infrastructure':
        raise ValueError('unreviewed deployment context')
    result = credentials(os.environ)
    for key in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN'):
        print('::add-mask::' + result[key])
    with open(os.environ['GITHUB_ENV'], 'a', encoding='utf-8') as stream:
        for key, value in result.items(): stream.write(key + '=' + value + '\n')

if __name__ == '__main__':
    try: main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError, http.client.HTTPException):
        print('staging OIDC role exchange denied', file=sys.stderr)
        sys.exit(1)
