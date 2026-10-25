"""Native APIs only. Raw bodies, secrets and canonical IDs never leave the run."""
import json
import os
import time
import uuid
import native_probe as p
import subscriptions_contract as contract

PRODUCER='baobab-dev-cp-subscriptions'
ASSESSOR='baobab-dev-subscriptions-assessor'
ENGINE='https://subscriptions.baobab-dev.test'
CP_SCOPES='subscription:internal-authority subscription:current-workload-read subscription:commercial-authority'
SCOPES='billing:manage billing:read billing:observe usage:record'

def save(name,value):
    path=p.ROOT/name
    with path.open('w') as out: json.dump(value,out)
    path.chmod(0o600)

def token(name=PRODUCER,audience='baobab-subscriptions',scope=SCOPES):
    native=p.read('native.json');client=native['clients'][name]
    fields={'grant_type':'client_credentials','audience':audience,'scope':scope}
    basic=None
    if client['config']['token_endpoint_auth_method']=='client_secret_basic':
        basic=(name,client['secret'])
    else:
        p.require(client['config']['token_endpoint_auth_method']=='client_secret_post')
        fields.update(client_id=name,client_secret=client['secret'])
    status,body,_=p.request('POST',p.ISSUER+'/oauth2/token',fields,form=True,basic=basic)
    p.require(status==200 and isinstance(body.get('access_token'),str),'NATIVE_TOKEN_REQUIRED')
    return body['access_token']

def cp_path(fixture):
    return p.CP+'/internal/subscriptions/v1/tenants/'+fixture['tenant_id']+'/product-subscriptions/'+fixture['product_subscription_id']

def refresh():
    bearer=token(ASSESSOR,'baobab-control-plane',CP_SCOPES)
    # Keep the bound mount inode: atomic rename would leave the engine reading
    # the prior token. The enclosing run is private; engine mount is read-only.
    target=p.ROOT/'subscriptions-identity/cp-token'
    target.write_text(bearer);target.chmod(0o644)
    return bearer

def clients():
    native=p.read('native.json')
    for name,aud,scopes in ((PRODUCER,'baobab-subscriptions',SCOPES),(ASSESSOR,'baobab-control-plane',CP_SCOPES)):
        secret=__import__('secrets').token_urlsafe(32)
        cfg={'client_id':name,'client_secret':secret,'grant_types':['client_credentials'],'response_types':[],
            'scope':scopes,'audience':[aud],'token_endpoint_auth_method':'client_secret_post',
            'client_credentials_grant_access_token_lifespan':'120s',
            'metadata':{'development_run_id':os.environ['DEV01_RUN_ID'],'environment':'development'}}
        p.require(p.api('GET','/admin/clients/'+name)[0]==404)
        p.require(p.api('POST','/admin/clients',cfg)[0]==201)
        code,readback=p.api('GET','/admin/clients/'+name)
        p.require(code==200 and readback['scope']==scopes and readback['audience']==[aud]
                  and readback['grant_types']==['client_credentials'] and readback['metadata']==cfg['metadata'])
        native['clients'][name]={'secret':secret,'config':cfg}
    save('native.json',native)
    refresh()
    cases=contract.fresh();cases['native-issuer-clients']={'result':'PASS','reason':'OBSERVED'};save('subscriptions-cases.json',cases)

def invoke(method,path,body=None,bearer=None,key=None):
    return p.request(method,ENGINE+path,body,token() if bearer is None else bearer,
        headers={'Idempotency-Key':key or 'onboarding-'+uuid.uuid4().hex})

def main(action):
    if action=='clients': clients();return
    if action=='refresh': refresh();return
    if action=='health': print(json.dumps({'subscriptions':p.request('GET',ENGINE+'/health/ready')[0]}));return
    cases=p.read('subscriptions-cases.json');fixture=p.read('subscription-fixture.json')
    current=None
    def record(name,ok):
        nonlocal current
        current=name;print('SUBSCRIPTIONS_CASE='+name,flush=True);p.require(ok,'SUBSCRIPTIONS_NATIVE_ASSERTION');cases[name]={'result':'PASS','reason':'OBSERVED'};save('subscriptions-cases.json',cases)
    try:
        if action=='initial':
            current='current-cp-snapshot'
            cp=refresh();status,snapshot,_=p.request('GET',cp_path(fixture)+'/current',token=cp)
            record('current-cp-snapshot',status==200 and snapshot['authoritative_revision']==1
                   and snapshot['classification']['classification_id']==fixture['classification_id']
                   and snapshot['primary_organisation_id']==fixture['organisation_id'])
            # Current CP is the source of the tuple, never caller-provided type.
            body={'tenant_id':fixture['tenant_id'],'product_subscription_id':fixture['product_subscription_id'],
                'product_id':snapshot['product_id'],'authoritative_revision':1,'legal_entity_id':fixture['legal_entity_id'],
                'subscription_type':snapshot['classification']['subscription_type'],
                'classification':{k:snapshot['classification'][k] for k in ('classification_id','classification_source','classification_reference')}}
            body['classification']['classified_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
            key='onboarding-'+uuid.uuid4().hex
            status,projection,_=invoke('POST','/v1/billing-projections',body,key=key)
            record('commercial-projection-persistence',status==201 and projection['readiness']['status']=='BLOCKED'
                   and projection['provider']['simulated'] is True and projection['authoritative_revision']==1)
            save('subscription-request.json',{'body':body,'key':key,'id':projection['billing_subscription_id']})
            path='/v1/tenants/'+fixture['tenant_id']+'/billing-projections/'+projection['billing_subscription_id']
            foreign='/v1/tenants/'+fixture['other_tenant_id']+'/billing-projections/'+projection['billing_subscription_id']
            bad={**body,'tenant_id':fixture['other_tenant_id']}
            record('wrong-tenant-denied',invoke('GET',foreign)[0]==404 and invoke('POST','/v1/billing-projections',bad)[0]==409
                   and p.request('GET',cp_path({**fixture,'tenant_id':fixture['other_tenant_id']})+'/current',token=cp)[0]==404)
            record('wrong-audience-denied',invoke('GET',path,bearer=cp)[0]==401)
            # Fault injection: the native issuer signs the right resource
            # audience/scope for a different client. This is negative evidence,
            # never a registry ceiling or a positive authorisation grant.
            current='foreign-client-denied'
            foreign_client='baobab-dev-nabhold-estate';native=p.read('native.json')
            cfg=native['clients'][foreign_client]['config']
            p.require(p.api('PUT','/admin/clients/'+foreign_client,{**cfg,'audience':['baobab-subscriptions'],'scope':'billing:read'})[0]==200)
            try: foreign_token=token(foreign_client,'baobab-subscriptions','billing:read')
            finally:p.require(p.api('PUT','/admin/clients/'+foreign_client,cfg)[0]==200)
            record('foreign-client-denied',invoke('GET',path,bearer=foreign_token)[0]==403)
            record('missing-scope-denied',invoke('POST','/v1/billing-projections',body,bearer=token(scope='billing:read'))[0]==403)
            bad=json.loads(json.dumps(body));bad['classification']['classification_id']='subcls_wrong'+uuid.uuid4().hex
            record('classification-denied',invoke('POST','/v1/billing-projections',bad)[0]==409)
            current='issuer-expiry-denied'
            native=p.read('native.json');cfg=native['clients'][PRODUCER]['config']
            p.require(p.api('PUT','/admin/clients/'+PRODUCER,{**cfg,'client_credentials_grant_access_token_lifespan':'2s'})[0]==200)
            try: short=token()
            finally:p.require(p.api('PUT','/admin/clients/'+PRODUCER,cfg)[0]==200)
            wait=p.claims(short)['exp']-time.time()+1;p.require(0<wait<10);time.sleep(wait)
            record('issuer-expiry-denied',invoke('GET',path,bearer=short)[0]==401)
            current='issuer-revocation-denied'
            bearer=token();p.require(invoke('GET',path,bearer=bearer)[0]==200)
            code,_,_=p.request('POST',p.ISSUER+'/oauth2/revoke',{'token':bearer,'token_type_hint':'access_token'},form=True,
                basic=(PRODUCER,native['clients'][PRODUCER]['secret']))
            code2,observed,_=p.request('POST',p.ISSUER+'/oauth2/introspect',{'token':bearer},form=True,
                basic=('baobab-dev-introspection',os.environ['DEV03_INTROSPECTION_SECRET']))
            record('issuer-revocation-denied',code==200 and code2==200 and observed['active'] is False
                   and p.claims(bearer)['exp']>time.time() and invoke('GET',path,bearer=bearer)[0]==401)
            current='event-durable-replay-conflict'
            event={'specversion':'1.0','id':str(uuid.uuid4()),'type':'com.baobab-platform.product.subscription.created.v1',
                'source':'urn:baobab-platform:service:baobab-cp','subject':'subscription:'+fixture['product_subscription_id'],
                'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'datacontenttype':'application/json',
                'dataschema':'https://contracts.baobab-platform.com/product/v1/events.schema.json#/$defs/subscriptionLifecycleEventData',
                'baobabscope':'tenant','correlationid':str(uuid.uuid4()),'tenantid':fixture['tenant_id'],
                'data':{'tenant_id':fixture['tenant_id'],'subscription_id':fixture['product_subscription_id'],'product_id':'dev-subscriptions','status':'ACTIVE'}}
            route='/internal/v1/cp-subscription-lifecycle-events'
            first=invoke('POST',route,event);again=invoke('POST',route,event)
            changed={**event,'correlationid':str(uuid.uuid4())}
            record('event-durable-replay-conflict',first[0]==202 and again[0]==200 and again[1]['replayed'] is True
                   and invoke('POST',route,changed)[0]==409)
            save('subscription-event.json',event)
        elif action in ('outage','recovery','revision','restart'):
            req=p.read('subscription-request.json');body=req['body'];path='/v1/tenants/'+fixture['tenant_id']+'/billing-projections/'+req['id']
            if action=='outage':record('cp-outage-denied',invoke('POST','/v1/billing-projections',body,key=req['key'])[0]==409)
            if action=='recovery':
                refresh();result=invoke('POST','/v1/billing-projections',body,key=req['key'])
                record('cp-recovery',result[0]==201 and result[1]['billing_subscription_id']==req['id'])
            if action=='revision':
                refresh();record('revision-before-replay',invoke('POST','/v1/billing-projections',body,key=req['key'])[0]==409)
            if action=='restart':
                refresh();result=invoke('GET',path);event=p.read('subscription-event.json')
                record('native-restart-persistence',result[0]==200 and result[1]['billing_subscription_id']==req['id']
                       and invoke('POST','/internal/v1/cp-subscription-lifecycle-events',event)[1]['replayed'] is True)
        elif action=='finish':
            for client in (PRODUCER,ASSESSOR):
                bearer=token(client,'baobab-control-plane' if client==ASSESSOR else 'baobab-subscriptions',CP_SCOPES if client==ASSESSOR else SCOPES)
                p.require(p.api('DELETE','/admin/clients/'+client)[0]==204)
                p.require(p.api('GET','/admin/clients/'+client)[0]==404)
                p.require(p.request('POST',p.ISSUER+'/oauth2/introspect',{'token':bearer},form=True,
                    basic=('baobab-dev-introspection',os.environ['DEV03_INTROSPECTION_SECRET']))[1]['active'] is False)
            save('subscriptions-issuer-cleanup.json',{'native_clients_deleted':True,'native_tokens_inactive':True})
        else:raise ValueError('UNKNOWN_SUBSCRIPTIONS_ACTION')
    except Exception:
        if current in contract.NATIVE:cases[current]={'result':'FAIL','reason':'NATIVE_ASSERTION_FAILED'};save('subscriptions-cases.json',cases)
        raise SystemExit('SUBSCRIPTIONS_NATIVE_PROBE_FAILED') from None
    contract.validate(cases)

if __name__=='__main__':
    import sys
    main(sys.argv[1])
