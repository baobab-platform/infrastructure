"""Closed HTTP metadata only. Never an authentication/qualification gate."""
import re

ROUTES = {'NAB_SIGN_IN', 'NAB_ACCOUNT', 'NAB_LOGIN', 'NAB_CALLBACK', 'NAB_SESSION',
          'NAB_LOGOUT', 'IAM_DISCOVERY', 'IAM_AUTH', 'IAM_LOGIN_ACTION', 'IAM_TOKEN',
          'IAM_INTROSPECT', 'IAM_JWKS', 'CP_SELF'}
LINE = re.compile(r'(?:[a-z0-9_.-]+\s+\|\s+)?INT03_HTTP ([A-Z_]+) (GET|POST|OTHER) ([1-5][0-9]{2})\Z')


def project(raw):
    if type(raw) is not str:
        return []
    result = []
    for line in raw.splitlines()[-256:]:
        match = LINE.fullmatch(line)
        if match and match[1] in ROUTES:
            result.append({'route': match[1], 'method': match[2], 'status': int(match[3])})
    return result[-32:]


def component(raw):
    """Retain the reused qualifier's already-scrubbed browser failure facts.

    A second finite allowlist prevents arbitrary exception values, URLs,
    identifiers or credentials from crossing this outer evidence boundary.
    """
    if type(raw) is not str:
        return {}
    result = {}
    stage = re.search(r'\bstep=human_proof stage=([a-z_]+)\b', raw)
    if stage and re.fullmatch(r'(startup|browser_launch|discovery|callback_exchange|unknown|'
                             r'login_(normal|state|nonce|pkce)(_(visit|form|username|password|submit|result|mfa))?)', stage[1]):
        result['browser_stage'] = stage[1]
    permitted = {'failure_class': {'Error', 'TimeoutError', 'TypeError', 'RuntimeError', 'AssertionError', 'ProtocolError', 'TargetClosedError', 'Other'},
        'host': {'IAM', 'RP', 'OTHER'}, 'path': {'AUTHORIZE', 'ACTION', 'CALLBACK', 'OTHER'},
        'type': {'HTML', 'JSON', 'OTHER'}, 'marker': {'COOKIE_MISSING', 'PROFILE_REQUIRED',
        'INVALID_PARAMETER', 'ISSUER_ERROR', 'ORGANISATION_SELECTION', 'NONE'},
        'body': {'TEXT', 'EMPTY', 'ABSENT'}}
    for key, allowed in permitted.items():
        found = re.search(r'\b' + key + r'=([A-Za-z_]+)\b', raw)
        if found and found[1] in allowed:
            result[key] = found[1]
    code = re.search(r'\bfailure_code=([A-Z0-9_]+)\b', raw)
    if code and (code[1] in {'NONE', 'OTHER', 'COOKIE_MISSING', 'PROFILE_REQUIRED', 'INVALID_PARAMETER',
                            'ISSUER_ERROR_PAGE', 'ORGANISATION_SELECTION', 'ERR_JWT_EXPIRED'} or
                 re.fullmatch(r'(FORM_U[0-9]P[0-9]T[0-9]O[0-9]|AUTHORIZATION_HTTP_[1-5][0-9]{2})', code[1])):
        result['failure_code'] = code[1]
    return result
