"""Original NAB-03 result vocabulary; no omitted/skipped case can qualify."""
CASES = ('published-home-nav-footer','wrong-audience-token','wrong-credential','disabled-caller',
 'expired-caller-token','revoked-caller-token','missing-grant','wrong-owner-or-context','neighbour-tenant',
 'draft-or-preview','withdrawn-content','dependency-outage-and-restoration','validator-negatives','teardown')
REASONS = {'NOT_EXECUTED','OBSERVED','PROVIDER_NOT_ELIGIBLE','CANONICAL_CAPABILITY_NOT_RESOLVED',
 'SERVICE_UNAVAILABLE','ASSERTION_FAILED','PREREQUISITE_FAILED','TEARDOWN_PENDING'}

def fresh(run):
    return {'schema':'infrastructure.dev05.nab03-observed.v1','run_id':run,
      'scope':'DEV05_NATIVE_CMS_DEVELOPMENT_ONLY','cases':{c:{'result':'BLOCKED','reason':'NOT_EXECUTED'} for c in CASES},
      'component_checks':{},'nab03_qualified':False,'canonical_provider_qualified':False,
      'protected_acceptance':False,'production_authorized':False,'synthetic_only':True}

def validate(report,run):
    expected=fresh(run)
    if not isinstance(report,dict) or set(report)!=set(expected):raise ValueError('DEV05_REPORT_INVALID')
    for key in expected.keys()-{'cases','component_checks','nab03_qualified'}:
        if type(report[key]) is not type(expected[key]) or report[key]!=expected[key]:raise ValueError('DEV05_REPORT_INVALID')
    if set(report['cases'])!=set(CASES) or type(report['nab03_qualified']) is not bool:raise ValueError('DEV05_REPORT_INVALID')
    for row in report['cases'].values():
        if set(row)!={'result','reason'} or row['result'] not in {'PASS','BLOCKED','FAIL'} or row['reason'] not in REASONS:raise ValueError('DEV05_REPORT_INVALID')
        if (row['result']=='PASS')!=(row['reason']=='OBSERVED'):raise ValueError('DEV05_REPORT_INVALID')
    if not isinstance(report['component_checks'],dict) or any(k not in COMPONENTS or type(v) is not bool for k,v in report['component_checks'].items()):raise ValueError('DEV05_REPORT_INVALID')
    if report['nab03_qualified'] and not all(row['result']=='PASS' for row in report['cases'].values()):raise ValueError('DEV05_REPORT_INVALID')
    return report

COMPONENTS={'native_cms_published_home_navigation_footer','native_bff_login_session','native_bff_logout_custody',
 'bff_token_free_session','bff_secure_opaque_cookie','provider_declared_partial','canonical_capability_denied',
 'issuer_readback_active','cp_validator_subject_accepted','wrong_audience_active','revoked_before_expiry',
 'fresh_after_revoke','disabled_principal_before_expiry','native_clients_deleted','native_tokens_inactive',
 'private_state_absent','owned_resources_absent','provider_outage_restored','cp_outage_observed'}
