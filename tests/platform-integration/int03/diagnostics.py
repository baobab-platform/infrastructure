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


# Prerequisite errors are constructed by the pinned INT-02 orchestrator after
# suppressing service logs. Re-parse them through this smaller finite allowlist
# instead of retaining an exception, service name, issuer URL or private path.
# This never downgrades a missing live prerequisite or claims qualification.
PREREQUISITE_OPS = {'up', 'exec', 'wait', 'build', 'config', 'down'}
PREREQUISITE_TARGETS = {'probe', 'keycloak', 'cp-db', 'service'}
IAM_LOG_CLASSES = {'DB_AUTH_FAILED', 'DB_OR_PEER_REFUSED', 'DB_OBJECT_MISSING',
    'SERVER_START_FAILED', 'CLI_EXECUTION_ERROR', 'HTTP_LISTENING',
    'MANAGEMENT_LISTENING', 'SERVER_STARTED', 'TEMP_ADMIN_CREATED',
    'LOGIN_USER_NOT_FOUND', 'LOGIN_INVALID_USER_CREDENTIALS',
    'LOGIN_INVALID_CLIENT_CREDENTIALS', 'LOGIN_REQUIRED_ACTIONS',
    'LOGIN_NOT_ALLOWED', 'FLOW_MIXED_LEVELS', 'FLOW_EXCEPTION',
    'TEMPLATE_FAILED', 'NULL_POINTER', 'ILLEGAL_STATE', 'AUTHENTICATION_FAILED'}
IAM_READINESS = {'unavailable', 'tls_unverified', 'issuer_mismatch'}
IAM_READINESS.update(str(code) for code in range(100, 600))


def prerequisite(raw):
    """Reduce inherited qualification failures to trusted closed vocabulary."""
    if type(raw) is not str:
        return {}
    result = {}
    m = re.search(r'\bCompose (up|exec|wait|build|config|down)/(probe|keycloak|cp-db|service) failed\b', raw)
    if m and m[1] in PREREQUISITE_OPS and m[2] in PREREQUISITE_TARGETS:
        result['operation'], result['target'] = m[1], m[2]
    m = re.search(r'\bstep=iam_readiness discovery=([a-z_0-9]{1,32})\b', raw)
    if m and m[1] in IAM_READINESS:
        result['iam_discovery'] = m[1]
    m = re.search(r'\bKeycloak log classes: ([A-Z_,]{1,500})', raw)
    if m:
        found = m[1].split(',')
        result['iam_log_classes'] = sorted(set(code for code in found if code in IAM_LOG_CLASSES))
    return result
