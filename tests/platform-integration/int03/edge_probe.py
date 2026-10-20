#!/usr/bin/env python3
"""Uncredentialed, finite diagnostics for a failed private INT-03 IAM preflight.

Never a qualification: only the verified-TLS path may supply identity evidence.
The direct loopback-network HTTP observation helps isolate edge/DNS faults,
and never conveys tokens, response bodies, host addresses or private paths.
"""
import json
import os
import socket
import ssl
import urllib.error
import urllib.request

PATH = '/realms/master/.well-known/openid-configuration'
EXPECTED = 'https://iam.int02.test/realms/master'
ALLOWED = {'DNS_ERROR', 'CONNECT_ERROR', 'TLS_ERROR', 'HTTP_200', 'HTTP_301',
           'HTTP_302', 'HTTP_400', 'HTTP_401', 'HTTP_403', 'HTTP_404',
           'HTTP_421', 'HTTP_502', 'HTTP_503', 'HTTP_504', 'INVALID_RESPONSE',
           'ISSUER_MISMATCH', 'UNKNOWN'}
context = ssl.create_default_context(cafile=os.environ['L4_CA_FILE'])
context.minimum_version = ssl.TLSVersion.TLSv1_3


def check(host, url, verified):
    try:
        socket.getaddrinfo(host, 443 if verified else 8080, type=socket.SOCK_STREAM)
    except OSError:
        return 'DNS_ERROR'
    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=5, context=context if verified else None) as response:
            status = response.status
            raw = response.read(16385)
    except ssl.SSLError:
        return 'TLS_ERROR'
    except urllib.error.HTTPError as error:
        status = error.code
        raw = b''
    except (OSError, ValueError):
        return 'CONNECT_ERROR'
    if status != 200:
        marker = 'HTTP_' + str(status)
        return marker if marker in ALLOWED else 'UNKNOWN'
    try:
        obj = json.loads(raw)
        if len(raw) > 16384 or type(obj) is not dict:
            return 'INVALID_RESPONSE'
        if obj.get('issuer') != EXPECTED:
            return 'ISSUER_MISMATCH'
        return 'HTTP_200'
    except (ValueError, UnicodeError):
        return 'INVALID_RESPONSE'


observed = {
    'iam_tls_edge': check('iam.int02.test', 'https://iam.int02.test' + PATH, True),
    'iam_private_upstream': check('keycloak', 'http://keycloak:8080' + PATH, False),
}
print(json.dumps(observed, sort_keys=True))
