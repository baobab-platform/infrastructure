"""Private real-provider probes. No credential or HTTP body is printed."""
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path('/run/dev01')
ISSUER = 'https://iam.baobab-dev.test/realms/baobab'
TLS = ssl.create_default_context(cafile='/tls/ca.pem')
TLS.minimum_version = ssl.TLSVersion.TLSv1_3


def request(method, url, data=None, token=None, form=False):
    body = (urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None
    headers = {'Accept': 'application/json'}
    if body:
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, body, headers, method=method)
    try:
        with urllib.request.urlopen(req, context=TLS, timeout=8) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError('BOUNDED_RESPONSE')
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        return error.code, None


def require(ok):
    if not ok:
        raise ValueError("PROVIDER_OBSERVATION_FAILED")


def subjects():
    code, auth = request('POST', 'https://iam.baobab-dev.test/realms/master/protocol/openid-connect/token',
                         {'client_id': 'admin-cli', 'grant_type': 'password', 'username': 'dev01-admin',
                          'password': os.environ['DEV01_ADMIN_PASSWORD']}, form=True)
    require(code == 200 and auth['access_token'])
    ids = {}
    for role in ('maker', 'checker'):
        username = 'synthetic-dev01-' + role + '-' + os.environ['DEV01_RUN_ID']
        user = {'username': username, 'enabled': True, 'emailVerified': True,
                'email': username + '@example.invalid',
                'credentials': [{'type': 'password', 'value': secrets.token_urlsafe(32), 'temporary': False}]}
        code, _ = request('POST', 'https://iam.baobab-dev.test/admin/realms/baobab/users', user, auth['access_token'])
        require(code == 201)
        code, actual = request('GET', 'https://iam.baobab-dev.test/admin/realms/baobab/users?' +
                               urllib.parse.urlencode({'username': username, 'exact': 'true'}), token=auth['access_token'])
        require(code == 200 and len(actual) == 1 and actual[0]['username'] == username and actual[0]['enabled'] is True)
        ids[role] = actual[0]['id']
    require(ids['maker'] != ids['checker'])
    # The host owner UID is used for this probe; no chmod of private host state.
    fd = os.open(ROOT / 'subjects.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(ids, out)
        out.flush()
        os.fsync(out.fileno())
    print('PROVIDER_SUBJECTS_OBSERVED')


def health():
    code, body = request('GET', ISSUER + '/.well-known/openid-configuration')
    require(code == 200 and body['issuer'] == ISSUER)
    code, _ = request('GET', 'https://cp.baobab-dev.test/healthz')
    require(code == 200)
    print('REAL_IAM_CP_HEALTH_OBSERVED')


try:
    if sys.argv[1] == 'subjects':
        subjects()
    elif sys.argv[1] == 'health':
        health()
    else:
        raise ValueError('UNKNOWN_PROBE')
except Exception:
    # HTTP errors can contain bearer material and private routes: fixed code only.
    raise SystemExit('DEV01_PROVIDER_PROBE_FAILED')
