"""Private actual CMS/Nabhold protocol driver. No provider activation is inferred."""
import http.cookiejar
import html
import urllib.error
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid

import native_probe as p
import cms_contract

CONSUMER='baobab-int03-cms-consumer';VALIDATOR='baobab-int03-cms-validator';BFF='nabhold-dev-bff'
CMS='https://cms.baobab-dev.test';ESTATE='https://nabhold.baobab-dev.test'

def stage(name):
    # Fixed source-owned markers only; OAuth values/bodies stay in private state.
    print('DEV05_PROBE_STAGE='+name,flush=True)

def checkpoint(report):
    fd=os.open(p.ROOT/'.cms-report.tmp',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out:json.dump(report,out);out.flush();os.fsync(out.fileno())
    os.replace(p.ROOT/'.cms-report.tmp',p.ROOT/'cms-report.json')

def report():
    return p.read('cms-report.json') if (p.ROOT/'cms-report.json').exists() else cms_contract.fresh(os.environ['DEV01_RUN_ID'])

def config():
    bootstrap=p.read('bootstrap.json');own=next(e for e in bootstrap['enterprises'] if e['key']=='nabhold')
    return p.read('native.json'),bootstrap,own

def clients():
    native,_,_=config();state=p.read('state.json');secret=state['secrets']
    for name,key in ((CONSUMER,'cms_consumer'),(VALIDATOR,'cms_validator'),(BFF,'bff')):
        human=name==BFF
        scopes='openid authority:self' if human else 'context:validate' if name==VALIDATOR else 'context:resolve content:entry:resolve'
        cfg={'client_id':name,'client_secret':secret[key],'grant_types':['authorization_code'] if human else ['client_credentials'],
          'response_types':['code'] if human else [],'scope':scopes,'audience':['baobab-control-plane','baobab-cms'] if name==CONSUMER else ['baobab-control-plane'],
          'token_endpoint_auth_method':'client_secret_basic' if human else 'client_secret_post',
          'redirect_uris':[ESTATE+'/api/auth/callback'] if human else [],'metadata':{'environment':'development','development_run_id':state['run_id'],
          'owner':'baobab-platform/baobab-cms' if name==VALIDATOR else 'baobab-platform/infrastructure'},
          'client_credentials_grant_access_token_lifespan':'60s','authorization_code_grant_access_token_lifespan':'120s'}
        p.require(p.api('GET','/admin/clients/'+name)[0]==404)
        p.require(p.api('POST','/admin/clients',cfg)[0]==201)
        code,actual=p.api('GET','/admin/clients/'+name);p.require(code==200 and actual['metadata']['development_run_id']==state['run_id'] and actual['scope']==scopes)
        native['clients'][name]={'secret':secret[key],'config':cfg}
    fd=os.open(p.ROOT/'.native.tmp',os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out:json.dump(native,out);out.flush();os.fsync(out.fileno())
    os.replace(p.ROOT/'.native.tmp',p.ROOT/'native.json')


def token(name=CONSUMER,audience='baobab-cms',scope='content:entry:resolve',secret=None):
    native=p.read('native.json');credential=native['clients'][name]['secret'] if secret is None else secret
    code,body,_=p.request('POST',p.ISSUER+'/oauth2/token',{'grant_type':'client_credentials','client_id':name,'client_secret':credential,'audience':audience,'scope':scope},form=True)
    p.require(code==200 and body.get('access_token'),'SIGNED_TOKEN_ISSUANCE');return body['access_token']

def status(bearer):
    return p.request('POST',p.ISSUER+'/oauth2/introspect',{'token':bearer},form=True,basic=('baobab-dev-introspection',os.environ['DEV03_INTROSPECTION_SECRET']))

def context():
    _,_,own=config();bearer=token(audience='baobab-control-plane',scope='context:resolve')
    code,body,_=p.context(bearer,own);p.require(code==200 and body.get('tenant_id')==own['tenant_id'] and body.get('organisation_id')==own['organisation_id']);return bearer,body

def resolve(bearer,cid,key='home',tenant=None,preview=False):
    _,bootstrap,own=config()
    # A DIGITAL_ESTATE CMS record is scoped to its CP-issued legal actor as
    # well as estate, Market, locale and tenant. Do not omit that dimension or
    # guess a UUID: Shared-043 supplies an exact run-bound synthetic legal ID.
    body={'tenant_id':tenant or own['tenant_id'],'content_key':key,
        'legal_entity_id':own['legal_entity_id'],
        'digital_estate_id':own['digital_estate_id'],'market_id':bootstrap['market_ids']['ZA'],'locale':'en-ZA'}
    if preview:body['preview_mode']=True
    return p.request('POST',CMS+'/v1/content/resolve?context_id='+cid,body,bearer)

def deny(result,code,status_code):
    return result[0]==status_code and result[1].get('code')==code and 'record' not in result[1]

def empty(result):
    return result[0]==200 and isinstance(result[1],dict) and 'record' in result[1] and result[1]['record'] is None

def published(result,key):
    _,_,own=config();record=result[1].get('record') if result[0]==200 else None
    return bool(record and record.get('tenant_id')==own['tenant_id'] and record.get('content_key')==key and record.get('publication_state')=='PUBLISHED')


def record_failure_class(result, key):
    """Bounded classification only; never print CMS content, context or IDs."""
    http, body, _ = result
    if http != 200:
        return 'HTTP_DENIED' if http in (400,401,403,404,409,422) else 'HTTP_UNAVAILABLE'
    if not isinstance(body,dict):return 'INVALID_BODY'
    record=body.get('record')
    if record is None:return 'NO_RECORD'
    if not isinstance(record,dict):return 'INVALID_BODY'
    if record.get('publication_state')!='PUBLISHED':return 'NOT_PUBLISHED'
    if record.get('content_key')!=key:return 'WRONG_CONTENT_KEY'
    if not published(result,key):return 'WRONG_TENANT'
    return 'UNEXPECTED'


def estate_page(expected):
    """Bounded private HTML observation; only booleans enter custody.

    Next may commit an HTML error response before an async failure is rendered,
    so HTTP 500 alone cannot prove fail-closed content or a real published page.
    """
    opener=urllib.request.build_opener(p.NoRedirect(),urllib.request.HTTPSHandler(context=p.TLS))
    request=urllib.request.Request(ESTATE+'/',headers={'Accept':'text/html'})
    try:response=opener.open(request,timeout=45)
    except urllib.error.HTTPError as error:response=error
    with response:
        code=response.status;raw=response.read(1024*1024+1)
    p.require(len(raw)<=1024*1024)
    text=raw.decode('utf-8','strict')
    return code,all(html.escape(value) in text for value in expected)


def bff(report):
    stage('BFF_LOGIN')
    native,bootstrap,_=config();human=native['humans']['maker']
    stage('BFF_KRATOS_FLOW')
    code,flow,_=p.request('GET',p.KRATOS+'/self-service/login/api');p.require(code==200)
    stage('BFF_KRATOS_LOGIN')
    code,logged,_=p.request('POST',p.KRATOS+'/self-service/login?flow='+flow['id'],{'method':'password','identifier':human['email'],'password':human['password']});p.require(code==200)
    session=logged['session_token']
    jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(p.NoRedirect(),urllib.request.HTTPSHandler(context=p.TLS),urllib.request.HTTPCookieProcessor(jar))
    stage('BFF_INITIATE')
    code,_,location=p.request('POST',ESTATE+'/api/auth/login',{},headers={'Origin':ESTATE},opener=opener)
    p.require(code in (302,303) and location)
    stage('BFF_PKCE')
    authorization=urllib.parse.urlsplit(location);fields=urllib.parse.parse_qs(authorization.query)
    p.require(set(fields['scope'][0].split())=={'openid','authority:self'} and fields['code_challenge_method']==['S256'] and fields.get('nonce'))
    stage('BFF_AUTHORIZE')
    code,_,location=p.request('GET',location,opener=opener)
    for _ in range(10):
        p.require(code in (302,303) and location)
        url=urllib.parse.urlsplit(location);query=urllib.parse.parse_qs(url.query)
        code,current,_=p.request('GET',p.KRATOS+'/sessions/whoami',headers={'X-Session-Token':session})
        p.require(code==200 and current['active'] and current['identity']['id']==human['id'])
        if url.netloc=='rp.baobab-dev.test' and url.path=='/login':
            challenge=query['login_challenge'][0];code,challenge_body=p.api('GET','/admin/oauth2/auth/requests/login?login_challenge='+challenge)
            p.require(code==200 and challenge_body['client']['client_id']==BFF)
            code,accepted=p.api('PUT','/admin/oauth2/auth/requests/login/accept?login_challenge='+challenge,{'subject':human['id'],'remember':False})
            p.require(code==200);location=accepted['redirect_to']
        elif url.netloc=='rp.baobab-dev.test' and url.path=='/consent':
            challenge=query['consent_challenge'][0];code,actual=p.api('GET','/admin/oauth2/auth/requests/consent?consent_challenge='+challenge)
            p.require(code==200 and actual['subject']==human['id'] and actual['client']['client_id']==BFF)
            code,accepted=p.api('PUT','/admin/oauth2/auth/requests/consent/accept?consent_challenge='+challenge,{'grant_scope':actual['requested_scope'],'grant_access_token_audience':['baobab-control-plane'],'remember':False})
            p.require(code==200);location=accepted['redirect_to']
        elif url.netloc=='nabhold.baobab-dev.test' and url.path=='/api/auth/callback':
            stage('BFF_CALLBACK')
            code,_,_=p.request('GET',location,opener=opener,timeout=30);p.require(code==200);break
        else:
            p.require(url.netloc=='hydra.int03.test')
        code,_,location=p.request('GET',location,opener=opener)
    else:raise ValueError('DEV05_BFF_CALLBACK_FAILED')
    stage('BFF_SESSION')
    code,identity,_=p.request('GET',ESTATE+'/api/auth/session',opener=opener)
    p.require(code==200 and identity['principalId']==bootstrap['maker_id'])
    report['component_checks']['native_bff_login_session']=True
    p.require(set(identity)=={'principalId','expiresAt','csrfToken'});report['component_checks']['bff_token_free_session']=True
    cookies=[c for c in jar if c.name=='__Host-nabhold-session']
    p.require(len(cookies)==1 and cookies[0].secure and cookies[0].path=='/' and not cookies[0].domain_specified and cookies[0].has_nonstandard_attr('HttpOnly') and str(cookies[0].get_nonstandard_attr('SameSite')).lower()=='strict' and re.fullmatch(r'[A-Za-z0-9_-]{43}',cookies[0].value))
    report['component_checks']['bff_secure_opaque_cookie']=True
    stage('BFF_LOGOUT');old=cookies[0]
    code,_,_=p.request('POST',ESTATE+'/api/auth/logout',{'csrfToken':identity['csrfToken']},form=True,headers={'Origin':ESTATE},opener=opener)
    p.require(code==303);jar.set_cookie(old)
    p.require(p.request('GET',ESTATE+'/api/auth/session',opener=opener)[0]==401)
    report['component_checks']['native_bff_logout_custody']=True


def main(action):
    if action=='clients':
        clients()
        return
    if action=='health':
        result={'cms':0,'estate':0}
        for name,url in [('cms',CMS+'/api/health/live'),('estate',ESTATE+'/api/auth/session')]:
            try:result[name]=p.request('GET',url,timeout=10)[0]
            except (OSError,ValueError):
                # Startup transport/JSON failures remain explicit status zero.
                continue
        print(json.dumps(result));return
    value=report();current={'initial':'published-home-nav-footer','draft':'draft-or-preview','withdraw':'withdrawn-content',
        'outage':'dependency-outage-and-restoration','restored':'dependency-outage-and-restoration','finish':'disabled-caller'}.get(action,'published-home-nav-footer')
    def record(case,ok):
        nonlocal current
        current=case;ok=ok() if callable(ok) else ok;p.require(ok,'DEV05_ASSERTION_FAILED');value['cases'][case]={'result':'PASS','reason':'OBSERVED'};checkpoint(value)
    try:
        native,bootstrap,own=config()
        if action=='initial':
            p.require(not (p.ROOT/'cms-started').exists());p.write('cms-started',{})
            bff(value);stage('CMS_CONTEXT');cp_token,ctx=context();bearer=token()
            code,actual,_=status(bearer);p.require(code==200 and actual['active'] is True);value['component_checks']['issuer_readback_active']=True
            validator=token(VALIDATOR,'baobab-control-plane','context:validate')
            code,actual,_=p.request('POST',p.CP+'/v1/platform-context/validate',{'context_id':ctx['context_id'],'subject_token':bearer},validator)
            p.require(code==200 and actual['authority_purpose']=='RUNTIME' and actual['organisation_id']==own['organisation_id']);value['component_checks']['cp_validator_subject_accepted']=True
            stage('CMS_RECORDS')
            records=[resolve(bearer,ctx['context_id'],key) for key in ('home','navigation','footer')]
            for result,key in zip(records,('home','navigation','footer')):
                if not published(result,key):
                    print('DEV05_RECORD_DIAGNOSTIC='+key.upper()+'_'+record_failure_class(result,key),flush=True)
            p.require(all(published(result,key) for result,key in zip(records,('home','navigation','footer'))))
            expected=[records[0][1]['record']['data']['headline'],records[2][1]['record']['data']['statement']]
            p.require(all(isinstance(value,str) and value for value in expected))
            value['component_checks']['native_cms_published_home_navigation_footer']=True
            stage('CANONICAL_RESOLUTION')
            code,decision,_=p.request('POST',p.CP+'/v1/capabilities/resolve',{'context_id':ctx['context_id'],'capability_key':'content.entry.resolve','required_contract_version':1,'correlation_id':str(uuid.uuid4())},cp_token)
            declaration=(p.ROOT/'sources/baobab-cms/.baobab/capability-provider.yaml').read_text()
            partial='implementation_status: PARTIAL' in declaration
            value['component_checks']['provider_declared_partial']=partial
            if partial or decision.get('decision')!='RESOLVED':
                p.require(code==200 and decision.get('decision')=='DENIED' and not decision.get('invocation'))
                value['component_checks']['canonical_capability_denied']=True
                value['cases']['published-home-nav-footer']={'result':'BLOCKED','reason':'PROVIDER_NOT_ELIGIBLE'}
                value['cases']['missing-grant']={'result':'BLOCKED','reason':'CANONICAL_CAPABILITY_NOT_RESOLVED'}
                # The actual estate must fail closed rather than serve defaults.
                _,visible=estate_page(expected);p.require(not visible)
                value['component_checks']['estate_canonical_path_unavailable']=True
            else:
                p.require(code==200 and decision.get('invocation'))
                estate_status,visible=estate_page(expected);p.require(estate_status==200 and visible)
                record('published-home-nav-footer',lambda:True)
                # A separate real tenant/context lacking this grant is the
                # control. An unknown capability is not a missing-grant proof.
                other=next(e for e in bootstrap['enterprises'] if e['key']=='zuribeans')
                separate=p.token(other['client_id'],native);code,otherctx,_=p.context(separate,other);p.require(code==200)
                code,denied,_=p.request('POST',p.CP+'/v1/capabilities/resolve',{'context_id':otherctx['context_id'],
                    'capability_key':'content.entry.resolve','required_contract_version':1,'correlation_id':str(uuid.uuid4())},separate)
                record('missing-grant',lambda:code==200 and denied.get('decision')=='DENIED' and denied.get('reason_code')=='GRANT_NOT_FOUND' and not denied.get('invocation'))
            record('wrong-audience-token',lambda:deny(resolve(cp_token,ctx['context_id']),'AUTHENTICATION_REQUIRED',401))
            record('wrong-credential',lambda:deny(resolve('invalid-credential',ctx['context_id']),'AUTHENTICATION_REQUIRED',401))
            # Actual short lifespan, not an edited signed token.
            current='expired-caller-token'
            cfg=native['clients'][CONSUMER]['config'];short=dict(cfg,client_credentials_grant_access_token_lifespan='2s')
            p.require(p.api('PUT','/admin/clients/'+CONSUMER,short)[0]==200)
            expired=token();p.require(p.api('PUT','/admin/clients/'+CONSUMER,cfg)[0]==200)
            delay=p.claims(expired)['exp']-time.time()+1;p.require(0<delay<10);time.sleep(delay)
            record('expired-caller-token',lambda:deny(resolve(expired,ctx['context_id']),'AUTHENTICATION_REQUIRED',401))
            current='revoked-caller-token'
            revoked=token();p.require(published(resolve(revoked,ctx['context_id']),'home'))
            p.require(p.request('POST',p.ISSUER+'/oauth2/revoke',{'token':revoked,'client_id':CONSUMER,'client_secret':native['clients'][CONSUMER]['secret']},form=True)[0]==200)
            code,actual,_=status(revoked);p.require(code==200 and actual['active'] is False)
            record('revoked-caller-token',lambda:deny(resolve(revoked,ctx['context_id']),'AUTHENTICATION_REQUIRED',401) and p.claims(revoked)['exp']>time.time())
            value['component_checks']['revoked_before_expiry']=True
            fresh=token();p.require(published(resolve(fresh,ctx['context_id']),'home'));value['component_checks']['fresh_after_revoke']=True
            current='wrong-owner-or-context'
            other=next(e for e in bootstrap['enterprises'] if e['key']=='zuribeans');neighbor_token=p.token(other['client_id'],native)
            code,neighbor,_=p.context(neighbor_token,other);p.require(code==200)
            record('wrong-owner-or-context',lambda:deny(resolve(fresh,neighbor['context_id']),'CONTENT_CONTEXT_REJECTED',403))
            record('neighbour-tenant',lambda:deny(resolve(fresh,ctx['context_id'],tenant=other['tenant_id']),'CONTENT_CONTEXT_REJECTED',403))
            current='validator-negatives'
            code,actual,_=p.request('POST',p.CP+'/v1/platform-context/validate',{'context_id':ctx['context_id'],'subject_token':'invalid.subject.bearer'},validator)
            record('validator-negatives',lambda:code==401 and actual.get('code')=='SUBJECT_TOKEN_INVALID' and deny(resolve(fresh,str(uuid.uuid4())),'CONTENT_CONTEXT_REJECTED',403))
        elif action=='draft':
            _,ctx=context();bearer=token()
            record('draft-or-preview',lambda:deny(resolve(bearer,ctx['context_id'],preview=True),'CONTENT_PREVIEW_NOT_PERMITTED',403) and empty(resolve(bearer,ctx['context_id'])))
        elif action=='withdraw':
            _,ctx=context();record('withdrawn-content',lambda:empty(resolve(token(),ctx['context_id'])))
        elif action=='outage':
            # Keep a prior, genuinely CP-issued context privately across outage.
            ctx=p.read('cms-last-context.json') if (p.ROOT/'cms-last-context.json').exists() else None
            p.require(ctx is not None)
            result=resolve(token(),ctx['context_id']);p.require(deny(result,'CONTENT_CONTEXT_UNAVAILABLE',503));value['component_checks']['cp_outage_observed']=True;checkpoint(value)
        elif action=='restored':
            p.require(value['component_checks'].get('cp_outage_observed') is True)
            _,ctx=context();record('dependency-outage-and-restoration',lambda:published(resolve(token(),ctx['context_id']),'home'))
            value['component_checks']['provider_outage_restored']=True
        elif action=='finish':
            _,ctx=context();bearer=token();p.require(published(resolve(bearer,ctx['context_id']),'home'))
            p.require(p.api('DELETE','/admin/clients/'+CONSUMER)[0]==204 and p.api('GET','/admin/clients/'+CONSUMER)[0]==404)
            code,actual,_=status(bearer);p.require(code==200 and actual['active'] is False)
            record('disabled-caller',lambda:deny(resolve(bearer,ctx['context_id']),'AUTHENTICATION_REQUIRED',401) and p.claims(bearer)['exp']>time.time())
            for name in (VALIDATOR,BFF):p.require(p.api('DELETE','/admin/clients/'+name)[0]==204 and p.api('GET','/admin/clients/'+name)[0]==404)
            value['component_checks']['native_clients_deleted']=True;value['component_checks']['native_tokens_inactive']=True
            value['cases']['teardown']={'result':'BLOCKED','reason':'TEARDOWN_PENDING'}
        else:raise ValueError('DEV05_UNKNOWN_ACTION')
        if action in ('initial','draft','withdraw','restored'):
            _,ctx=context()
            path=p.ROOT/'cms-last-context.json';path.write_text(json.dumps(ctx));path.chmod(0o600)
        cms_contract.validate(value,os.environ['DEV01_RUN_ID']);checkpoint(value)
        print('DEV05_STAGE_'+action.upper()+'_OBSERVED')
    except Exception:
        value['cases'][current]={'result':'FAIL','reason':'ASSERTION_FAILED'}
        for row in value['cases'].values():
            if row['reason']=='NOT_EXECUTED':row['reason']='PREREQUISITE_FAILED'
        checkpoint(value)
        raise SystemExit('DEV05_PROBE_FAILED') from None

if __name__=='__main__':main(sys.argv[1])
