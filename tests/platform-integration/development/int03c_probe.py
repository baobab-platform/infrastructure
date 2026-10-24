"""Private, destructive DEV-04 seven-case driver over actual native IAM/CP APIs.

Transport, Kratos login and Hydra PKCE come from the maintained DEV-03 driver.
Only closed assertions leave the private run. The host independently completes
teardown; this process cannot claim accepting-runtime or resource absence.
"""
import hashlib
import json
import os
import time
import uuid

import native_probe as p
import int03c_contract as contract

OWNER = 'baobab-int03c-issuer-owner'
VERIFIER = 'baobab-int03c-issuer-verifier'


def checkpoint(report):
    # Private atomic replace; the host validates every closed field before custody.
    temp = p.ROOT / '.int03c-report.tmp'
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(report, out); out.flush(); os.fsync(out.fileno())
    os.replace(temp, p.ROOT / 'int03c-report.json')


def bound(actual, bearer, audience='baobab-control-plane'):
    """Bind issuer readback to the issued JWT and an actual <=60s lifetime.

    JWT decoding supplies observations, not trust: CP independently verifies the
    signature/current status. Reject booleans/absent or contradictory timestamps.
    """
    c = p.claims(bearer)
    aud = actual.get('aud', []); aud = [aud] if isinstance(aud, str) else aud
    checks = {
        'active': actual.get('active') is True,
        'issuer_bound': actual.get('iss') == c.get('iss') == p.ISSUER,
        'subject_bound': actual.get('sub') == c.get('sub') == OWNER,
        'client_bound': actual.get('client_id') == OWNER,
        'audience_bound': aud == [audience],
        'scope_bound': set(actual.get('scope', '').split()) == {'context:resolve'},
        'integer_times': type(c.get('exp')) is int and type(c.get('iat')) is int,
        'expiry_bound': actual.get('exp') == c.get('exp'),
        'issued_at_bound': actual.get('iat') == c.get('iat'),
    }
    checks['lifetime_bounded'] = checks['integer_times'] and 0 < c['exp'] - c['iat'] <= 60
    checks['current_time_bound'] = checks['integer_times'] and c['iat'] <= time.time() < c['exp']
    if not all(checks.values()):
        # Only fixed field-level booleans and a bounded relative lifetime leave
        # the private driver. Never print token/subject/issuer/body/timestamps.
        lifetime = c['exp'] - c['iat'] if checks['integer_times'] else None
        print('DEV04_BINDING=' + json.dumps({**checks, 'jwt_lifetime_seconds':
              lifetime if type(lifetime) is int and 0 <= lifetime <= 900 else None}, sort_keys=True), flush=True)
    return all(checks.values())



def main():
    run_id = os.environ['DEV01_RUN_ID']
    report = contract.fresh(run_id)
    checkpoint(report)
    current = 'issuer-issuance-and-readback'
    def observe(key, condition):
        p.require(type(condition) is bool and condition, 'DEV04_ASSERTION_FAILED')
        report['cases'][current]['assertions'][key] = True
        checkpoint(report)
    def finish():
        row = report['cases'][current]
        p.require(all(row['assertions'].values()), 'DEV04_ASSERTION_FAILED')
        row.update(result='PASS', reason='OBSERVED'); checkpoint(report)
    try:
        p.require(not (p.ROOT / 'authority-started').exists() and not (p.ROOT / 'int03c-started').exists(), 'FRESH_AUTHORITY_RUN_REQUIRED')
        p.write('int03c-started', {})
        native = p.read('native.json'); bootstrap = p.read('bootstrap.json'); state = p.read('state.json')
        target_id = bootstrap['proof_principals'][OWNER]
        own = next(e for e in bootstrap['enterprises'] if e['key'] == 'nabhold')
        sibling = next(e for e in bootstrap['enterprises'] if e['key'] == 'thamani')
        external = next(e for e in bootstrap['enterprises'] if e['key'] == 'external-client')
        verifier_auth = (VERIFIER, native['clients'][VERIFIER]['secret'])
        def status(bearer, auth=verifier_auth):
            return p.request('POST', p.ISSUER + '/oauth2/introspect', {'token': bearer}, form=True, basic=auth)
        for name in (OWNER, VERIFIER):
            code, client = p.api('GET', '/admin/clients/' + name)
            p.require(code == 200 and client['client_id'] == name
                      and client['grant_types'] == ['client_credentials']
                      and client['audience'] == ['baobab-control-plane'] and client['scope'] == 'context:resolve'
                      and client['metadata']['development_run_id'] == run_id
                      and client['metadata']['int03c_run_id'] == run_id
                      and client['metadata']['environment'] == 'development'
                      and client['token_endpoint_auth_method'] == 'client_secret_post'
                      and client.get('client_credentials_grant_access_token_lifespan') in ('60s', '1m0s'))
        # A provider GET alone is insufficient: independently bind the actual
        # issued lifetime below as well as the requested/native client ceiling.
        observe('exact_client_ceiling', True)
        bearer = p.token(OWNER, native)
        code, actual, _ = status(bearer)
        observe('verifier_authenticated', code == 200)
        observe('active_readback', actual.get('active') is True)
        observe('issuer_subject_client_audience_scope_expiry_bound', bound(actual, bearer))
        observe('owner_cannot_introspect', status(bearer, (OWNER, native['clients'][OWNER]['secret']))[0] == 401)
        observe('wrong_verifier_secret_denied', status(bearer, (VERIFIER, 'invalid-secret'))[0] == 401)
        observe('positive_cp_before_mutation', p.context(bearer, own)[0] == 200); finish()

        current = 'current-cp-principal-and-link'
        maker = p.native_human('maker', native); checker = p.native_human('checker', native)
        observe('distinct_current_humans', p.claims(maker)['sub'] == native['humans']['maker']['id']
                and p.claims(checker)['sub'] == native['humans']['checker']['id']
                and p.claims(maker)['sub'] != p.claims(checker)['sub'])
        code, actual, _ = p.request('GET', p.CP + '/v1/admin/int03c/principals/' + target_id, token=checker)
        observe('principal_active', code == 200 and actual.get('status') == 'ACTIVE')
        observe('exact_principal_readback', actual.get('principal_id') == target_id)
        digest = 'sha256:' + hashlib.sha256((p.ROOT / 'bootstrap.json').read_bytes()).hexdigest()
        payload = {'principal_id': target_id, 'issuer': p.ISSUER, 'subject': OWNER, 'run_id': run_id,
                   'source_sha': state['sources']['baobab-cp'], 'source_evidence_digest': digest}
        code, provenance, _ = p.request('POST', p.CP + '/v1/admin/int03c/provenance', payload, maker)
        p.require(code == 202)
        approve = p.CP + '/v1/admin/int03c/provenance/' + provenance['provenance_id'] + '/approve'
        observe('same_principal_approval_denied', p.request('POST', approve, {'source_evidence_digest': digest}, maker)[0] == 409)
        code, approved, _ = p.request('POST', approve, {'source_evidence_digest': digest}, checker)
        observe('canonical_issuer_subject_provenance_approved', code == 200
                and approved.get('status') == 'INDEPENDENTLY_APPROVED_UNATTESTED'
                and approved.get('source_evidence_digest') == digest
                and approved.get('principal_id') == target_id and p.claims(bearer)['iss'] == p.ISSUER
                and p.claims(bearer)['sub'] == OWNER and approved.get('run_id') == run_id
                and approved.get('source_sha') == state['sources']['baobab-cp'])
        code, actual, _ = p.context(bearer, own)
        observe('own_tenant_organisation_market', code == 200 and actual.get('tenant_id') == own['tenant_id']
                and actual.get('organisation_id') == own['organisation_id'] and actual.get('country_code') == 'ZA'); finish()

        current = 'wrong-audience-denial'
        config = native['clients'][OWNER]['config']; wrong = dict(config, audience=['baobab-erp'])
        p.require(p.api('PUT', '/admin/clients/' + OWNER, wrong)[0] == 200)
        try:
            code, body, _ = p.request('POST', p.ISSUER + '/oauth2/token', {'grant_type': 'client_credentials',
                'scope': 'context:resolve', 'audience': 'baobab-erp', 'client_id': OWNER,
                'client_secret': native['clients'][OWNER]['secret']}, form=True)
            p.require(code == 200); wrong_bearer = body['access_token']
        finally:
            p.require(p.api('PUT', '/admin/clients/' + OWNER, config)[0] == 200)
        code, actual, _ = status(wrong_bearer)
        observe('genuine_same_subject_wrong_audience', code == 200 and bound(actual, wrong_bearer, 'baobab-erp'))
        observe('issuer_still_active', actual.get('active') is True)
        observe('cp_401', p.context(wrong_bearer, own)[0] == 401)
        observe('unexpired_after_denial', p.claims(wrong_bearer)['exp'] > time.time())
        observe('valid_control_succeeds', p.context(p.token(OWNER, native), own)[0] == 200); finish()

        current = 'wrong-tenant-denial'; bearer = p.token(OWNER, native)
        observe('sibling_403', p.context(bearer, sibling)[0] == 403)
        observe('external_403', p.context(bearer, external)[0] == 403)
        observe('same_unexpired_bearer', p.claims(bearer)['exp'] > time.time())
        observe('valid_control_succeeds', p.context(bearer, own)[0] == 200); finish()

        current = 'issuer-revocation-before-expiry'; bearer = p.token(OWNER, native)
        observe('positive_before_revoke', p.context(bearer, own)[0] == 200)
        code, actual, _ = status(bearer); observe('active_before_revoke', code == 200 and bound(actual, bearer))
        observe('native_revoke_200', p.request('POST', p.ISSUER + '/oauth2/revoke', {'token': bearer,
            'token_type_hint': 'access_token', 'client_id': OWNER, 'client_secret': native['clients'][OWNER]['secret']}, form=True)[0] == 200)
        code, actual, _ = status(bearer); observe('independent_inactive_readback', code == 200 and actual.get('active') is False)
        observe('same_bearer_cp_401', p.context(bearer, own)[0] == 401)
        observe('unexpired_after_denial', p.claims(bearer)['exp'] > time.time())
        fresh = p.token(OWNER, native); observe('fresh_token_cp_succeeds', p.context(fresh, own)[0] == 200); finish()

        current = 'cp-principal-deactivation'; bearer = p.token(OWNER, native)
        observe('positive_before_disable', p.context(bearer, own)[0] == 200)
        payload = {'issuer': p.ISSUER, 'subject': OWNER, 'run_id': run_id,
                   'source_sha': state['sources']['baobab-cp'], 'idempotency_key': str(uuid.uuid4())}
        code, plan, _ = p.request('POST', p.CP + '/v1/admin/int03c/principals/' + target_id + '/deactivation-requests', payload, maker)
        p.require(code == 202)
        approve = p.CP + '/v1/admin/int03c/deactivation-requests/' + plan['request_id'] + '/approve'
        observe('same_principal_denied', p.request('POST', approve, {'plan_digest': plan['plan_digest']}, maker)[0] == 409)
        observe('wrong_digest_denied', p.request('POST', approve, {'plan_digest': 'sha256:' + '0'*64}, checker)[0] == 409)
        code, completed, _ = p.request('POST', approve, {'plan_digest': plan['plan_digest']}, checker)
        observe('distinct_checker_completed', code == 200 and completed.get('decision') == 'COMPLETED'
                and completed.get('principal_id') == target_id and completed.get('plan_digest') == plan['plan_digest'])
        code, actual, _ = p.request('GET', p.CP + '/v1/admin/int03c/principals/' + target_id, token=checker)
        observe('principal_disabled_readback', code == 200 and actual.get('principal_id') == target_id and actual.get('status') == 'DISABLED')
        observe('same_bearer_cp_403', p.context(bearer, own)[0] == 403)
        observe('unexpired_after_denial', p.claims(bearer)['exp'] > time.time())
        code, actual, _ = status(bearer); observe('issuer_independently_active', code == 200 and bound(actual, bearer)); finish()

        current = 'complete-teardown'
        # Observe provider deletion before destroying the accepting runtime/stores.
        for original in (bearer, fresh, wrong_bearer):
            p.require(p.request('POST', p.ISSUER + '/oauth2/revoke', {'token': original,
                'token_type_hint': 'access_token', 'client_id': OWNER,
                'client_secret': native['clients'][OWNER]['secret']}, form=True)[0] == 200)
        for name in (OWNER, VERIFIER):
            p.require(p.api('DELETE', '/admin/clients/' + name)[0] == 204)
            p.require(p.api('GET', '/admin/clients/' + name)[0] == 404)
        observe('both_issuer_clients_absent', True)
        for name in (OWNER, VERIFIER):
            code, _, _ = p.request('POST', p.ISSUER + '/oauth2/token', {'grant_type': 'client_credentials',
                'scope': 'context:resolve', 'audience': 'baobab-control-plane', 'client_id': name,
                'client_secret': native['clients'][name]['secret']}, form=True)
            p.require(code in (400, 401))
        observe('issuance_after_delete_denied', True)
        for original in (bearer, fresh, wrong_bearer):
            code, actual, _ = status(original)
            p.require(code == 200 and actual.get('active') is False)
        observe('original_tokens_inactive', True)
        for human in native['humans'].values():
            url = 'http://kratos:4434/admin/identities/' + human['id']
            p.require(p.request('DELETE', url)[0] == 204 and p.request('GET', url)[0] == 404)
        observe('native_human_identities_absent', True)
        code, actual, _ = p.request('GET', p.CP + '/v1/admin/int03c/principals/' + target_id, token=checker)
        observe('cp_principal_terminal', code == 200 and actual.get('status') == 'DISABLED' and actual.get('principal_id') == target_id)
        report['cases'][current]['reason'] = 'TEARDOWN_PENDING'; checkpoint(report)
        contract.validate(report, run_id)
        print('DEV04_NATIVE_CASES_OBSERVED_TEARDOWN_PENDING')
    except Exception as error:
        row = report['cases'][current]
        row.update(result='FAIL', reason='SERVICE_UNAVAILABLE' if isinstance(error, OSError) else 'ASSERTION_FAILED')
        for name, pending in report['cases'].items():
            if name != current and pending['result'] == 'BLOCKED':
                pending['reason'] = 'PREREQUISITE_FAILED'
        checkpoint(report)
        raise SystemExit('DEV04_NATIVE_QUALIFICATION_FAILED') from None


if __name__ == '__main__':
    main()
