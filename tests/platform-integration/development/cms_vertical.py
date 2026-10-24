"""DEV-05 addon to the existing private development lifecycle.

CMS and estate processes consume actual CP-issued references. No provider,
certification, ACTIVE binding or entitlement is synthesized by this adapter.
"""
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import sys

import adapter
import dev
import cms_contract

BASE=Path(__file__).resolve().parent
CONSUMER='baobab-int03-cms-consumer'
VALIDATOR='baobab-int03-cms-validator'
BFF='nabhold-dev-bff'
CMS='https://cms.baobab-dev.test'
ESTATE='https://nabhold.baobab-dev.test'


def lock():
    value=json.loads((BASE/'cms-lock.json').read_text(),object_pairs_hook=dev.unique)
    dev.require(set(value)=={'schema','sources','redis','node','frontend'} and value['schema']=='infrastructure.dev05.sources.v1'
        and set(value['sources'])=={'baobab-cms','nabhold'} and all(dev.SHA.fullmatch(v) for v in value['sources'].values())
        and all('@sha256:' in value[k] and dev.DIGEST.fullmatch(value[k]) for k in ('redis','node','frontend')),'DEV05_LOCK_INVALID')
    return value


def prepare():
    run=dev.prepare();directory,state=dev.current(run);value=lock()
    state['cms_lock_sha256']=hashlib.sha256((BASE/'cms-lock.json').read_bytes()).hexdigest()
    state['cms']=cms_contract.fresh(run)
    for key in ('cms_db','cms_payload','cms_consumer','cms_validator','bff','redis','session_key'):
        state['secrets'][key]=os.urandom(32).hex()
    dev.persist(directory,state,'PREPARED')
    sys.path.insert(0,str(BASE.parent/'int03'))
    import cms_gate
    verdict,_=cms_gate.judge((directory/'sources/shared/contracts/identity/v1/workload-registry.yaml').read_text())
    dev.require(verdict=='OPEN','DEV05_CANONICAL_REGISTRY_REFUSED')
    for repo,sha in value['sources'].items():
        target=directory/'sources'/repo
        dev.call(['git','init','-q',str(target)],state=state)
        dev.call(['git','-C',str(target),'fetch','--quiet','--depth','1','https://github.com/baobab-platform/'+repo+'.git',sha],state=state,timeout=180)
        dev.call(['git','-C',str(target),'checkout','--quiet','--detach','FETCH_HEAD'],state=state)
        state['sources'][repo]=sha
        dev.persist(directory,state,'PREPARED')
    return run


def up(run):
    dev.up(run);directory,state=dev.current(run);value=lock();secret=state['secrets']
    dev.require(state['cms_lock_sha256']==hashlib.sha256((BASE/'cms-lock.json').read_bytes()).hexdigest(),'DEV05_SOURCE_DRIFT')
    for name,target in [('cms-tool','build'),('cms','runtime')]:
        image=state['project']+'-'+name;state['images'][name]=image;dev.persist(directory,state,'RUNNING')
        args=['docker','build','--tag',image,'--target',target]
        for key,val in {**dev.labels(state),'org.opencontainers.image.revision':state['sources']['baobab-cms']}.items():args+=['--label',key+'='+val]
        dev.call([*args,str(directory/'sources/baobab-cms')],timeout=1800,state=state)
        state['image_ids'][name]=dev.call(['docker','image','inspect',image,'--format','{{.Id}}'])
        dev.persist(directory,state,'RUNNING')
    image=state['project']+'-nabhold';state['images']['nabhold']=image;dev.persist(directory,state,'RUNNING')
    package_token=os.environ.get('DEV05_NPM_TOKEN','');dev.require(bool(package_token),'DEV05_PACKAGE_READ_REQUIRED')
    tokenfile=directory/'package-token';tokenfile.write_text(package_token);tokenfile.chmod(0o600)
    try:
        args=['docker','build','--tag',image,'--file',str(BASE/'nabhold.Dockerfile'),
          '--build-context','nabhold_git='+str(directory/'sources/nabhold/.git'),
          '--build-arg','LAB_UID='+str(state['uid']),'--build-arg','LAB_GID='+str(state['gid']),
          '--secret','id=npm_token,src='+str(tokenfile)]
        for key,val in {**dev.labels(state),'org.opencontainers.image.revision':state['sources']['nabhold']}.items():args+=['--label',key+'='+val]
        dev.call([*args,str(directory/'sources/nabhold')],timeout=1800,state=state)
    finally:tokenfile.unlink(missing_ok=True)
    state['image_ids']['nabhold']=dev.call(['docker','image','inspect',image,'--format','{{.Id}}'])
    dev.persist(directory,state,'RUNNING')
    bootstrap=dev.read(directory/'bootstrap.json');own=next(e for e in bootstrap['enterprises'] if e['key']=='nabhold')
    refs={'tenant':own['tenant_id'],'organisation':own['organisation_id'],'legalEntity':own['legal_entity_id'],
          'digitalEstate':own['digital_estate_id'],'market':bootstrap['market_ids']['ZA']}
    declaration=json.dumps({'schema':'cms.int03.reference-declaration.v1','run_id':run[:16],'references':refs},separators=(',',':'))
    deadline=datetime.fromtimestamp(state['deadline']-10,timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    tls=adapter.host(directory/'tls');labels=dev.labels(state)
    composition=dev.read(directory/'compose.json');services=composition['services']
    services['cms-db']={'image':dev.load_lock()['images']['postgres'],'environment':{'POSTGRES_USER':'payload','POSTGRES_PASSWORD':secret['cms_db'],'POSTGRES_DB':'cms_int03_'+run[:16]},'volumes':['cms-data:/var/lib/postgresql/data'],'healthcheck':{'test':['CMD-SHELL','pg_isready -U payload -d cms_int03_'+run[:16]],'interval':'3s','timeout':'3s','retries':40}}
    env={'DATABASE_URL':'postgresql://payload:'+secret['cms_db']+'@cms-db:5432/cms_int03_'+run[:16],
      'PAYLOAD_SECRET':secret['cms_payload'],'BAOBAB_ENVIRONMENT':'ci','CI':'true','NODE_ENV':'production',
      'CMS_INT03_FIXTURE':'synthetic-disposable','CMS_INT03_RUN_ID':run[:16],'CMS_INT03_REFERENCE_DECLARATION':declaration,
      'CMS_TOKEN_ISSUER':adapter.ISSUER,'CMS_TOKEN_AUDIENCE':'baobab-cms','CMS_TOKEN_JWKS_URL':adapter.ISSUER+'/.well-known/jwks.json',
      'CONTROL_PLANE_URL':'https://cp.baobab-dev.test','CMS_CONTEXT_VALIDATOR_MODE':'development-proof',
      'CMS_WORKLOAD_ENVIRONMENT':'development','CMS_WORKLOAD_CLIENT_ID':VALIDATOR,'CMS_WORKLOAD_CLIENT_SECRET':secret['cms_validator'],
      'CMS_WORKLOAD_TOKEN_ENDPOINT':adapter.ISSUER+'/oauth2/token','CMS_WORKLOAD_INTROSPECTION_ENDPOINT':adapter.ISSUER+'/oauth2/introspect/dev05',
      'CMS_PROOF_DEADLINE':deadline,'NODE_EXTRA_CA_CERTS':'/tls/ca.pem','HOSTNAME':'0.0.0.0','NEXT_TELEMETRY_DISABLED':'1'}
    services['cms-tool']={'image':state['images']['cms-tool'],'environment':env,'volumes':[tls+':/tls:ro']}
    services['cms']={'image':state['images']['cms'],'environment':env,'volumes':[tls+':/tls:ro']}
    acl=directory/'redis.acl';acl.write_text('user default off\nuser nabhold on >'+secret['redis']+' ~nabhold:bff:v1:* +@connection +set +get +getdel +del\n');acl.chmod(0o644)
    services['redis']={'image':value['redis'],'command':['redis-server','--save','','--appendonly','no','--aclfile','/redis.acl','--port','0','--tls-port','6380','--tls-cert-file','/tls/edge.pem','--tls-key-file','/tls/edge.key','--tls-ca-cert-file','/tls/ca.pem','--tls-auth-clients','no'],'volumes':[adapter.host(acl)+':/redis.acl:ro',tls+':/tls:ro'],'networks':{'lab':{'aliases':['redis.baobab-dev.test']}}}
    services['nabhold']={'image':state['images']['nabhold'],'volumes':[tls+':/tls:ro'],'environment':{
      'NODE_EXTRA_CA_CERTS':'/tls/ca.pem','NABHOLD_OIDC_ENABLED':'true','NABHOLD_OIDC_ENVIRONMENT':'development',
      'NABHOLD_OIDC_ORIGIN':ESTATE,'NABHOLD_OIDC_ISSUER':adapter.ISSUER,'NABHOLD_OIDC_CLIENT_ID':BFF,
      'NABHOLD_OIDC_CLIENT_SECRET':secret['bff'],'NABHOLD_OIDC_INTROSPECTION_ENDPOINT':adapter.ISSUER+'/oauth2/introspect/dev05',
      'NABHOLD_OIDC_CP_ORIGIN':'https://cp.baobab-dev.test','NABHOLD_OIDC_TRUST_PROXY':'true',
      'NABHOLD_BFF_STORE_ENABLED':'true','NABHOLD_BFF_STORE_KEYS_JSON':json.dumps({'development':base64.b64encode(bytes.fromhex(secret['session_key'])).decode()}),
      'NABHOLD_BFF_STORE_ACTIVE_KEY':'development','NABHOLD_BFF_STORE_EPOCH':'dev'+run,'NABHOLD_BFF_REDIS_HOST':'redis.baobab-dev.test',
      'NABHOLD_BFF_REDIS_PORT':'6380','NABHOLD_BFF_REDIS_USERNAME':'nabhold','NABHOLD_BFF_REDIS_PASSWORD':secret['redis'],
      'NABHOLD_BFF_REDIS_CA_PEM':(directory/'tls/ca.pem').read_text(),
      'NABHOLD_CONTENT_SOURCE':'capability','NABHOLD_CONTENT_FALLBACK':'disabled','NABHOLD_CMS_PROOF_ENABLED':'true',
      'NABHOLD_WORKLOAD_ENVIRONMENT':'development','NABHOLD_WORKLOAD_CLIENT_ID':CONSUMER,
      'NABHOLD_WORKLOAD_ISSUER':adapter.ISSUER,'NABHOLD_WORKLOAD_TOKEN_ENDPOINT':adapter.ISSUER+'/oauth2/token',
      'NABHOLD_WORKLOAD_INTROSPECTION_ENDPOINT':adapter.ISSUER+'/oauth2/introspect/dev05','NABHOLD_WORKLOAD_CLIENT_SECRET':secret['cms_consumer'],
      'NABHOLD_CMS_PROOF_DEADLINE':deadline,'BAOBAB_CONTROL_PLANE_API_URL':'https://cp.baobab-dev.test',
      'NABHOLD_CONTENT_TENANT_ID':refs['tenant'],'NABHOLD_CONTENT_ORGANISATION_ID':refs['organisation'],
      'NABHOLD_CONTENT_COUNTRY_CODE':'ZA','NABHOLD_CONTENT_DIGITAL_ESTATE_ID':refs['digitalEstate'],
      'NABHOLD_CONTENT_MARKET_ID':refs['market'],'NABHOLD_SERVICE_ORIGINS':json.dumps({'baobab-cms':CMS}),
      'NEXT_PUBLIC_SITE_URL':ESTATE}}
    probe=services['probe'];probe['environment'].update(DEV05_PROFILE='native-cms')
    probe['volumes'] += [adapter.host(BASE/name)+':/'+name+':ro' for name in ('cms_probe.py','cms_contract.py')]
    composition['volumes']['cms-data']={'labels':labels}
    for item in services.values():item.update(labels=labels,restart='no');item.setdefault('networks',['lab'])
    services['edge']['networks']['lab']['aliases']+=['cms.baobab-dev.test','nabhold.baobab-dev.test']
    edge=adapter.EDGE.replace(' location = /oauth2/introspect {',' location = /oauth2/introspect/dev05 {\n limit_except POST { deny all; }\n set $reader http://probe:8090; proxy_pass $reader/introspect;\n }\n location = /oauth2/introspect {',1)
    extra=''
    for name,upstream in [('cms.baobab-dev.test','cms:3000'),('nabhold.baobab-dev.test','nabhold:3000')]:
        extra+='server { listen 443 ssl; server_name '+name+'; ssl_certificate /tls/edge.pem; ssl_certificate_key /tls/edge.key; location / { set $target http://'+upstream+'; proxy_pass $target; proxy_set_header Host '+name+'; proxy_set_header X-Forwarded-Host '+name+'; proxy_set_header X-Forwarded-Proto https; } }\n'
    edge=edge[:-2]+extra+'}\n'
    (directory/'nginx.conf').write_text(edge)
    dev.write(directory/'compose.json',composition);state['compose_sha256']=hashlib.sha256((directory/'compose.json').read_bytes()).hexdigest();dev.persist(directory,state,'RUNNING')
    dev.compose(directory,state,'up','-d','--wait','--wait-timeout','120','cms-db','redis','probe','edge',timeout=180)
    dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py','clients')
    dev.compose(directory,state,'exec','-T','cms-db','psql','-U','payload','-d','cms_int03_'+run[:16],'-v','ON_ERROR_STOP=1','-c','CREATE SCHEMA payload AUTHORIZATION payload;')
    dev.compose(directory,state,'run','--rm','--no-deps','cms-tool','npm','run','db:migrate',timeout=240)
    fixture(directory,state,'seed');fixture(directory,state,'publish')
    dev.compose(directory,state,'up','-d','cms','nabhold')
    for _ in range(90):
        try:
            dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py','health',timeout=15);break
        except dev.Refused:time.sleep(2)
    else:raise dev.Refused('DEV05_SERVICES_UNAVAILABLE')
    state['tests']=True;dev.persist(directory,state,'TESTED')


def fixture(directory,state,action):
    raw=dev.compose(directory,state,'run','--rm','--no-deps','cms-tool','node','--import','tsx','scripts/qualification/int03-fixture.ts',action,timeout=120)
    # Payload may emit operational startup logs; the final JSON document is the
    # closed fixture result, which is validated and never echoed with raw logs.
    result=json.loads(raw.splitlines()[-1]);dev.require(result.get('converged') is True and result.get('cp_issuance_proven') is False,'DEV05_FIXTURE_FAILED')
    return result


def qualify(run):
    directory,state=dev.current(run);dev.verify_sources(directory,state)
    state['cms']=cms_contract.fresh(run);dev.persist(directory,state,'TESTED')
    try:
        for action in ('initial','draft','withdraw','outage','finish'):
            if action=='draft':fixture(directory,state,'draft')
            if action=='withdraw':fixture(directory,state,'withdraw')
            if action=='outage':
                fixture(directory,state,'publish');dev.compose(directory,state,'stop','cp')
            dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py',action,timeout=180)
            if action=='outage':
                dev.compose(directory,state,'up','-d','cp');time.sleep(3)
                dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py','restored',timeout=30)
    finally:
        if (directory/'cms-report.json').exists():
            report=dev.read(directory/'cms-report.json');cms_contract.validate(report,run);state['cms']=report;dev.persist(directory,state,'TESTED')
    return state['cms']
