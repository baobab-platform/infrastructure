"""Supplemental native HTTP component proof; never an INT-05 replacement."""
import re
from urllib.parse import urlsplit, parse_qs

ORIGIN = 'https://rp.baobab-dev.test'
CALLBACK = ORIGIN + '/api/iam/callback'
BFF = 'baobab-dev-zuribeans-bff'
CHECKS = {'native-next-iam-session', 'current-cp-trade-http-context', 'csrf-denial',
          'wrong-organisation-denial', 'membership-suspension-denial',
          'custody-outage-and-recovery', 'issuer-consent-revocation', 'native-fixture-cleanup'}
SOURCES = {'shared', 'baobab-cp', 'baobab-iam', 'baobab-trade', 'zuribeans'}
HTTP_HOPS = {'IAM_DISCOVERY', 'IAM_TOKEN', 'IAM_INTROSPECTION', 'IAM_JWKS',
             'CP_PRINCIPAL', 'CP_ESTATE', 'CP_CONTEXT', 'TRADE_CONTEXT'}


def http_status_diagnostics(raw):
    """Release only finite hop labels/statuses, never paths, queries or bodies."""
    result = []
    for line in raw.splitlines()[-64:]:
        match = re.fullmatch(r'([A-Z_]+) ([1-5][0-9]{2}) ([1-5][0-9]{2}|-)', line)
        if match and match[1] in HTTP_HOPS:
            result.append('DEV07_BFF_HTTP_HOP=' + match[1] + ':' + match[2] + ':UPSTREAM_' +
                          ('NONE' if match[3] == '-' else match[3]))
    return result


def authorization(url):
    """Validate the actual BFF-generated request, retaining its state/PKCE.

    This function generates no verifier, state, nonce, code or token.
    """
    def require(ok):
        if not ok:
            raise ValueError('DEV07_BFF_AUTHORIZATION_REFUSED')
    require(type(url) is str)
    u = urlsplit(url)
    require(u.scheme == 'https' and u.netloc == 'hydra.int03.test'
            and u.path == '/oauth2/auth' and not u.fragment)
    q = parse_qs(u.query, strict_parsing=True, keep_blank_values=True)
    require(set(q) == {'client_id', 'response_type', 'redirect_uri', 'scope', 'state',
                       'nonce', 'code_challenge', 'code_challenge_method', 'audience'})
    require(all(len(v) == 1 for v in q.values()))
    expected = {'client_id': BFF, 'response_type': 'code', 'redirect_uri': CALLBACK,
                'scope': 'openid trade:buy', 'audience': 'baobab-trade',
                'code_challenge_method': 'S256'}
    require(all(q[k] == [v] for k, v in expected.items()))
    require(all(re.fullmatch(r'[A-Za-z0-9_-]{43}', q[k][0])
                for k in ('state', 'nonce', 'code_challenge')))
    return q['state'][0]


def fresh(run, sources):
    return {'schema': 'infrastructure.dev07-bff-http-component.v1', 'run_id': run,
            'sources': sources, 'checks': {key: False for key in sorted(CHECKS)},
            'bff_http_qualified': False, 'int05_qualified': False,
            'provider_qualified': False, 'protected_acceptance': False,
            'production_authorized': False}


def validate(value, run, sources):
    expected = fresh(run, sources)
    if (not isinstance(value, dict) or set(value) != set(expected)
            or value['schema'] != expected['schema'] or value['run_id'] != run
            or not re.fullmatch(r'[0-9a-f]{32}', run)
            or value['sources'] != sources or set(sources) != SOURCES
            or any(not re.fullmatch(r'[0-9a-f]{40}', s) for s in sources.values())
            or not isinstance(value['checks'], dict)
            or set(value['checks']) != CHECKS
            or any(type(v) is not bool for v in value['checks'].values())
            or any(value[k] is not False for k in expected if k.endswith('_qualified')
                   or k in ('protected_acceptance', 'production_authorized'))):
        raise ValueError('DEV07_BFF_COMPONENT_RECEIPT_REFUSED')
    return value
