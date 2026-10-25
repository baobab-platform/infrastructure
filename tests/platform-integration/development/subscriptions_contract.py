"""Finite engineering observations, never substitutes for DEV-09 or INT-07."""
NATIVE = frozenset({'engine-cp-database-denied','native-issuer-clients','current-cp-snapshot','commercial-projection-persistence',
 'wrong-tenant-denied','wrong-audience-denied','missing-scope-denied','foreign-client-denied',
 'revision-before-replay','classification-denied','cp-outage-denied','cp-recovery',
 'issuer-expiry-denied','issuer-revocation-denied','event-durable-replay-conflict',
 'native-restart-persistence','teardown'})
BLOCKED = {'current-internal-positive':'INDEPENDENT_INTERNAL_ELIGIBILITY_NOT_ESTABLISHED',
 'internal-revoked-eligibility-differential':'VALID_INTERNAL_POSITIVE_PREREQUISITE_MISSING',
 'killbill-native-provider':'REAL_KILLBILL_PROVIDER_NOT_QUALIFIED'}

def fresh():
    return {key:{'result':'BLOCKED','reason':BLOCKED.get(key,'NOT_OBSERVED')} for key in sorted(NATIVE|BLOCKED.keys())}

def validate(cases):
    if not isinstance(cases,dict) or set(cases)!=NATIVE|BLOCKED.keys(): raise ValueError('SUBSCRIPTIONS_CASE_INVENTORY')
    for key,row in cases.items():
        if set(row)!={'result','reason'}: raise ValueError('SUBSCRIPTIONS_CASE_FIELDS')
        if key in BLOCKED:
            if row!={'result':'BLOCKED','reason':BLOCKED[key]}: raise ValueError('SUBSCRIPTIONS_INDEPENDENT_GATE')
        elif row not in ({'result':'PASS','reason':'OBSERVED'},{'result':'BLOCKED','reason':'NOT_OBSERVED'},
                         {'result':'FAIL','reason':'NATIVE_ASSERTION_FAILED'}): raise ValueError('SUBSCRIPTIONS_CASE_RESULT')
    return cases
