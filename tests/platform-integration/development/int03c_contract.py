"""Closed DEV-04 evidence vocabulary. Validation checks shape, not runtime truth.

Case IDs retain Shared's original meanings. Every assertion must be observed;
no missing assertion, skipped case or successful source test can qualify a run.
"""
import re

SCHEMA = 'infrastructure.dev04.int03c-observed.v1'
ASSERTIONS = {
    'issuer-issuance-and-readback': {'exact_client_ceiling', 'verifier_authenticated',
        'owner_cannot_introspect', 'wrong_verifier_secret_denied', 'active_readback',
        'issuer_subject_client_audience_scope_expiry_bound', 'positive_cp_before_mutation'},
    'current-cp-principal-and-link': {'principal_active', 'exact_principal_readback',
        'canonical_issuer_subject_provenance_approved', 'distinct_current_humans',
        'same_principal_approval_denied', 'own_tenant_organisation_market'},
    'wrong-audience-denial': {'genuine_same_subject_wrong_audience', 'cp_401',
        'issuer_still_active', 'unexpired_after_denial', 'valid_control_succeeds'},
    'wrong-tenant-denial': {'sibling_403', 'external_403', 'same_unexpired_bearer',
        'valid_control_succeeds'},
    'issuer-revocation-before-expiry': {'positive_before_revoke', 'active_before_revoke',
        'native_revoke_200', 'independent_inactive_readback', 'same_bearer_cp_401',
        'unexpired_after_denial', 'fresh_token_cp_succeeds'},
    'cp-principal-deactivation': {'positive_before_disable', 'same_principal_denied',
        'wrong_digest_denied', 'distinct_checker_completed', 'principal_disabled_readback',
        'same_bearer_cp_403', 'unexpired_after_denial', 'issuer_independently_active'},
    'complete-teardown': {'both_issuer_clients_absent', 'issuance_after_delete_denied',
        'original_tokens_inactive', 'native_human_identities_absent', 'cp_principal_terminal',
        'accepting_runtime_absent', 'owned_resources_absent', 'private_state_absent'},
}
REASONS = {'NOT_EXECUTED', 'OBSERVED', 'ASSERTION_FAILED', 'SERVICE_UNAVAILABLE',
           'PREREQUISITE_FAILED', 'TEARDOWN_PENDING'}


def fresh(run_id):
    return {'schema': SCHEMA, 'run_id': run_id, 'scope': 'DEV04_INT03C_DEVELOPMENT_ONLY',
            'synthetic_only': True, 'canonical_provider_qualified': False,
            'protected_acceptance': False, 'production_authorized': False, 'nab03_qualified': False,
            'cases': {name: {'result': 'BLOCKED', 'reason': 'NOT_EXECUTED',
                            'assertions': {key: False for key in sorted(keys)}}
                      for name, keys in ASSERTIONS.items()}}


def validate(report, run_id, complete=False):
    expected = fresh(run_id)
    if not isinstance(report, dict) or set(report) != set(expected):
        raise ValueError('DEV04_REPORT_INVALID')
    for key in expected.keys() - {'cases'}:
        if type(report[key]) is not type(expected[key]) or report[key] != expected[key]:
            raise ValueError('DEV04_REPORT_INVALID')
    if not re.fullmatch(r'[0-9a-f]{32}', run_id) or set(report['cases']) != set(ASSERTIONS):
        raise ValueError('DEV04_REPORT_INVALID')
    for name, keys in ASSERTIONS.items():
        row = report['cases'][name]
        if (set(row) != {'result', 'reason', 'assertions'} or row['result'] not in {'PASS', 'FAIL', 'BLOCKED'}
                or row['reason'] not in REASONS or set(row['assertions']) != keys
                or any(type(v) is not bool for v in row['assertions'].values())
                or (row['result'] == 'PASS') != (all(row['assertions'].values()) and row['reason'] == 'OBSERVED')):
            raise ValueError('DEV04_REPORT_INVALID')
        if complete and row['result'] != 'PASS':
            raise ValueError('DEV04_CASES_INCOMPLETE')
    return report
