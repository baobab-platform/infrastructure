"""Private driver for actual Next -> IAM/Redis -> native Trade HTTP -> CP.

No token is extracted from BFF custody, constructed, signed or exported.
The owner completes actual native Kratos/Hydra challenges for synthetic people.
"""
from http.cookiejar import CookieJar
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import native_probe as p
import buyer_bff_contract as c
from buyer_identity_probe import client_auth


def stage(name):
    p.require(name in {'HEALTH', 'LOGIN', 'CALLBACK', 'SESSION', 'CONTEXT', 'CSRF',
                       'FOREIGN', 'SUSPENDED', 'CUSTODY', 'RECOVERY', 'REVOCATION'})
    print('DEV07_BFF_HTTP_STAGE=' + name, flush=True)


def checkpoint(value):
    c.validate(value, os.environ['DEV01_RUN_ID'], p.read('bff-source-pins.json'))
    path = p.ROOT / '.bff-report.tmp'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(value, out); out.flush(); os.fsync(out.fileno())
    os.replace(path, p.ROOT / 'bff-report.json')


def observed(name):
    pins = p.read('bff-source-pins.json')
    report = p.read('bff-report.json') if (p.ROOT / 'bff-report.json').exists() else c.fresh(os.environ['DEV01_RUN_ID'], pins)
    p.require(name in c.CHECKS)
    report['checks'][name] = True
    checkpoint(report)


def http(method, path, body=None, headers=None, opener=None):
    # Only this source-owned RP origin receives opaque browser custody/CSRF.
    p.require(path.startswith('/') and not path.startswith('//') and '#' not in path)
    url = c.ORIGIN + path
    h = {'Origin': c.ORIGIN, 'Sec-Fetch-Site': 'same-origin', **(headers or {})}
    raw = json.dumps(body).encode() if body is not None else None
    if raw is not None:
        h['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, raw, h, method=method)
    client = opener or urllib.request.build_opener(p.NoRedirect(), urllib.request.HTTPSHandler(context=p.TLS))
    try:
        response = client.open(request, timeout=12)
    except urllib.error.HTTPError as error:
        response = error
    data = response.read(65537)
    p.require(len(data) <= 65536, 'DEV07_BFF_RESPONSE_BOUND')
    return response.status, data, response.headers


def session():
    return http('GET', '/api/iam/session', headers={'Cookie': p.read('bff-browser.json')['cookie']})


def buyer(organisation=None, csrf=None):
    browser = p.read('bff-browser.json'); fixture = p.read('buyer-fixture.json')
    return http('POST', '/api/buyer/context', {
        'organisationId': organisation or fixture['organisation_id'], 'countryCode': 'UG',
        'csrfToken': csrf or browser['csrf']}, headers={'Cookie': browser['cookie']})


def positive():
    stage('CONTEXT')
    native = p.read('native.json'); fixture = p.read('buyer-fixture.json')
    fields, basic = client_auth(native, 'baobab-dev-trade-buyer-validator')
    code, token, _ = p.request('POST', p.ISSUER + '/oauth2/token', {
        'grant_type': 'client_credentials', 'scope': 'context:resolve',
        'audience': 'baobab-control-plane', **fields}, form=True, basic=basic)
    p.require(code == 200 and token.get('access_token'), 'DEV07_BFF_CP_CALLER_REQUIRED')
    code, cp, _ = p.request('POST', p.CP + '/v1/platform-context/resolve', {
        'tenant_id': fixture['tenant_id'], 'organisation_id': fixture['organisation_id'],
        'country_code': 'UG'}, token['access_token'])
    p.require(code == 200 and cp.get('market_id') and cp.get('country_code') == 'UG', 'DEV07_BFF_CP_CURRENT_REQUIRED')
    code, raw, headers = buyer()
    print('DEV07_BFF_HTTP_REPLY=CONTEXT:' + str(code), flush=True)
    p.require(code == 200 and 'no-store' in headers.get('Cache-Control', ''), 'DEV07_BFF_CONTEXT_DENIED')
    result = json.loads(raw)
    p.require(set(result) == {'buyer'} and set(result['buyer']) == {'organisationId', 'marketId', 'roles', 'expiresAt'})
    summary = result['buyer']
    p.require(summary['organisationId'] == fixture['organisation_id'] and summary['marketId'] == cp['market_id']
              and summary['roles'] == ['BUYER'] and time.time()*1000 < summary['expiresAt'] <= p.read('bff-browser.json')['expires'],
              'DEV07_BFF_SCOPE_OR_LIFETIME_MISMATCH')
    observed('current-cp-trade-http-context')


def login():
    stage('LOGIN')
    jar = CookieJar()
    opener = urllib.request.build_opener(p.NoRedirect(), urllib.request.HTTPSHandler(context=p.TLS), urllib.request.HTTPCookieProcessor(jar))
    code, _, headers = http('POST', '/api/iam/login', {}, opener=opener)
    print('DEV07_BFF_HTTP_REPLY=LOGIN:' + str(code), flush=True)
    p.require(code == 303, 'DEV07_BFF_LOGIN_DENIED')
    url = headers.get('Location'); c.authorization(url)
    native = p.read('native.json')
    callback = p.native_human('maker', native, client_id=c.BFF, scope='openid trade:buy',
        audience='baobab-trade', callback=c.CALLBACK, authorization_url=url)
    stage('CALLBACK')
    target = urllib.parse.urlsplit(callback)
    p.require(target.scheme == 'https' and target.netloc == 'rp.baobab-dev.test' and target.path == '/api/iam/callback')
    code, raw, headers = http('GET', target.path + '?' + target.query, opener=opener)
    print('DEV07_BFF_HTTP_REPLY=CALLBACK:' + str(code), flush=True)
    p.require(code == 200 and b'code=' not in raw, 'DEV07_BFF_CALLBACK_DENIED')
    values = [x for x in jar if x.name == '__Host-zb-iam-session']
    p.require(len(values) == 1 and re.fullmatch(r'[A-Za-z0-9_-]{43}', values[0].value))
    cookie = values[0]
    p.require(cookie.secure and cookie.path == '/' and cookie.has_nonstandard_attr('HttpOnly')
              and cookie.get_nonstandard_attr('SameSite', '').lower() == 'strict')
    stage('SESSION')
    code, raw, headers = http('GET', '/api/iam/session', opener=opener)
    p.require(code == 200 and 'no-store' in headers.get('Cache-Control', ''), 'DEV07_BFF_SESSION_DENIED')
    value = json.loads(raw)
    p.require(set(value) == {'authenticated', 'expiresAt', 'csrfToken'} and value['authenticated'] is True
              and re.fullmatch(r'[A-Za-z0-9_-]{43}', value['csrfToken']) and value['expiresAt'] > time.time()*1000)
    p.write('bff-browser.json', {'cookie': cookie.name + '=' + cookie.value,
                              'csrf': value['csrfToken'], 'expires': value['expiresAt']})
    observed('native-next-iam-session')


def denied(action):
    stage({'csrf': 'CSRF', 'foreign': 'FOREIGN', 'suspended': 'SUSPENDED', 'custody': 'CUSTODY'}[action])
    fixture = p.read('buyer-fixture.json')
    if action == 'csrf':
        code, raw, _ = buyer(csrf='x'*43)
    elif action == 'foreign':
        code, raw, _ = buyer(organisation=fixture['other_organisation_id'])
    elif action == 'suspended':
        code, raw, _ = buyer()
    else:
        code, raw, _ = session()
    p.require(code == 401 and json.loads(raw) == {'code': 'AUTHENTICATION_UNAVAILABLE_OR_DENIED'}, 'DEV07_BFF_NEGATIVE_NOT_DENIED')
    if action == 'custody':
        p.write('bff-custody-outage.json', {'observed': True})
    else:
        observed({'csrf': 'csrf-denial', 'foreign': 'wrong-organisation-denial',
                  'suspended': 'membership-suspension-denial'}[action])


def revoke():
    stage('REVOCATION')
    browser = p.read('bff-browser.json'); native = p.read('native.json')
    p.require(session()[0] == 200 and browser['expires'] > time.time()*1000)
    subject = native['humans']['maker']['id']
    query = urllib.parse.urlencode({'subject': subject})
    code, before = p.api('GET', '/admin/oauth2/auth/sessions/consent?' + query)
    def own(rows):
        return isinstance(rows, list) and any(x.get('consent_request', {}).get('client', {}).get('client_id') == c.BFF for x in rows)
    p.require(code == 200 and own(before), 'DEV07_BFF_ISSUER_CONSENT_READBACK_REQUIRED')
    query = urllib.parse.urlencode({'subject': subject, 'client': c.BFF})
    p.require(p.api('DELETE', '/admin/oauth2/auth/sessions/consent?' + query)[0] == 204)
    code, after = p.api('GET', '/admin/oauth2/auth/sessions/consent?' + urllib.parse.urlencode({'subject': subject}))
    p.require(code == 200 and not own(after), 'DEV07_BFF_CONSENT_SURVIVED')
    p.require(browser['expires'] > time.time()*1000 and session()[0] == 401 and buyer()[0] == 401,
              'DEV07_BFF_REVOKED_SESSION_ACCEPTED')
    observed('issuer-consent-revocation')


def dev11_connected_trace():
    """Exercise real BFF -> IAM/CP -> Trade HTTP with verified private TLS.

    Run-owned trace IDs remain inside /run/dev01; only booleans leave the
    private runtime. The host separately checks real BFF/Trade service logs.
    """
    browser = p.read('bff-browser.json')
    fixture = p.read('buyer-fixture.json')
    trace = secrets.token_hex(16)
    upstream = secrets.token_hex(8)
    carrier = '00-' + trace + '-' + upstream + '-01'
    args = {'organisationId': fixture['organisation_id'], 'countryCode': 'UG',
            'csrfToken': browser['csrf']}
    request_headers = {'Cookie': browser['cookie'], 'traceparent': carrier}
    code, body, headers = http('POST', '/api/buyer/context', args, headers=request_headers)
    observed = headers.get('traceparent', '')
    valid = re.fullmatch(r'00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})', observed)
    positive = bool(code == 200 and valid and valid.group(1) == trace
                    and valid.group(2) != upstream and set(json.loads(body)) == {'buyer'})

    bad = {**args, 'csrfToken': 'x' * 43}
    denied_code, denied_body, denied_headers = http(
        'POST', '/api/buyer/context', bad, headers=request_headers)
    wrong = denied_headers.get('traceparent', '')
    wrong_span = re.fullmatch(r'00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})', wrong)
    csrf_denied = (denied_code == 401 and json.loads(denied_body) ==
                   {'code': 'AUTHENTICATION_UNAVAILABLE_OR_DENIED'} and
                   wrong_span is not None and wrong_span.group(1) == trace)

    no_custody, response, absent_headers = http(
        'POST', '/api/buyer/context', args, headers={'traceparent': carrier})
    missing_span = re.fullmatch(
        r'00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})',
        absent_headers.get('traceparent', ''))
    no_custody_denied = (no_custody == 401 and
                        json.loads(response) == {'code': 'AUTHENTICATION_UNAVAILABLE_OR_DENIED'}
                        and missing_span is not None and missing_span.group(1) == trace)
    p.write('dev11-trace-marker.json', {'trace': trace, 'upstream': upstream})
    print(json.dumps({
        'scope': 'NATIVE_NEXT_TRADE_HTTP_WITH_CURRENT_IAM_CP',
        'checks': {'dev11_bff_authorised_route_w3c': positive,
                   'dev11_bff_csrf_denied_w3c': csrf_denied,
                   'dev11_bff_missing_session_denied_w3c': no_custody_denied},
        'outbox_consumer_qualified': False, 'production_authorized': False,
    }, sort_keys=True))


def main(action):
    p.require(p.read('state.json').get('buyer_bff_http_profile') is True)
    if action == 'dev11-trace':
        dev11_connected_trace()
        return
    if action == 'health':
        result = {'trade': p.request('GET', 'https://engine.baobab-dev.test/health', timeout=3)[0],
                  'bff': http('GET', '/api/health')[0]}
        print(json.dumps(result)); return
    if action == 'login': login()
    elif action == 'positive': positive()
    elif action in ('csrf', 'foreign', 'suspended', 'custody'): denied(action)
    elif action == 'recovery':
        stage('RECOVERY'); p.require(p.read('bff-custody-outage.json') == {'observed': True})
        positive(); observed('custody-outage-and-recovery')
    elif action == 'revoke': revoke()
    else: raise ValueError('DEV07_BFF_UNKNOWN_ACTION')


if __name__ == '__main__':
    try: main(sys.argv[1])
    except Exception:
        raise SystemExit('DEV07_BFF_HTTP_NOT_OBSERVED') from None
