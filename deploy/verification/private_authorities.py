#!/usr/bin/env python3
"""Run inside the private staging boundary with an admitted proof workload.

Checks live CP binding authority and IAM readiness. Does not synthesize runtime
profiles, maker/checker approval, identity mappings or successful browser login.
"""
import datetime
import hashlib
import http.client
import json
import os
import pathlib
import re
import ssl
import stat
import sys
import urllib.parse


def protected(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_size > 65536:
            raise ValueError('unprotected proof material')
        return stream.read(65537)


def endpoint(origin, namespace):
    parsed = urllib.parse.urlsplit(origin)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/') or not parsed.hostname.endswith('.' + namespace):
        raise ValueError('private authority origin required')
    return parsed


def request(origin, namespace, context, path, token=None, body=None):
    address = endpoint(origin, namespace)
    connection = http.client.HTTPSConnection(address.hostname, address.port or 443, timeout=5, context=context)
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        connection.request('POST' if body is not None else 'GET', path, None if body is None else json.dumps(body).encode(), headers)
        response = connection.getresponse()
        raw = response.read(65537)
        if len(raw) > 65536 or response.status not in (200, 204):
            raise ValueError('authority denied')
        if body is not None and response.getheader('Content-Type', '').split(';')[0] != 'application/json':
            raise ValueError('unexpected authority response')
        return raw
    finally:
        connection.close()


def validate_binding(response, expected, now):
    binding, scope = expected['binding'], expected['scope']
    if response['ProviderID'] != binding['provider_id'] or response['EngineInstanceID'] != binding['engine_instance_id'] or response['Scope'] != {'OrganisationID': scope['organisation_id'], 'EstateID': scope['estate_id']}:
        raise ValueError('canonical binding drift')
    if any(response[key] != 'ACTIVE' for key in ('ProviderStatus', 'InstanceStatus', 'BindingStatus')):
        raise ValueError('inactive platform identity')
    if response['RuntimeCapability'] != expected['runtime_capability'] or response['SupportStatus'] != 'VERIFIED' or response['ProfileRevision'] < 1:
        raise ValueError('runtime capability unverified')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', response['ArtifactDigest']) or response['ArtifactDigest'] != response['DeployedArtifactDigest']:
        raise ValueError('runtime artifact drift')
    until = datetime.datetime.fromisoformat(response['EvidenceExpiresAt'].replace('Z', '+00:00'))
    if until <= now:
        raise ValueError('expired runtime profile')


def main(config_path, output):
    config = json.loads(protected(config_path))
    token = protected(config['cp_token_file']).decode('ascii').strip()
    if not token or any(ord(char) <= 32 or ord(char) >= 127 for char in token):
        raise ValueError('invalid workload credential')
    context = ssl.create_default_context(cadata=protected(config['ca_file']).decode('ascii'))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    protected(config['client_certificate_file'])
    protected(config['client_key_file'])
    context.load_cert_chain(config['client_certificate_file'], config['client_key_file'])
    raw = request(config['cp_origin'], config['namespace'], context, '/internal/federation/v1/binding', token, config['binding_request'])
    response = json.loads(raw)
    now = datetime.datetime.now(datetime.timezone.utc)
    validate_binding(response, config['binding_request'], now)
    if response['ArtifactDigest'] != config['observed_keycloak_digest']:
        raise ValueError('profile does not describe observed Keycloak image')
    request(config['iam_origin'], config['namespace'], context, '/ready')
    evidence = {'schema': 'baobab.staging-authority-probe.v1', 'observed_at': now.isoformat(), 'cp_binding_sha256': hashlib.sha256(raw).hexdigest(), 'profile_revision': response['ProfileRevision'], 'artifact_digest': response['ArtifactDigest'], 'iam_ready': True, 'browser_login_proven': False, 'operational_acceptance': False}
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(evidence, stream, indent=2)
        stream.write('\n')

if __name__ == '__main__':
    try:
        if len(sys.argv) != 3:
            raise ValueError('protected config and evidence output required')
        main(sys.argv[1], sys.argv[2])
    except (ValueError, KeyError, TypeError, OSError, ssl.SSLError, http.client.HTTPException):
        print('private staging authority proof denied', file=sys.stderr)
        sys.exit(1)
