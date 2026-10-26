"""Closed redacted DEV-14/15 receipts. Authority is never inferred from a plan."""
import re

AUTHORITY_CHECKS=frozenset({'issuer_subjects','own_context','neighbour_context','cross_tenant_denied','unknown_tenant_denied','validator_unassigned','wrong_audience_denied','missing_scope_denied','current_bindings','current_validator','expired_token_denied','revoked_token_denied'})
COMMON=frozenset('ENG-ONB-0'+str(i) for i in range(1,10))
REASONS={'OBSERVED','NOT_EXECUTED','DEPENDENCY_UNAVAILABLE','AUTHORITY_UNQUALIFIED','NATIVE_NOT_IMPLEMENTED','ASSERTION_FAILED','TEARDOWN_PENDING'}

def require(ok):
    if not ok:raise ValueError('ENGINE_RECEIPT_REFUSED')

def fresh(profile,run):
    return {'schema':'infrastructure.engine-integration.observed.v1','run_id':run,
      'profile_key':profile['profile_key'],'subject_engine':profile['subject_engine'],
      'synthetic_only':True,'protected_acceptance':False,'production_authorized':False,
      'capabilities':{c['capability_key']:{'source':'DECLARED_IMPLEMENTED','development':'NOT_OBSERVED','certification':'NOT_QUALIFIED','protected_authorized':False} for c in profile['capabilities']},
      'independent_observations':{'native_cp_resolutions':{c['capability_key']:0 for c in profile['capabilities']},'native_audits_joined':0,'issuer_cleanup':False,'host_cleanup':False,'faults_observed':[],'authority_denials':0,'principal_denial':False},
      'cases':{case:{'result':'BLOCKED','reason':'NOT_EXECUTED'} for case in profile['reporting']['case_ids']}}

def validate(report,run):
    require(isinstance(report,dict) and set(report)=={'schema','run_id','profile_key','subject_engine','synthetic_only','protected_acceptance','production_authorized','cases','capabilities','independent_observations'})
    require(report['schema']=='infrastructure.engine-integration.observed.v1' and report['run_id']==run and re.fullmatch('[0-9a-f]{32}',run))
    require(report['synthetic_only'] is True and report['protected_acceptance'] is False and report['production_authorized'] is False)
    require(all(isinstance(report[k],str) and re.fullmatch('[a-z][a-z0-9-]{1,62}',report[k]) for k in ('profile_key','subject_engine')))
    require(isinstance(report['cases'],dict) and COMMON<=set(report['cases']))
    observed=report['independent_observations']
    require(isinstance(observed,dict) and set(observed)=={'native_cp_resolutions','native_audits_joined','issuer_cleanup','host_cleanup','faults_observed','authority_denials','principal_denial'})
    require(type(observed['native_audits_joined']) is int and observed['native_audits_joined']>=0 and type(observed['issuer_cleanup']) is bool and type(observed['host_cleanup']) is bool and type(observed['principal_denial']) is bool)
    require(type(observed['authority_denials']) is int and 0<=observed['authority_denials']<=4 and isinstance(observed['faults_observed'],list) and len(observed['faults_observed'])<=16 and len(set(observed['faults_observed']))==len(observed['faults_observed']) and all(isinstance(name,str) and re.fullmatch('[a-z][a-z0-9-]{1,62}',name) for name in observed['faults_observed']))
    require(isinstance(report['capabilities'],dict) and bool(report['capabilities']) and set(report['capabilities'])==set(observed['native_cp_resolutions']))
    for key,cap in report['capabilities'].items():
        require(re.fullmatch(r'[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*',key) and isinstance(cap,dict) and set(cap)=={'source','development','certification','protected_authorized'})
        delta=observed['native_cp_resolutions'][key]
        require(type(delta) is int and delta>=0 and cap['source']=='DECLARED_IMPLEMENTED' and cap['development'] in {'NOT_OBSERVED','OBSERVED'} and cap['certification']=='NOT_QUALIFIED' and cap['protected_authorized'] is False)
        require(cap['development']!='OBSERVED' or delta>0)
    for key,row in report['cases'].items():
        require(isinstance(key,str) and re.fullmatch('[A-Z][A-Z0-9-]{2,79}',key) and not key.startswith(('NAB-','INT-')))
        require(isinstance(row,dict) and set(row)=={'result','reason'} and row['result'] in {'PASS','FAIL','BLOCKED'} and row['reason'] in REASONS)
        require((row['result']=='PASS')==(row['reason']=='OBSERVED'))
    if report['cases']['ENG-ONB-04']['result']=='PASS':require(observed['authority_denials']==4)
    if report['cases']['ENG-ONB-07']['result']=='PASS':require({'cp','hydra'}<=set(observed['faults_observed']))
    if report['cases']['ENG-ONB-08']['result']=='PASS':require(observed['issuer_cleanup'] and observed['host_cleanup'])
    if report['cases']['ENG-ONB-05']['result']=='PASS':require(all(cap['development']=='OBSERVED' for cap in report['capabilities'].values()))
    return report
