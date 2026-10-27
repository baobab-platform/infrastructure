"""Closed Trade-owned component receipt, never a replacement for INT-05."""
CASES = {'issuer-issuance-and-independent-readback','cp-principal-estate-organisation-market',
    'native-buyer-context','wrong-company-denial','wrong-audience-denial','membership-suspension-denial',
    'issuer-revocation-before-expiry','owned-buyer-bff-native-cleanup'}
REASONS = {'OBSERVED','NOT_EXECUTED','AUTHORITY_NOT_CONFIGURED','DEPENDENCY_UNAVAILABLE','ASSERTION_FAILED','CLEANUP_FAILED'}
FIELDS = {'schema','source_sha','evidence_class','scope','iam_cp_component_qualified','host_teardown',
    'bff_http_qualified','int05_qualified','provider_qualified','protected_acceptance','production_authorized','cases'}

def validate(value, source):
    def require(ok):
        if not ok:raise ValueError('DEV07_COMPONENT_RECEIPT_REFUSED')
    require(isinstance(value,dict) and set(value)==FIELDS)
    require(value['schema']=='baobab-trade.dev07-iam-cp-components.v1' and value['source_sha']==source)
    require(value['scope']=='LIVE_IAM_CP_NATIVE_TRADE_HANDLER' and value['host_teardown']=='NOT_OBSERVED')
    require(value['evidence_class'] in {'NOT_OBSERVED','REAL_COMPONENT_SYNTHETIC_DATA'})
    require(type(value['iam_cp_component_qualified']) is bool)
    require(all(value[k] is False for k in ('bff_http_qualified','int05_qualified','provider_qualified','protected_acceptance','production_authorized')))
    require(isinstance(value['cases'],dict) and set(value['cases'])==CASES)
    for row in value['cases'].values():
        require(isinstance(row,dict) and set(row)=={'result','reason'} and row['result'] in {'PASS','FAIL','BLOCKED'} and row['reason'] in REASONS)
        require((row['result']=='PASS')==(row['reason']=='OBSERVED'))
    if value['iam_cp_component_qualified']:
        require(value['evidence_class']=='REAL_COMPONENT_SYNTHETIC_DATA' and all(r['result']=='PASS' for r in value['cases'].values()))
    return value
