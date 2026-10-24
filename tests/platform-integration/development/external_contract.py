"""Closed DEV-06 observations preserve the complete original INT-07 meaning."""
CASES = ('zero-estates', 'independent-registered-workload', 'own-context',
 'nabhold-tenant-denied', 'zuribeans-tenant-denied', 'thamani-tenant-denied',
 'forged-tenant-denied', 'fake-estate-injection-denied', 'wrong-owner-denied',
 'wrong-audience-denied', 'expired-token-denied', 'revoked-token-replay-denied',
 'dependency-outage-and-recovery', 'bound-resource-and-audited-effect',
 'absent-subscription-denied', 'retired-binding-denied', 'unentitled-resource-denied', 'teardown')
COMPONENTS = {'zero_estates_read_before', 'zero_estates_read_after', 'native_pulse_dependencies',
 'native_canonical_hydration', 'native_cross_tenant_no_leak', 'real_external_resource_read',
 'restricted_evidence_denied', 'current_cp_subject_validation', 'native_clients_deleted',
 'native_tokens_inactive', 'private_state_absent', 'owned_resources_absent', 'canonical_resolution_denied'}
REASONS = {'NOT_EXECUTED', 'OBSERVED', 'ASSERTION_FAILED', 'PREREQUISITE_FAILED',
 'CANONICAL_ENTITLEMENT_NOT_ESTABLISHED', 'CANONICAL_BINDING_NOT_ESTABLISHED', 'TEARDOWN_PENDING'}

def fresh(run):
    return {'schema':'infrastructure.dev06.int07-observed.v1', 'run_id':run,
      'scope':'DEV06_EXTERNAL_API_ONLY_COMPONENT_DEVELOPMENT',
      'canonical_scenario':'INT-07', 'cases':{name:{'result':'BLOCKED','reason':'NOT_EXECUTED'} for name in CASES},
      'component_checks':{}, 'int07_qualified':False, 'canonical_provider_qualified':False,
      'synthetic_only':True, 'protected_acceptance':False, 'production_authorized':False}

def validate(report,run):
    expected=fresh(run)
    if not isinstance(report,dict) or set(report)!=set(expected): raise ValueError('DEV06_REPORT_INVALID')
    for key in expected.keys()-{'cases','component_checks'}:
        if type(report[key]) is not type(expected[key]) or report[key]!=expected[key]:raise ValueError('DEV06_REPORT_INVALID')
    if not isinstance(report['cases'],dict) or set(report['cases'])!=set(CASES):raise ValueError('DEV06_REPORT_INVALID')
    for row in report['cases'].values():
        if not isinstance(row,dict) or set(row)!={'result','reason'} or row['result'] not in {'PASS','FAIL','BLOCKED'} or row['reason'] not in REASONS:raise ValueError('DEV06_REPORT_INVALID')
        if (row['result']=='PASS')!=(row['reason']=='OBSERVED'):raise ValueError('DEV06_REPORT_INVALID')
    if not isinstance(report['component_checks'],dict) or any(k not in COMPONENTS or type(v) is not bool for k,v in report['component_checks'].items()):raise ValueError('DEV06_REPORT_INVALID')
    # This implementation has no independent subscription/grant/binding
    # positive. It cannot promote INT-07, even by marking every row PASS.
    return report
