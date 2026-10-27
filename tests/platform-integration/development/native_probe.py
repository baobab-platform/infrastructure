"""Private DEV-03 native-provider driver. Tokens/claims/credentials never printed.

The small relying party is a disposable protocol driver, not IAM's registered
production hook or an estate BFF. Only actual Hydra signs tokens; Kratos owns
password/session validation; CP alone owns identity/context/grant decisions.
"""
import base64
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT=Path('/run/dev01')
ISSUER='https://hydra.int03.test'
KRATOS='https://kratos.baobab-dev.test'
CP='https://cp.baobab-dev.test'
CALLBACK='https://rp.baobab-dev.test/callback'
TLS=ssl.create_default_context(cafile='/tls/ca.pem');TLS.minimum_version=ssl.TLSVersion.TLSv1_3
ADMIN_SCOPES='changeset:write changeset:approve changeset:read'
# Proof-only Hydra clients have an issuer-enforced 55s ceiling, safely below
# the verifier's unchanged 60s upper bound. Hydra may sign after RequestedAt;
# the margin accommodates that delay without permitting any longer token.
PROOF_LIFESPAN='55s'
WORKLOADS=('baobab-dev-nabhold-estate','baobab-dev-zuribeans-estate','baobab-dev-thamani-estate','baobab-dev-equator-estate-estate','baobab-int03c-issuer-owner','baobab-int03c-issuer-verifier')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args): return None

def require(ok,code='PROVIDER_OBSERVATION_FAILED'):
    if not ok: raise ValueError(code)

def write(name,value):
    fd=os.open(ROOT/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out: json.dump(value,out);out.flush();os.fsync(out.fileno())

def read(name): return json.loads((ROOT/name).read_text())

def request(method,url,data=None,token=None,form=False,basic=None,headers=None,opener=None,timeout=8):
    # Private provider admin planes are the only permitted cleartext origins.
    parsed=urllib.parse.urlsplit(url)
    require((parsed.scheme=='https' and parsed.hostname in ('hydra.int03.test','kratos.baobab-dev.test','cp.baobab-dev.test','cms.baobab-dev.test','nabhold.baobab-dev.test','pulse.baobab-dev.test','subscriptions.baobab-dev.test','engine.baobab-dev.test')) or
            (parsed.scheme=='http' and parsed.netloc in ('hydra:4445','kratos:4434')),'UNTRUSTED_ENDPOINT')
    body=(urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()) if data is not None else None
    h={'Accept':'application/json',**(headers or {})}
    if body is not None: h['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
    if token: h['Authorization']='Bearer '+token
    if basic: h['Authorization']='Basic '+base64.b64encode((basic[0]+':'+basic[1]).encode()).decode()
    req=urllib.request.Request(url,body,h,method=method)
    client=opener or urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=TLS))
    try: response=client.open(req,timeout=timeout)
    except urllib.error.HTTPError as error: response=error
    raw=response.read(65537);require(len(raw)<=65536,'BOUNDED_RESPONSE')
    kind=response.headers.get('Content-Type','')
    return response.status,json.loads(raw) if raw and 'json' in kind else None,response.headers.get('Location')

def api(method,path,data=None):
    code,body,_=request(method,'http://hydra:4445'+path,data);return code,body

def subjects():
    value={'humans':{},'clients':{}}
    ids={}
    for role in ('maker','checker'):
        email='synthetic-'+role+'-'+os.environ['DEV01_RUN_ID']+'@example.invalid';password=secrets.token_urlsafe(32)
        code,body,_=request('POST','http://kratos:4434/admin/identities',{'schema_id':'default','traits':{'email':email},'credentials':{'password':{'config':{'password':password}}}})
        require(code==201 and body['state']=='active','KRATOS_CREATE')
        native_id=body['id'];code,actual,_=request('GET','http://kratos:4434/admin/identities/'+native_id)
        require(code==200 and actual['traits']['email']==email and actual['state']=='active','KRATOS_READBACK')
        ids[role]=native_id;value['humans'][role]={'id':native_id,'email':email,'password':password}
    require(ids['maker']!=ids['checker'],'DISTINCT_REAL_IDENTITIES')
    clients=list(WORKLOADS)+['baobab-dev-human','baobab-dev-introspection']
    state=read('state.json');profile=state.get('engine_profile')
    identities={v['client_id']:v for v in profile['iam'].values()} if profile else {}
    require(not set(identities).intersection(clients),'PROFILE_CLIENT_COLLISION')
    clients+=sorted(identities)
    buyer_configs = read('buyer-client-spec.json') if state.get('buyer_identity_profile') else {}
    require(not set(buyer_configs).intersection(clients),'PROFILE_CLIENT_COLLISION')
    clients+=sorted(buyer_configs)
    for name in clients:
        secret=(os.environ['DEV03_INTROSPECTION_SECRET'] if name=='baobab-dev-introspection' else
                os.environ['DEV04_VERIFIER_SECRET'] if name=='baobab-int03c-issuer-verifier' else secrets.token_urlsafe(32))
        human=name=='baobab-dev-human'
        proof=name.startswith('baobab-int03c-')
        config={'client_id':name,'client_secret':secret,'grant_types':['authorization_code'] if human else ['client_credentials'],
                'response_types':['code'] if human else [],'scope':ADMIN_SCOPES if human else 'context:resolve',
                'audience':['baobab-control-plane'],'token_endpoint_auth_method':'client_secret_post' if proof else 'client_secret_basic',
                'redirect_uris':[CALLBACK] if human else [],'metadata':{'development_run_id':os.environ['DEV01_RUN_ID'],'environment':'development','owner':'baobab-platform/infrastructure',**({'int03c_run_id':os.environ['DEV01_RUN_ID']} if proof else {})},
                'client_credentials_grant_access_token_lifespan':PROOF_LIFESPAN if proof else '120s','authorization_code_grant_access_token_lifespan':'120s'}
        if name in identities:
            role=next(role for role,item in profile['iam'].items() if item['client_id']==name)
            secret=state['secrets']['engine_'+role]
            config.update(client_secret=secret,scope=' '.join(identities[name]['scopes']),audience=identities[name]['audiences'],token_endpoint_auth_method='client_secret_post')
        if name in buyer_configs:
            config=buyer_configs[name]; secret=config['client_secret']
        code,_=api('GET','/admin/clients/'+name);require(code==404,'REFUSE_EXISTING_ISSUER_CLIENT')
        code,created=api('POST','/admin/clients',config);require(code==201 and created['client_id']==name,'HYDRA_CREATE')
        code,actual=api('GET','/admin/clients/'+name)
        require(code==200 and actual['metadata']['development_run_id']==os.environ['DEV01_RUN_ID'] and actual['grant_types']==config['grant_types'] and actual['audience']==config['audience'],'HYDRA_READBACK')
        value['clients'][name]={'secret':secret,'config':config}
    write('native.json',value);write('subjects.json',ids)
    print('PROVIDER_SUBJECTS_OBSERVED')

class Hook(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        # Private run-owned OCI publication, not an identity or provider stub.
        # Only content-addressed actual built-image bytes can be read.
        import re, hashlib, shutil
        match=re.fullmatch(r'/v2/(baobab-[a-z0-9-]{1,56})/(manifests|blobs)/sha256:([0-9a-f]{64})',self.path)
        try:
            require(match is not None)
            engine,kind,digest=match.groups();state=read('state.json')
            if state.get('engine_profile') and engine==state['engine_profile']['subject_engine']:
                require(state.get('engine_oci_manifest_digest'));root=ROOT/'engine-oci'
            elif engine=='baobab-pulse':
                require(state.get('external_api') is True);root=ROOT/'external-oci'
            else:
                require(engine=='baobab-cms' and isinstance(state.get('cms'),dict) and state.get('cms_oci_manifest_digest'));root=ROOT/'cms-oci'
            path=root/'manifest.json' if kind=='manifests' else root/'blobs'/digest
            require(path.is_file())
            if kind=='manifests':require(hashlib.sha256(path.read_bytes()).hexdigest()==digest)
            self.send_response(200)
            self.send_header('Content-Type','application/vnd.oci.image.manifest.v1+json' if kind=='manifests' else 'application/octet-stream')
            self.send_header('Docker-Content-Digest','sha256:'+digest)
            self.send_header('Content-Length',str(path.stat().st_size));self.end_headers()
            with path.open('rb') as source:shutil.copyfileobj(source,self.wfile)
        except Exception:
            self.send_response(404);self.end_headers()

    def do_POST(self):
        client=None
        try:
            if self.path=='/introspect':
                return self.introspect()
            require(self.path=='/token-hook' and hmac.compare_digest(self.headers.get('X-DEV03-Hook-Key',''),os.environ['DEV03_HOOK_KEY']))
            size=int(self.headers.get('Content-Length','0'));require(0<size<65536)
            body=json.loads(self.rfile.read(size)); req=body['request'];session=body['session'];client=req['client_id'];grant=req['grant_types']
            native=read('native.json');require(client in native['clients'] and session['client_id']==client)
            if read('state.json').get('buyer_identity_profile') and client in ('baobab-dev-zuribeans-bff','baobab-dev-trade-buyer-validator'):
                from dev07_buyer_fixture import normalised_claims
                # The real Kratos assurance was bound at Hydra consent
                # to this access-token session. Refuse disagreement with a
                # separately-present ID-token value; never infer an AAL.
                id_token=session['id_token']
                access=session.get('access_token',{})
                assurance=(access.get('acr') if isinstance(access,dict) else None)
                id_assurance=id_token.get('acr')
                if id_assurance is not None and assurance is not None:
                    require(id_assurance==assurance,'DEV07_ASSURANCE_MISMATCH')
                subject=id_token['subject']
                if client=='baobab-dev-zuribeans-bff' and grant==['authorization_code']:
                    # Hydra 26.2 does not expose consent AAL to this hook.
                    # Re-authenticate the already verified private Kratos
                    # session at issuance time, bound to exact BFF + subject.
                    # This is synthetic dev identity evidence, not a policy
                    # bypass and not a production IAM issuer implementation.
                    witness=read('dev07-kratos-session.json')
                    owner=read('state.json')
                    require(owner.get('buyer_identity_profile') is True and
                            witness['run_id']==owner['run_id'] and
                            witness['client_id']==client and
                            witness['subject']==subject and
                            time.time()<witness['expires_at']<=owner['deadline'],
                            'DEV07_KRATOS_WITNESS_REFUSED')
                    status,kratos,_=request('GET',KRATOS+'/sessions/whoami',
                        headers={'X-Session-Token':witness['session_token']})
                    require(status==200 and kratos['active'] is True and
                            kratos['identity']['id']==subject,
                            'DEV07_KRATOS_SESSION_NOT_CURRENT')
                    current_acr=kratos.get('authenticator_assurance_level')
                    require(current_acr in ('aal1','aal2'),
                            'DEV07_KRATOS_ASSURANCE_ABSENT')
                    require(assurance in (None,current_acr) and
                            id_assurance in (None,current_acr),
                            'DEV07_ASSURANCE_MISMATCH')
                    assurance=current_acr
                claims=normalised_claims(client,grant,subject,
                    {x['id'] for x in native['humans'].values()},
                    assurance if assurance is not None else id_assurance)
                raw=json.dumps({'session':{'access_token':claims}}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
                return
            human=client in ('baobab-dev-human','nabhold-dev-bff');require(grant==(['authorization_code'] if human else ['client_credentials']))
            if human: require(session['id_token']['subject'] in {x['id'] for x in native['humans'].values()})
            else: require(client in tuple(v['client_id'] for v in read('state.json').get('engine_profile',{}).get('iam',{}).values())+WORKLOADS+('baobab-int03-cms-consumer','baobab-int03-cms-validator','baobab-dev-external-api','baobab-dev-pulse-validator','baobab-dev-cp-subscriptions','baobab-dev-subscriptions-assessor') and session['id_token']['subject']==client)
            # Identity normalisation only. No tenant/org/capability/grant claims.
            claims={'actor_type':'human' if human else 'workload','azp':client}
            if human: claims['realm_access']={'roles':['cp:platform-admin']}
            raw=json.dumps({'session':{'access_token':claims}}).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
        except Exception as error:
            # Closed DEV-07 diagnostic for this one synthetic BFF only.
            # The run directory stays private; no webhook/request/token body
            # or exception text is copied into exported evidence or logs.
            if client=='baobab-dev-zuribeans-bff':
                reason='OTHER'
                if isinstance(error,ValueError) and str(error) in ('DEV07_GRANT_REFUSED','DEV07_ASSURANCE_ABSENT'):
                    reason=str(error)
                elif isinstance(error,KeyError):
                    key=error.args[0] if len(error.args)==1 else None
                    if key in ('subject','id_token','acr','grant_types'):
                        reason='MISSING_'+key.upper()
                try:write('dev07-token-hook-refusal.json',{'reason':reason})
                except (FileExistsError,OSError):pass
            self.send_response(403);self.end_headers()

    def introspect(self):
        try:
            require(os.environ.get('DEV05_PROFILE')=='native-cms')
            size=int(self.headers.get('Content-Length','0'));require(0<size<16384)
            fields=urllib.parse.parse_qs(self.rfile.read(size).decode(),strict_parsing=True)
            require(all(len(v)==1 for v in fields.values()) and 'token' in fields)
            if self.headers.get('Authorization','').startswith('Basic '):
                require('client_id' not in fields and 'client_secret' not in fields)
                name,secret=base64.b64decode(self.headers['Authorization'][6:],validate=True).decode().split(':',1)
            else:
                name=fields['client_id'][0];secret=fields['client_secret'][0]
            native=read('native.json')
            require(name in ('baobab-int03-cms-consumer','baobab-int03-cms-validator','nabhold-dev-bff') and
                    hmac.compare_digest(secret,native['clients'][name]['secret']))
            code,body,_=request('POST','http://hydra:4445/admin/oauth2/introspect',{'token':fields['token'][0]},form=True)
            require(code==200)
            if body.get('active') is True:
                require((name=='baobab-int03-cms-validator' and body.get('client_id') in ('baobab-int03-cms-validator','baobab-int03-cms-consumer')) or body.get('client_id')==name)
                # Hydra's native extension container holds issuer-produced
                # custom claims. Promote only actor_type, rejecting conflicts.
                extra=body.get('ext',{})
                if 'actor_type' in extra:
                    require('actor_type' not in body or body['actor_type']==extra['actor_type'])
                    body['actor_type']=extra['actor_type']
            raw=json.dumps(body).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
        except Exception:
            self.send_response(401);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"error":"invalid_client"}')

def provider_ready():
    observed={'hydra':0,'kratos':0}
    try: observed['hydra']=request('GET',ISSUER+'/.well-known/openid-configuration',timeout=3)[0]
    except (OSError,ValueError):
        # Startup transport/JSON errors remain explicit status 0, never ready.
        pass
    for path in ('/admin/health/ready','/health/ready'):
        try: observed['kratos']=request('GET','http://kratos:4434'+path,timeout=3)[0]
        except (OSError,ValueError): continue
        if observed['kratos']==200: break
    return observed

def health():
    code,body,_=request('GET',ISSUER+'/.well-known/openid-configuration');require(code==200 and body['issuer']==ISSUER)
    require(provider_ready()['kratos']==200)
    require(request('GET',CP+'/healthz')[0]==200)
    print('REAL_IAM_CP_HEALTH_OBSERVED')

def token(name,native=None):
    native=native or read('native.json')
    form={'grant_type':'client_credentials','scope':'context:resolve','audience':'baobab-control-plane'}
    credential=native['clients'][name]
    auth=(name,credential['secret'])
    if credential['config']['token_endpoint_auth_method']=='client_secret_post':
        form.update(client_id=name,client_secret=credential['secret']);auth=None
    code,body,_=request('POST',ISSUER+'/oauth2/token',form,form=True,basic=auth)
    require(code==200 and body.get('access_token'),'SIGNED_TOKEN_ISSUANCE')
    return body['access_token']

def claims(token):
    # Expiry and subject are observations only: CP verifies signature and claims.
    part=token.split('.')[1];return json.loads(base64.urlsafe_b64decode(part+'='*((-len(part))%4)))

def validate_callback(location,state,callback=CALLBACK):
    url=urllib.parse.urlsplit(location);values=urllib.parse.parse_qs(url.query)
    require(url.scheme=='https' and url.netloc=='rp.baobab-dev.test' and url.path==urllib.parse.urlsplit(callback).path and callback in (CALLBACK,'https://rp.baobab-dev.test/dev07/callback') and not url.fragment
            and values.get('state')==[state] and len(values.get('code',[]))==1 and 'error' not in values,'CALLBACK_BINDING_DENIED')

def native_human(role,native,negative=None,*,client_id='baobab-dev-human',scope=ADMIN_SCOPES,audience='baobab-control-plane',callback=CALLBACK,return_code=False):
    if client_id!='baobab-dev-human' or return_code:
        require(read('state.json').get('buyer_identity_profile') is True, 'DEV07_PROFILE_REQUIRED')
        require((client_id=='baobab-dev-human' and scope==ADMIN_SCOPES and audience=='baobab-control-plane' and callback==CALLBACK) or
                (client_id=='baobab-dev-zuribeans-bff' and scope=='openid trade:buy' and audience=='baobab-trade' and callback=='https://rp.baobab-dev.test/dev07/callback'), 'DEV07_CODE_PROFILE_REFUSED')
    human=native['humans'][role]
    code,flow,_=request('GET',KRATOS+'/self-service/login/api');require(code==200)
    code,login,_=request('POST',KRATOS+'/self-service/login?flow='+flow['id'],{'method':'password','identifier':human['email'],'password':human['password']})
    require(code==200 and login['session']['active'] and login['session']['identity']['id']==human['id'],'REAL_KRATOS_LOGIN')
    session_token=login['session_token']
    def current():
        code,actual,_=request('GET',KRATOS+'/sessions/whoami',headers={'X-Session-Token':session_token})
        require(code==200 and actual['active'] and actual['identity']['id']==human['id'],'KRATOS_CURRENT_SESSION')
    current()
    if client_id=='baobab-dev-zuribeans-bff':
        # Only this synthetic, run-owned qualification BFF may use a direct
        # Kratos session witness. Never infer acr from client claims/consent.
        owner=read('state.json')
        require(owner.get('buyer_identity_profile') is True,'DEV07_PROFILE_REQUIRED')
        witness=ROOT/'dev07-kratos-session.json'
        witness.unlink(missing_ok=True)
        write('dev07-kratos-session.json',{
            'run_id':owner['run_id'],'client_id':client_id,
            'subject':human['id'],'session_token':session_token,
            'expires_at':min(owner['deadline'],time.time()+120)})
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(32)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    opener=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=TLS),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    query=urllib.parse.urlencode({'client_id':client_id,'response_type':'code','redirect_uri':callback,'scope':scope,'state':state,'code_challenge':challenge,'code_challenge_method':'S256','audience':audience})
    code,_,location=request('GET',ISSUER+'/oauth2/auth?'+query,opener=opener)
    for _ in range(8):
        require(code in (302,303) and location,'REAL_AUTHORIZATION_REDIRECT')
        url=urllib.parse.urlsplit(location);params=urllib.parse.parse_qs(url.query)
        if url.scheme=='https' and url.netloc=='rp.baobab-dev.test' and url.path=='/login':
            current();nonce=params['login_challenge'][0]
            status,actual=api('GET','/admin/oauth2/auth/requests/login?login_challenge='+nonce)
            require(status==200 and actual['client']['client_id']==client_id,'LOGIN_CHALLENGE_BINDING')
            status,accepted=api('PUT','/admin/oauth2/auth/requests/login/accept?login_challenge='+nonce,{'subject':human['id'],'remember':False,'acr':login['session']['authenticator_assurance_level']})
            require(status==200);location=accepted['redirect_to']
        elif url.scheme=='https' and url.netloc=='rp.baobab-dev.test' and url.path=='/consent':
            current();nonce=params['consent_challenge'][0]
            status,actual=api('GET','/admin/oauth2/auth/requests/consent?consent_challenge='+nonce)
            require(status==200 and actual['subject']==human['id'] and actual['client']['client_id']==client_id and set(actual['requested_scope'])<=set(scope.split()),'CONSENT_BINDING')
            consent={'grant_scope':actual['requested_scope'],
                     'grant_access_token_audience':[audience],'remember':False}
            if client_id=='baobab-dev-zuribeans-bff':
                # Hydra's token hook reads assurance from the consent session.
                # Bind it to this real Kratos login, which was independently
                # checked above via WhoAmI, instead of synthesizing an acr.
                kratos_acr=login['session'].get('authenticator_assurance_level')
                require(kratos_acr in ('aal1','aal2'),'DEV07_KRATOS_ASSURANCE_ABSENT')
                # Hydra's token hook observes the OAuth access-token
                # session; the ID-token session alone need not be projected
                # into that hook. Carry the same real Kratos AAL in both
                # channels, never a caller-supplied assurance value.
                consent['session']={'access_token':{'acr':kratos_acr},
                                    'id_token':{'acr':kratos_acr}}
            status,accepted=api('PUT','/admin/oauth2/auth/requests/consent/accept?consent_challenge='+nonce,consent)
            require(status==200);location=accepted['redirect_to']
        elif url.scheme=='https' and url.netloc=='rp.baobab-dev.test' and url.path==urllib.parse.urlsplit(callback).path:
            if negative=='wrong_state':
                try: validate_callback(location,state+'wrong',callback)
                except ValueError: return True
                raise ValueError('WRONG_STATE_ACCEPTED')
            validate_callback(location,state,callback)
            if return_code:
                require(negative is None, 'CODE_PACKET_NEGATIVE_REFUSED')
                return {'code':params['code'][0],'verifier':verifier,'redirect_uri':callback}
            exchange={'grant_type':'authorization_code','code':params['code'][0],'redirect_uri':callback,'code_verifier':verifier}
            if negative=='wrong_pkce': exchange['code_verifier']=secrets.token_urlsafe(32)
            status,body,_=request('POST',ISSUER+'/oauth2/token',exchange,form=True,basic=(client_id,native['clients'][client_id]['secret']))
            if negative=='wrong_pkce':
                require(status==400 and body.get('error')=='invalid_grant','REAL_PKCE_MISMATCH_DENIED')
                return True
            require(status==200 and claims(body['access_token'])['sub']==human['id'],'REAL_SIGNED_HUMAN_TOKEN')
            if negative=='code_replay':
                bad_status,bad,_=request('POST',ISSUER+'/oauth2/token',exchange,form=True,basic=(client_id,native['clients'][client_id]['secret']))
                require(bad_status==400 and bad.get('error')=='invalid_grant','CODE_REPLAY_DENIED')
                return True
            return body['access_token']
        else:
            require(url.scheme=='https' and url.netloc=='hydra.int03.test','REDIRECT_ORIGIN')
        code,_,location=request('GET',location,opener=opener)
    raise ValueError('AUTHORIZATION_DID_NOT_COMPLETE')

def context(token,enterprise):
    return request('POST',CP+'/v1/platform-context/resolve',{'tenant_id':enterprise['tenant_id'],'organisation_id':enterprise['organisation_id'],'country_code':'ZA'},token)

def authority():
    require(not (ROOT/'authority-started').exists(),'FRESH_AUTHORITY_RUN_REQUIRED');write('authority-started',{})
    native=read('native.json');bootstrap=read('bootstrap.json');state=read('state.json');observed={}
    def check(name,ok): require(ok,'DEV03_'+name.upper());observed[name]=True
    a=next(e for e in bootstrap['enterprises'] if e['key']=='zuribeans');external=next(e for e in bootstrap['enterprises'] if e['key']=='external-client');sibling=next(e for e in bootstrap['enterprises'] if e['key']=='thamani')
    name=a['client_id'];credential=native['clients'][name]
    bearer=token(name,native);positive_status,positive,_=context(bearer,a)
    check('actual_signed_issuer_and_cp_context',positive_status==200 and positive.get('tenant_id')==a['tenant_id'] and positive.get('organisation_id')==a['organisation_id'] and positive.get('country_code')=='ZA')
    check('wrong_sibling_tenant_denied',context(bearer,sibling)[0]==403)
    check('wrong_external_tenant_denied',context(bearer,external)[0]==403)
    wrong=dict(credential['config']);wrong['audience']=['baobab-erp']
    require(api('PUT','/admin/clients/'+name,wrong)[0]==200)
    code,body,_=request('POST',ISSUER+'/oauth2/token',{'grant_type':'client_credentials','scope':'context:resolve','audience':'baobab-erp'},form=True,basic=(name,credential['secret']))
    require(code==200);wrong_token=body['access_token'];require(api('PUT','/admin/clients/'+name,credential['config'])[0]==200)
    wrong_claims=claims(wrong_token);audiences=wrong_claims.get('aud',[])
    if isinstance(audiences,str): audiences=[audiences]
    check('wrong_audience_denied',wrong_claims['sub']==claims(bearer)['sub'] and 'baobab-erp' in audiences and 'baobab-control-plane' not in audiences and context(wrong_token,a)[0]==401)
    code,resolved,_=context(bearer,a);require(code==200)
    status,decision,_=request('POST',CP+'/v1/capabilities/resolve',{'context_id':resolved['context_id'],'capability_key':'content.entry.resolve','required_contract_version':1,'correlation_id':str(uuid.uuid4())},bearer)
    check('absent_capability_grant_denied',status==200 and decision['decision']=='DENIED' and decision.get('reason_code') in ('CAPABILITY_UNKNOWN','GRANT_NOT_FOUND') and not decision.get('invocation') and not decision.get('grant_id'))
    short=dict(credential['config']);short['client_credentials_grant_access_token_lifespan']='2s';require(api('PUT','/admin/clients/'+name,short)[0]==200)
    expired=token(name,native);require(api('PUT','/admin/clients/'+name,credential['config'])[0]==200)
    wait=claims(expired)['exp']-time.time()+1;require(0<wait<10,'REAL_SHORT_LIVED_TOKEN_REQUIRED');time.sleep(wait)
    check('expired_issuer_token_denied',context(expired,a)[0]==401)
    bearer=token(name,native);require(context(bearer,a)[0]==200)
    require(request('POST',ISSUER+'/oauth2/revoke',{'token':bearer,'token_type_hint':'access_token'},form=True,basic=(name,credential['secret']))[0]==200)
    status,readback,_=request('POST',ISSUER+'/oauth2/introspect',{'token':bearer},form=True,basic=('baobab-dev-introspection',os.environ['DEV03_INTROSPECTION_SECRET']))
    revoked_status=context(bearer,a)[0]
    check('issuer_revocation_while_unexpired',status==200 and readback['active'] is False and claims(bearer)['exp']>time.time() and revoked_status==401)
    fresh=token(name,native);check('fresh_credential_after_revoke_succeeds',context(fresh,a)[0]==200)
    maker=native_human('maker',native);checker=native_human('checker',native)
    check('real_kratos_hydra_pkce_distinct_humans',claims(maker)['sub']!=claims(checker)['sub'] and claims(maker)['sub']==native['humans']['maker']['id'] and claims(checker)['sub']==native['humans']['checker']['id'])
    target='baobab-int03c-issuer-owner';target_id=bootstrap['proof_principals'][target];owner=token(target,native)
    nabhold=next(e for e in bootstrap['enterprises'] if e['key']=='nabhold');require(context(owner,nabhold)[0]==200)
    digest='sha256:'+hashlib.sha256((ROOT/'bootstrap.json').read_bytes()).hexdigest()
    payload={'principal_id':target_id,'issuer':ISSUER,'subject':target,'run_id':state['run_id'],'source_sha':state['sources']['baobab-cp'],'source_evidence_digest':digest}
    status,provenance,_=request('POST',CP+'/v1/admin/int03c/provenance',payload,maker);require(status==202,'CP_PROVENANCE_PROPOSE')
    approve=CP+'/v1/admin/int03c/provenance/'+provenance['provenance_id']+'/approve'
    check('same_principal_provenance_approval_denied',request('POST',approve,{'source_evidence_digest':digest},maker)[0]==409)
    require(request('POST',approve,{'source_evidence_digest':digest},checker)[0]==200,'CP_PROVENANCE_APPROVE')
    payload={k:payload[k] for k in ('issuer','subject','run_id','source_sha')};payload['idempotency_key']=str(uuid.uuid4())
    status,plan,_=request('POST',CP+'/v1/admin/int03c/principals/'+target_id+'/deactivation-requests',payload,maker);require(status==202,'CP_DEACTIVATION_PROPOSE')
    approve=CP+'/v1/admin/int03c/deactivation-requests/'+plan['request_id']+'/approve'
    check('same_principal_deactivation_approval_denied',request('POST',approve,{'plan_digest':plan['plan_digest']},maker)[0]==409)
    require(request('POST',approve,{'plan_digest':plan['plan_digest']},checker)[0]==200,'CP_DISTINCT_CHECKER')
    status,actual,_=request('GET',CP+'/v1/admin/int03c/principals/'+target_id,token=checker)
    disabled_status=context(owner,nabhold)[0]
    check('cp_principal_deactivation_while_unexpired',status==200 and actual['status']=='DISABLED' and claims(owner)['exp']>time.time() and disabled_status==403)
    # The issuer itself is still active; CP's own canonical disable caused denial.
    status,actual,_=request('POST',ISSUER+'/oauth2/introspect',{'token':owner},form=True,basic=('baobab-dev-introspection',os.environ['DEV03_INTROSPECTION_SECRET']))
    check('cp_denial_independent_of_issuer_status',status==200 and actual['active'] is True)
    check('wrong_pkce_denied_by_issuer',native_human('maker',native,'wrong_pkce'))
    check('wrong_state_denied_by_relying_party',native_human('checker',native,'wrong_state'))
    check('authorization_code_replay_denied',native_human('checker',native,'code_replay'))
    write('authority.json',{'schema':'infrastructure.dev03.authority-observed.v1','checks':observed,'synthetic_only':True,'canonical_provider_qualified':False,'int03c_qualified':False,'nab03_qualified':False,'protected_acceptance':False})
    print('REAL_NATIVE_ISSUER_CP_AUTHORITY_OBSERVED')

if __name__=='__main__':
    try:
        action=sys.argv[1]
        if action=='serve': ThreadingHTTPServer(('0.0.0.0',8090),Hook).serve_forever()
        elif action=='provider-ready': print(json.dumps(provider_ready()))
        elif action=='subjects': subjects()
        elif action=='health': health()
        elif action=='authority': authority()
        else: raise ValueError('UNKNOWN_PROBE')
    except Exception as error:
        # Closed local assertion names only; no provider strings or HTTP bodies.
        code=str(error) if isinstance(error,ValueError) and str(error).startswith(('DEV03_','REAL_','CP_','KRATOS_','HYDRA_','SIGNED_','PROVIDER_','FRESH_')) else 'NATIVE_PROTOCOL_FAILED'
        raise SystemExit('DEV03_PROVIDER_PROBE_FAILED '+code)
