"""Platform-owned generic issuer/CP observations. No engine domain code here."""
import json
import base64
import os
import secrets
import time
import uuid
import native_probe as p

CHECKS=frozenset({'issuer_subjects','own_context','neighbour_context','cross_tenant_denied','unknown_tenant_denied',
    'validator_unassigned','wrong_audience_denied','missing_scope_denied','current_bindings','current_validator',
    'expired_token_denied','revoked_token_denied'})

def profile():
    state=p.read('state.json');return state,state['engine_profile'],p.read('bootstrap.json')

def token(role='caller',audiences=None,scopes=None):
    state,profile,_=globals()['profile']();identity=profile['iam'][role]
    fields=[('grant_type','client_credentials'),('client_id',identity['client_id']),('client_secret',state['secrets']['engine_'+role]),
        ('scope',' '.join(scopes if scopes is not None else identity['scopes']))]
    fields += [('audience',aud) for aud in (audiences if audiences is not None else identity['audiences'])]
    code,body,_=p.request('POST',p.ISSUER+'/oauth2/token',fields,form=True)
    p.require(code==200 and body.get('access_token'));return body['access_token']

def resolve_context(bearer,enterprise):
    return p.request('POST',p.CP+'/v1/platform-context/resolve',{'tenant_id':enterprise['tenant_id'],'organisation_id':enterprise['organisation_id'],'country_code':enterprise['markets'][0]},bearer)

def private_checkpoint(name,value):
    path=p.ROOT/name;tmp=path.with_name('.'+name+'.'+secrets.token_hex(8))
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as handle:json.dump(value,handle);handle.flush();os.fsync(handle.fileno())
    os.replace(tmp,path)

def witness(state,descriptor,bootstrap):
    own=next(e for e in bootstrap['enterprises'] if e['key']==descriptor['enterprise_seed'])
    neighbour=next(e for e in bootstrap['enterprises'] if e['key']==descriptor['neighbour_seed'])
    caller=token();other=token('neighbour')
    code,context,_=resolve_context(caller,own);p.require(code==200)
    code,foreign,_=resolve_context(other,neighbour);p.require(code==200)
    private_checkpoint('engine-witness.json',{'caller_token':caller,'context':context,'neighbour_token':other,'neighbour_context':foreign})

def main(action):
    state,descriptor,bootstrap=profile()
    if action=='principal':
        bearer=token();claims=p.claims(bearer)
        code,status,_=p.request('POST',p.ISSUER+'/oauth2/introspect',{'token':bearer},form=True,basic=('baobab-dev-introspection',state['secrets']['introspection']))
        p.require(code==200 and status['active'] is True and claims['exp']>time.time())
        own=next(e for e in bootstrap['enterprises'] if e['key']==descriptor['enterprise_seed'])
        p.require(resolve_context(bearer,own)[0]==403)
        print(json.dumps({'disabled_principal_denied':True}));return
    if action=='cleanup':
        original=token();claims=p.claims(original)
        p.require(claims['exp']>time.time())
        for role,identity in descriptor['iam'].items():
            name=identity['client_id']
            code,current=p.api('GET','/admin/clients/'+name)
            p.require(code==200 and current['metadata']['development_run_id']==state['run_id'] and current['audience']==identity['audiences'] and current['scope']==' '.join(identity['scopes']))
            p.require(p.api('DELETE','/admin/clients/'+name)[0]==204)
            p.require(p.api('GET','/admin/clients/'+name)[0]==404)
            code,_,_=p.request('POST',p.ISSUER+'/oauth2/token',{'grant_type':'client_credentials','client_id':name,'client_secret':state['secrets']['engine_'+role],'scope':' '.join(identity['scopes'])},form=True)
            p.require(code in (400,401))
        code,status,_=p.request('POST',p.ISSUER+'/oauth2/introspect',{'token':original},form=True,basic=('baobab-dev-introspection',state['secrets']['introspection']))
        p.require(code==200 and status['active'] is False and claims['exp']>time.time())
        own=next(e for e in bootstrap['enterprises'] if e['key']==descriptor['enterprise_seed'])
        p.require(resolve_context(original,own)[0]==401)
        print(json.dumps({'issuer_cleanup_observed':True}));return
    if action=='witness':
        witness(state,descriptor,bootstrap);print(json.dumps({'witness_created':True}));return
    if action=='health':
        p.require(p.request('GET','https://engine.baobab-dev.test'+descriptor['adapter']['readiness_path'])[0]==200)
        print(json.dumps({'status':'READY'}));return
    p.require(action=='authority');checks={}
    def observe(name,value):
        p.require(name in CHECKS and value);checks[name]=True
    own=next(e for e in bootstrap['enterprises'] if e['key']==descriptor['enterprise_seed'])
    neighbour=next(e for e in bootstrap['enterprises'] if e['key']==descriptor['neighbour_seed'])
    caller=token();other=token('neighbour');validator=token('validator')
    observe('issuer_subjects',p.claims(caller)['sub']==descriptor['iam']['caller']['client_id'] and
        p.claims(other)['sub']==descriptor['iam']['neighbour']['client_id'] and p.claims(validator)['sub']==descriptor['iam']['validator']['client_id'] and p.claims(caller)['actor_type']=='workload')
    code,context,_=resolve_context(caller,own)
    observe('own_context',code==200 and context['tenant_id']==own['tenant_id'] and context['organisation_id']==own['organisation_id'])
    code,foreign,_=resolve_context(other,neighbour)
    observe('neighbour_context',code==200 and foreign['tenant_id']==neighbour['tenant_id'])
    observe('cross_tenant_denied',resolve_context(caller,neighbour)[0]==403 and resolve_context(other,own)[0]==403)
    observe('unknown_tenant_denied',resolve_context(caller,{**own,'tenant_id':'tn_unknown'+state['run_id']})[0] in (403,404))
    observe('validator_unassigned',resolve_context(validator,own)[0]==403)
    wrong_aud=token(audiences=[descriptor['subject_engine']]);observe('wrong_audience_denied',resolve_context(wrong_aud,own)[0]==401)
    native_scope=next(s for s in descriptor['iam']['caller']['scopes'] if s!='context:resolve')
    no_scope=token(scopes=[native_scope]);observe('missing_scope_denied',resolve_context(no_scope,own)[0]==403)
    code,validated,_=p.request('POST',p.CP+'/v1/platform-context/validate',{'context_id':context['context_id'],'subject_token':caller},validator)
    observe('current_validator',code==200 and validated['tenant_id']==own['tenant_id'] and validated['context_id']==context['context_id'])
    fixture=p.read('engine-capability.json');matches=[]
    for cap in descriptor['capabilities']:
        correlation=str(uuid.uuid4());key=cap['capability_key']
        code,result,_=p.request('POST',p.CP+'/v1/capabilities/resolve',{'context_id':context['context_id'],'capability_key':key,
            'required_contract_version':cap['contract_version'],'correlation_id':correlation},caller)
        matches.append(code==200 and result['decision']=='RESOLVED' and result['correlation_id']==correlation and
            result['grant_id']=='grant_'+fixture['grants'][key].replace('-','') and result['binding_id']=='bind_'+fixture['bindings'][key].replace('-','') and
            result['invocation']['provider_id']=='provider_'+fixture['provider_id'].replace('-','') and
            result['invocation']['engine_instance_id']=='ei_'+fixture['engine_instance_id'].replace('-',''))
    observe('current_bindings',bool(matches) and all(matches))
    client=descriptor['iam']['caller']['client_id'];config=p.read('native.json')['clients'][client]['config']
    try:
        p.require(p.api('PUT','/admin/clients/'+client,{**config,'client_credentials_grant_access_token_lifespan':'2s'})[0]==200)
        expired=token()
    finally:p.require(p.api('PUT','/admin/clients/'+client,config)[0]==200)
    delay=p.claims(expired)['exp']-time.time()+1;p.require(0<delay<10);time.sleep(delay)
    observe('expired_token_denied',resolve_context(expired,own)[0]==401)
    revoked=token();p.require(p.request('POST',p.ISSUER+'/oauth2/revoke',{'token':revoked,'client_id':client,'client_secret':state['secrets']['engine_caller']},form=True)[0]==200)
    code,status,_=p.request('POST',p.ISSUER+'/oauth2/introspect',{'token':revoked},form=True,basic=('baobab-dev-introspection',state['secrets']['introspection']))
    observe('revoked_token_denied',code==200 and status['active'] is False and p.claims(revoked)['exp']>time.time() and resolve_context(revoked,own)[0]==401)
    foreign=token().split('.')
    claims=p.claims('.'.join(foreign));claims['iss']='https://untrusted-issuer.invalid'
    foreign[1]=base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    # Deliberately forged negative input, never an issued or trusted identity.
    private_checkpoint('engine-security.json',{'revoked':revoked,'expired':expired,'wrong_audience':token(audiences=['baobab-control-plane']),'missing_scope':token(scopes=['context:resolve']),'untrusted_issuer':'.'.join(foreign)})
    p.require(set(checks)==CHECKS);print(json.dumps({'checks':checks},sort_keys=True))

if __name__=='__main__':
    import sys
    try:main(sys.argv[1])
    except Exception:raise SystemExit('ENGINE_PLATFORM_PROBE_FAILED') from None
