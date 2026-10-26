"""Engine-side protocol driver; mounted read-only into an unprivileged container.

Receives only this engine's native stores, registered caller/validator clients,
public IAM/CP endpoints and opaque owner-issued context references. No issuer
admin API, CP DSN, Docker socket or operator directory is reachable here.
"""
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args):return None

class Driver:
    def __init__(self):
        self.context=json.loads(Path('/run/engine/context.json').read_text())
        tls=ssl.create_default_context(cafile='/tls/ca.pem');tls.minimum_version=ssl.TLSVersion.TLSv1_3
        self.client=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=tls))
    def request(self,method,url,body=None,token=None,headers=None,form=False):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in {'engine.baobab-dev.test','cp.baobab-dev.test','hydra.int03.test'} or parsed.username or parsed.fragment:
            raise ValueError('ENGINE_ENDPOINT_REFUSED')
        data=(urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()) if body is not None else None
        h={'Accept':'application/json','X-Correlation-Id':str(uuid.uuid4()),**(headers or {})}
        if data is not None:h['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
        if token:h['Authorization']='Bearer '+token
        try:response=self.client.open(urllib.request.Request(url,data,h,method=method),timeout=8)
        except urllib.error.HTTPError as e:response=e
        self.last_headers={k.lower():v for k,v in response.headers.items()}
        raw=response.read(65537)
        if len(raw)>65536:raise ValueError('ENGINE_RESPONSE_OVERSIZED')
        return response.status,json.loads(raw) if raw and 'json' in response.headers.get('Content-Type','') else None
    def token(self,role='caller',audiences=None,scopes=None):
        identity=self.context['iam'][role]
        fields=[('grant_type','client_credentials'),('client_id',identity['client_id']),('client_secret',identity['client_secret']),('scope',' '.join(scopes if scopes is not None else identity['scopes']))]
        fields += [('audience',aud) for aud in (audiences if audiences is not None else identity['audiences'])]
        code,body=self.request('POST','https://hydra.int03.test/oauth2/token',fields,form=True)
        if code!=200 or not isinstance(body.get('access_token'),str):raise ValueError('ENGINE_ISSUANCE_REFUSED')
        return body['access_token']
    def resolve(self,role='caller',token=None,tenant=None):
        selected=self.context['neighbour' if role=='neighbour' else 'tenant']
        body={'tenant_id':tenant or selected['id'],'organisation_id':selected['organisation_id'],'country_code':selected['country']}
        return self.request('POST','https://cp.baobab-dev.test/v1/platform-context/resolve',body,token or self.token(role))
    def native(self,path,body,token,context_id,key=None,method='POST'):
        headers={'X-Baobab-Context-Id':context_id}
        if key:headers['Idempotency-Key']=key
        return self.request(method,'https://engine.baobab-dev.test'+path,body,token,headers)


def isolation():
    import socket
    driver=Driver()
    for hostname,port in (('hydra',4445),('kratos',4434),('cp-db',5432),('probe',8090)):
        try:
            with socket.create_connection((hostname,port),timeout=1):
                raise ValueError('PRIVATE_ADMIN_PLANE_REACHABLE')
        except OSError:
            pass  # Denial is required; a successful connection refuses the run.
    code,metadata=driver.request('GET','https://hydra.int03.test/.well-known/openid-configuration')
    if code!=200 or metadata.get('issuer')!='https://hydra.int03.test':raise ValueError('PUBLIC_ISSUER_UNAVAILABLE')
    # Test the public bridge too: issuer admin routes are never proxied.
    code,_=driver.request('GET','https://hydra.int03.test/admin/clients')
    if code!=404:raise ValueError('ISSUER_ADMIN_PROXY_EXPOSED')
    print(json.dumps({'private_planes_unreachable':True}))

if __name__=='__main__':
    import sys
    try:
        if sys.argv[1]!='isolation':raise ValueError('UNKNOWN_ENGINE_TOOL_PHASE')
        isolation()
    except Exception:raise SystemExit('ENGINE_ISOLATION_REFUSED') from None
