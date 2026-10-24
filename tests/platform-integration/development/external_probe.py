"""Actual external OAuth/CP/Pulse observations; only closed results leave custody."""
import json
import os
import time
import uuid
import native_probe as p
import external_contract as contract

CLIENT='baobab-dev-external-api'
VALIDATOR='baobab-dev-pulse-validator'
PULSE='https://pulse.baobab-dev.test'

def checkpoint(report):
    contract.validate(report,os.environ['DEV01_RUN_ID'])
    path=p.ROOT/'.external-report.tmp'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out:json.dump(report,out);out.flush();os.fsync(out.fileno())
    os.replace(path,p.ROOT/'external-report.json')

def config():
    bootstrap=p.read('bootstrap.json')
    own=next(e for e in bootstrap['enterprises'] if e['key']=='external-client')
    p.require(not own.get('digital_estate_id') and own.get('client_id')==CLIENT)
    return p.read('native.json'),bootstrap,own

def clients():
    native,_,_=config();state=p.read('state.json')
    for name,key in ((CLIENT,'external_caller'),(VALIDATOR,'external_validator')):
        scopes='context:validate' if name==VALIDATOR else 'context:resolve intelligence:evidence:search'
        cfg={'client_id':name,'client_secret':state['secrets'][key], 'grant_types':['client_credentials'],
            'response_types':[],'scope':scopes,'audience':['baobab-control-plane'] if name==VALIDATOR else ['baobab-control-plane','baobab-pulse'],
            'token_endpoint_auth_method':'client_secret_post', 'client_credentials_grant_access_token_lifespan':'120s',
            'metadata':{'development_run_id':state['run_id'],'environment':'development','owner':'baobab-platform/baobab-pulse' if name==VALIDATOR else 'baobab-platform/infrastructure'}}
        p.require(p.api('GET','/admin/clients/'+name)[0]==404)
        p.require(p.api('POST','/admin/clients',cfg)[0]==201)
        code,actual=p.api('GET','/admin/clients/'+name)
        p.require(code==200 and actual['scope']==scopes and actual['audience']==cfg['audience'] and
                  actual['metadata']==cfg['metadata'] and actual['client_credentials_grant_access_token_lifespan']=='2m0s')
        native['clients'][name]={'secret':state['secrets'][key],'config':cfg}
    path=p.ROOT/'.native-external.tmp'
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as out:json.dump(native,out);out.flush();os.fsync(out.fileno())
    os.replace(path,p.ROOT/'native.json')

def token(name=CLIENT,audience='baobab-pulse',scope='intelligence:evidence:search'):
    native=p.read('native.json')
    code,body,_=p.request('POST',p.ISSUER+'/oauth2/token',{'grant_type':'client_credentials','client_id':name,
        'client_secret':native['clients'][name]['secret'],'audience':audience,'scope':scope},form=True)
    p.require(code==200 and body.get('access_token'))
    return body['access_token']

def context():
    _,_,own=config();bearer=token(audience='baobab-control-plane',scope='context:resolve')
    code,ctx,_=p.context(bearer,own)
    p.require(code==200 and ctx['tenant_id']==own['tenant_id'] and ctx['organisation_id']==own['organisation_id'] and not ctx.get('digital_estate_id'))
    return bearer,ctx

def search(bearer,cid,evidence=None):
    body={'query_text':'INT-02 synthetic canonical evidence for provider conformance.','top_k':10}
    if evidence:body['evidence_set_id']=evidence
    return p.request('POST',PULSE+'/evidence/search',body,bearer,headers={'X-Baobab-Context-Id':cid})

def positive(result):
    code,body,_=result
    return code==200 and len(body.get('candidates',[]))==1 and body['candidates'][0].get('canonical_object_id')=='evd_int02_native' and not body['candidates'][0].get('is_stale')

def status(bearer):
    return p.request('POST',p.ISSUER+'/oauth2/introspect',{'token':bearer},form=True,
        basic=('baobab-dev-introspection',os.environ['DEV03_INTROSPECTION_SECRET']))

def main(action):
    if action=='clients':clients();return
    if action=='authority-input':
        _,ctx=context();bearer=token();validator=token(VALIDATOR,'baobab-control-plane','context:validate')
        code,body,_=p.request('POST',p.CP+'/v1/platform-context/validate',{'context_id':ctx['context_id'],'subject_token':bearer},validator)
        print('DEV06_DIRECT_CP='+('READY' if code==200 else 'REFUSED'),flush=True)
        target=p.ROOT/'pulse-fixtures/authority.json'
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out:json.dump({'context_id':ctx['context_id'],'subject':CLIENT,'token':bearer},out)
        return
    if action=='health':
        print(json.dumps({'pulse':p.request('GET',PULSE+'/readyz')[0]}));return
    run=os.environ['DEV01_RUN_ID'];path=p.ROOT/'external-report.json'
    report=p.read('external-report.json') if path.exists() else contract.fresh(run)
    current={'outage':'dependency-outage-and-recovery','restored':'dependency-outage-and-recovery',
             'finish':'teardown'}.get(action,'independent-registered-workload')
    def record(case,observe):
        nonlocal current
        current=case
        print('DEV06_PROBE_CASE='+case,flush=True)
        p.require(observe())
        report['cases'][case]={'result':'PASS','reason':'OBSERVED'};checkpoint(report)
    try:
        native,bootstrap,own=config()
        if action=='initial':
            cp_token,ctx=context();bearer=token()
            record('independent-registered-workload',lambda:p.claims(bearer)['sub']==CLIENT and p.claims(bearer)['actor_type']=='workload')
            record('own-context',lambda:ctx['principal_id']==own['principal_id'] if 'principal_id' in ctx else ctx['tenant_id']==own['tenant_id'])
            # Use actual maintained Pulse HTTP/authentication/context adapters.
            # This component positive is NOT an entitled bound invocation.
            current='bound-resource-and-audited-effect'
            observed=search(bearer,ctx['context_id'])
            if not positive(observed):
                code=observed[0]
                if type(code) is int and code in (200,400,401,403,404,500,502,503,504):print('DEV06_RESOURCE_HTTP='+str(code),flush=True)
                reason=observed[1].get('code') if isinstance(observed[1],dict) else None
                if reason in {'AUTH_TOKEN_INVALID','CAPABILITY_AUTHORITY_UNAVAILABLE','CAPABILITY_ACCESS_DENIED','CONTEXT_NOT_FOUND','PULSE_INTERNAL_ERROR','CAPABILITY_RUNTIME_UNAVAILABLE','SEMANTIC_RETRIEVAL_UNAVAILABLE'}:print('DEV06_RESOURCE_CODE='+reason,flush=True)
            p.require(positive(observed))
            report['component_checks']['real_external_resource_read']=True
            restricted=search(bearer,ctx['context_id'],'evs_int02_restricted')
            p.require(restricted[0]==200 and restricted[1].get('candidates')==[])
            report['component_checks']['restricted_evidence_denied']=True
            report['component_checks']['current_cp_subject_validation']=True
            for key in ('nabhold','zuribeans','thamani'):
                other=next(e for e in bootstrap['enterprises'] if e['key']==key)
                record(key+'-tenant-denied',lambda other=other:p.context(cp_token,other)[0]==403)
            forged={**own,'tenant_id':'tn_forged'+run}
            record('forged-tenant-denied',lambda:p.context(cp_token,forged)[0]==403)
            record('fake-estate-injection-denied',lambda:p.request('POST',p.CP+'/v1/platform-context/resolve',
                {'tenant_id':own['tenant_id'],'organisation_id':own['organisation_id'],'country_code':'ZA','digital_estate_id':str(uuid.uuid4())},cp_token)[0] in (400,403,422))
            other=next(e for e in bootstrap['enterprises'] if e['key']=='nabhold')
            other_token=p.token(other['client_id'],native);code,foreign,_=p.context(other_token,other);p.require(code==200)
            record('wrong-owner-denied',lambda:search(bearer,foreign['context_id'])[0]==404)
            record('wrong-audience-denied',lambda:search(cp_token,ctx['context_id'])[0]==401)
            current='expired-token-denied'
            cfg=native['clients'][CLIENT]['config']
            try:
                p.require(p.api('PUT','/admin/clients/'+CLIENT,{**cfg,'client_credentials_grant_access_token_lifespan':'2s'})[0]==200)
                expired=token()
            finally:p.require(p.api('PUT','/admin/clients/'+CLIENT,cfg)[0]==200)
            delay=p.claims(expired)['exp']-time.time()+1;p.require(0<delay<10);time.sleep(delay)
            record('expired-token-denied',lambda:search(expired,ctx['context_id'])[0]==401)
            current='revoked-token-replay-denied'
            revoked=token();p.require(positive(search(revoked,ctx['context_id'])))
            p.require(p.request('POST',p.ISSUER+'/oauth2/revoke',{'token':revoked,'client_id':CLIENT,'client_secret':cfg['client_secret']},form=True)[0]==200)
            code,actual,_=status(revoked);p.require(code==200 and actual['active'] is False and p.claims(revoked)['exp']>time.time())
            record('revoked-token-replay-denied',lambda:search(revoked,ctx['context_id'])[0]==401 and search(revoked,ctx['context_id'])[0]==401)
            p.require(positive(search(token(),ctx['context_id'])))
            # Resolve through CP's canonical API. Missing grant/provider does
            # not become a positive or a controlled absent-subscription proof.
            code,decision,_=p.request('POST',p.CP+'/v1/capabilities/resolve',{'context_id':ctx['context_id'],
                'capability_key':'intelligence.evidence.search','required_contract_version':1,'correlation_id':str(uuid.uuid4())},cp_token)
            p.require(code==200 and decision.get('decision')=='DENIED' and decision.get('reason_code')=='GRANT_NOT_FOUND' and not decision.get('invocation'))
            report['component_checks']['canonical_resolution_denied']=True
            for case in ('bound-resource-and-audited-effect','absent-subscription-denied','unentitled-resource-denied'):
                report['cases'][case]={'result':'BLOCKED','reason':'CANONICAL_ENTITLEMENT_NOT_ESTABLISHED'}
            report['cases']['retired-binding-denied']={'result':'BLOCKED','reason':'CANONICAL_BINDING_NOT_ESTABLISHED'}
            p.write('external-context.json',ctx)
        elif action=='outage':
            current='dependency-outage-and-recovery';ctx=p.read('external-context.json')
            p.require(search(token(),ctx['context_id'])[0]==503)
        elif action=='restored':
            _,ctx=context();record('dependency-outage-and-recovery',lambda:positive(search(token(),ctx['context_id'])))
        elif action=='finish':
            for name in (CLIENT,VALIDATOR):
                p.require(p.api('DELETE','/admin/clients/'+name)[0]==204 and p.api('GET','/admin/clients/'+name)[0]==404)
            report['component_checks']['native_clients_deleted']=True
            code,actual,_=status(p.read('external-last-token.json')['token'])
            p.require(code==200 and actual['active'] is False)
            report['component_checks']['native_tokens_inactive']=True
            report['cases']['teardown']={'result':'BLOCKED','reason':'TEARDOWN_PENDING'}
        else:raise ValueError('DEV06_ACTION_REFUSED')
        if action=='initial':p.write('external-last-token.json',{'token':token()})
        checkpoint(report)
    except Exception:
        report['cases'][current]={'result':'FAIL','reason':'ASSERTION_FAILED'}
        for row in report['cases'].values():
            if row['reason']=='NOT_EXECUTED':row['reason']='PREREQUISITE_FAILED'
        checkpoint(report)
        raise SystemExit('DEV06_PROBE_FAILED') from None

if __name__=='__main__':main(__import__('sys').argv[1])
