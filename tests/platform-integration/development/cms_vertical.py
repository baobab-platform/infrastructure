"""DEV-05 addon to the existing private development lifecycle.

CMS and estate processes consume actual CP-issued references. No provider,
certification, ACTIVE binding or entitlement is synthesized by this adapter.
"""
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
import time
import sys

import adapter
import dev
import cms_contract
import external_oci

BASE=Path(__file__).resolve().parent
CONSUMER='baobab-int03-cms-consumer'
VALIDATOR='baobab-int03-cms-validator'
BFF='nabhold-dev-bff'
CMS='https://cms.baobab-dev.test'
ESTATE='https://nabhold.baobab-dev.test'


@contextmanager
def package_access(directory,state):
    """One build's GHCR/npm access; never alter the operator's Docker login."""
    token=os.environ.get('DEV05_NPM_TOKEN','')
    username=os.environ.get('DEV05_REGISTRY_USERNAME','')
    dev.require(bool(token) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}',username),
        'DEV05_PACKAGE_READ_REQUIRED')
    config=directory/'build-docker-config';tokenfile=directory/'package-token'
    config.mkdir(mode=0o700)
    try:
        tokenfile.write_text(token);tokenfile.chmod(0o600)
        # Both login and BuildKit must use the same isolated credential store.
        # The npm credential reaches BuildKit only through its secret mount.
        build_env={key:value for key,value in os.environ.items() if key!='DEV05_NPM_TOKEN'}
        build_env['DOCKER_CONFIG']=str(config)
        dev.call(['docker','login','ghcr.io','--username',username,'--password-stdin'],
            stdin=token,env=build_env,state=state,timeout=60)
        yield build_env,tokenfile
    finally:
        tokenfile.unlink(missing_ok=True)
        shutil.rmtree(config)


def bff_epoch(run):
    """Lossless full 128-bit run identity in Nabhold's bounded Redis namespace.

    Nabhold confidential custody accepts an epoch matching
    ^[a-z][a-z0-9-]{0,31}$. Base32 keeps all bits without truncation.
    """
    dev.require(type(run) is str and re.fullmatch(r'[0-9a-f]{32}',run), 'DEV05_RUN_ID_INVALID')
    epoch='dev'+base64.b32encode(bytes.fromhex(run)).decode('ascii').rstrip('=').lower()
    dev.require(bool(re.fullmatch(r'[a-z][a-z0-9-]{0,31}',epoch)), 'DEV05_BFF_EPOCH_INVALID')
    return epoch


def lock():
    value=json.loads((BASE/'cms-lock.json').read_text(),object_pairs_hook=dev.unique)
    dev.require(set(value)=={'schema','sources','redis','node','frontend'} and value['schema']=='infrastructure.dev05.sources.v1'
        and set(value['sources'])=={'baobab-cms','nabhold'} and all(dev.SHA.fullmatch(v) for v in value['sources'].values())
        and all('@sha256:' in value[k] and dev.DIGEST.fullmatch(value[k]) for k in ('redis','node','frontend')),'DEV05_LOCK_INVALID')
    return value


def prepare():
    print('DEV05_PHASE=PREPARE',flush=True)
    run=dev.prepare(lock_name='cms-base-lock.json');directory,state=dev.current(run);value=lock()
    state['runtime_images'].update({key:value[key] for key in ('redis','node','frontend')})
    state['cms_lock_sha256']=hashlib.sha256((BASE/'cms-lock.json').read_bytes()).hexdigest()
    state['cms']=cms_contract.fresh(run)
    for key in ('cms_db','cms_payload','cms_consumer','cms_validator','bff','redis','session_key'):
        state['secrets'][key]=os.urandom(32).hex()
    dev.persist(directory,state,'PREPARED')
    sys.path.insert(0,str(BASE.parent/'int03'))
    import cms_gate
    print('DEV05_PHASE=REGISTRY',flush=True)
    verdict,_=cms_gate.judge((directory/'sources/shared/contracts/identity/v1/workload-registry.yaml').read_text())
    dev.require(verdict=='OPEN','DEV05_CANONICAL_REGISTRY_REFUSED')
    print('DEV05_PHASE=OWNER_SOURCES',flush=True)
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
    print('DEV05_PHASE=CMS_IMAGES',flush=True)
    for name,target in [('cms-tool','build'),('cms','runtime')]:
        image=state['project']+'-'+name;state['images'][name]=image;dev.persist(directory,state,'RUNNING')
        args=['docker','build','--tag',image,'--target',target]
        for key,val in {**dev.labels(state),'org.opencontainers.image.revision':state['sources']['baobab-cms']}.items():args+=['--label',key+'='+val]
        dev.call([*args,str(directory/'sources/baobab-cms')],timeout=1800,state=state)
        state['image_ids'][name]=dev.call(['docker','image','inspect',image,'--format','{{.Id}}'])
        dev.persist(directory,state,'RUNNING')
    # Publish actual saved runtime config/layers using the DEV-06 OCI proof.
    # A tag or image/config ID is not an OCI manifest digest.
    archive=directory/'cms-image.tar'
    dev.call(['docker','image','save','--output',str(archive),state['images']['cms']],timeout=180,state=state)
    manifest=external_oci.publish(archive,directory/'cms-oci',state['image_ids']['cms']);archive.unlink()
    dev.write(directory/'cms-source.json',{'source_sha':state['sources']['baobab-cms'],'manifest_digest':manifest,
        'declaration_digest':'sha256:'+hashlib.sha256((directory/'sources/baobab-cms/.baobab/capability-provider.yaml').read_bytes()).hexdigest()})
    state['cms_oci_manifest_digest']=manifest;dev.persist(directory,state,'RUNNING')
    authority=owner_fixture(directory,state,'register')
    print('DEV05_PHASE=ESTATE_IMAGE',flush=True)
    image=state['project']+'-nabhold';state['images']['nabhold']=image;dev.persist(directory,state,'RUNNING')
    with package_access(directory,state) as (build_env,tokenfile):
        args=['docker','build','--tag',image,'--file',str(BASE/'nabhold.Dockerfile'),
          '--build-context','nabhold_git='+str(directory/'sources/nabhold/.git'),
          '--build-arg','LAB_UID='+str(state['uid']),'--build-arg','LAB_GID='+str(state['gid']),
          '--secret','id=npm_token,src='+str(tokenfile)]
        for key,val in {**dev.labels(state),'org.opencontainers.image.revision':state['sources']['nabhold']}.items():args+=['--label',key+'='+val]
        dev.call([*args,str(directory/'sources/nabhold')],timeout=1800,state=state,env=build_env)
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
      'CMS_CAPABILITY_PROVIDER_ID':'provider_'+authority['provider_id'].replace('-',''),
      'CMS_ENGINE_INSTANCE_ID':'ei_'+authority['engine_instance_id'].replace('-',''),
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
      'NABHOLD_BFF_STORE_ACTIVE_KEY':'development','NABHOLD_BFF_STORE_EPOCH':bff_epoch(run),'NABHOLD_BFF_REDIS_HOST':'redis.baobab-dev.test',
      'NABHOLD_BFF_REDIS_PORT':'6380','NABHOLD_BFF_REDIS_USERNAME':'nabhold','NABHOLD_BFF_REDIS_PASSWORD':secret['redis'],
      'NABHOLD_BFF_REDIS_CA_PEM':(directory/'tls/ca.pem').read_text(),
      'NABHOLD_CONTENT_SOURCE':'capability','NABHOLD_CONTENT_FALLBACK':'disabled','NABHOLD_CMS_PROOF_ENABLED':'true',
      'NABHOLD_WORKLOAD_ENVIRONMENT':'development','NABHOLD_WORKLOAD_CLIENT_ID':CONSUMER,
      'NABHOLD_WORKLOAD_ISSUER':adapter.ISSUER,'NABHOLD_WORKLOAD_TOKEN_ENDPOINT':adapter.ISSUER+'/oauth2/token',
      'NABHOLD_WORKLOAD_INTROSPECTION_ENDPOINT':adapter.ISSUER+'/oauth2/introspect/dev05','NABHOLD_WORKLOAD_CLIENT_SECRET':secret['cms_consumer'],
      'NABHOLD_CMS_PROOF_DEADLINE':deadline,'BAOBAB_CONTROL_PLANE_API_URL':'https://cp.baobab-dev.test',
      'NABHOLD_CONTENT_TENANT_ID':refs['tenant'],'NABHOLD_CONTENT_ORGANISATION_ID':refs['organisation'],
      'NABHOLD_CONTENT_LEGAL_ENTITY_ID':refs['legalEntity'],
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
    state['cms_config_hashes']={name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in ('nginx.conf','redis.acl')}
    dev.write(directory/'compose.json',composition);state['compose_sha256']=hashlib.sha256((directory/'compose.json').read_bytes()).hexdigest();dev.persist(directory,state,'RUNNING')
    print('DEV05_PHASE=PROVIDER_START',flush=True)
    dev.compose(directory,state,'up','-d','--wait','--wait-timeout','120','cms-db','redis','probe','edge',timeout=180)
    print('DEV05_PHASE=ISSUER_CLIENTS',flush=True)
    dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py','clients')
    print('DEV05_PHASE=CMS_SCHEMA',flush=True)
    dev.compose(directory,state,'exec','-T','cms-db','psql','-U','payload','-d','cms_int03_'+run[:16],'-v','ON_ERROR_STOP=1','-c','CREATE SCHEMA payload AUTHORIZATION payload;')
    print('DEV05_PHASE=CMS_MIGRATIONS',flush=True)
    dev.compose(directory,state,'run','--rm','--no-deps','cms-tool','npm','run','db:migrate',timeout=240)
    print('DEV05_PHASE=CMS_FIXTURE',flush=True)
    fixture(directory,state,'seed');fixture(directory,state,'publish')
    dev.compose(directory,state,'up','-d','cms','nabhold')
    print('DEV05_PHASE=HTTP_HEALTH',flush=True)
    for attempt in range(90):
        try:
            health=json.loads(dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py','health',timeout=25))
            dev.require(set(health)=={'cms','estate'} and all(type(v) is int and 0<=v<600 for v in health.values()),'DEV05_HEALTH_SHAPE')
            if health=={'cms':200,'estate':401}:break
            if attempt%15==0:print('DEV05_HEALTH='+json.dumps(health,sort_keys=True),flush=True)
        except dev.Refused:
            # Refused/malformed startup probes cannot advance readiness.
            pass
        time.sleep(2)
    else:raise dev.Refused('DEV05_SERVICES_UNAVAILABLE')
    owner_fixture(directory,state,'activate')
    dev.test(run)
    directory,state=dev.current(run)
    verify_runtime(directory,state)
    state['cms_runtime_identity_verified']=True;dev.persist(directory,state,'TESTED')



def verify_runtime(directory,state):
    """Read actual extra-container images and network/host exposure, not Compose intent."""
    for name in ('cms','nabhold','cms-db','redis'):
        container=dev.compose(directory,state,'ps','-q',name)
        dev.require(bool(container),'DEV05_CONTAINER_NOT_RUNNING')
        actual=json.loads(dev.call(['docker','inspect',container]))[0]
        image=state['image_ids'].get(name)
        if image is None:
            reference=state['runtime_images']['postgres' if name=='cms-db' else name]
            image=dev.call(['docker','image','inspect',reference,'--format','{{.Id}}'])
        dev.require(actual['Image']==image and not actual['HostConfig']['PortBindings'] and not actual['HostConfig']['Privileged']
            and actual['Config']['Labels'].get('io.baobab.dev.run')==state['run_id'],'DEV05_RUNTIME_IDENTITY_INVALID')
        networks=actual['NetworkSettings']['Networks'];dev.require(len(networks)==1,'DEV05_NETWORK_INVALID')
        network=json.loads(dev.call(['docker','network','inspect',next(iter(networks))]))[0]
        dev.require(network['Internal'] is True,'DEV05_PUBLIC_NETWORK_FORBIDDEN')
    dev.require(all(hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest for name,digest in state['cms_config_hashes'].items()),'DEV05_CONFIG_DRIFT')


def fixture(directory,state,action):
    raw=dev.compose(directory,state,'run','--rm','--no-deps','cms-tool','node','--import','tsx','scripts/qualification/int03-fixture.ts',action,timeout=120)
    # Payload may emit operational startup logs; the final JSON document is the
    # closed fixture result, which is validated and never echoed with raw logs.
    result=json.loads(raw.splitlines()[-1]);dev.require(result.get('converged') is True and result.get('cp_issuance_proven') is False,'DEV05_FIXTURE_FAILED')
    return result


def qualify(run):
    directory,state=dev.current(run);dev.verify_sources(directory,state)
    dev.require(state['cms_lock_sha256']==hashlib.sha256((BASE/'cms-lock.json').read_bytes()).hexdigest(),'DEV05_SOURCE_DRIFT')
    verify_runtime(directory,state)
    state['cms']=cms_contract.fresh(run)
    state['cms']['component_checks'].update(normal_provider_activation=True,actual_oci_publication=True)
    dev.persist(directory,state,'TESTED')
    owner_fixture(directory,state,'read')
    # Retry cannot reuse a former green probe report.
    dev.write(directory/'cms-report.json',state['cms'])
    try:
        # Execute the *maintained* CMS token provider in the same isolated
        # toolchain/environment/network before delivery probes. A fixed result
        # is diagnostic only, not authority evidence or a passed NAB-03 case.
        code=("import {createDevelopmentValidatorTokens} from './src/baobab/identity/development-validator.ts';"
              "try { const token=await createDevelopmentValidatorTokens().getToken();"
              "process.stdout.write(token?'DEV05_CMS_VALIDATOR=READY':'DEV05_CMS_VALIDATOR=UNAVAILABLE');"
              "} catch {process.stdout.write('DEV05_CMS_VALIDATOR=UNAVAILABLE');}")
        try:
            observed=dev.compose(directory,state,'run','--rm','--no-deps','cms-tool',
                'node','--import','tsx','--input-type=module','-e',code,timeout=35)
        except dev.Refused:
            observed='DEV05_CMS_VALIDATOR=UNAVAILABLE'
        print(observed if observed in {'DEV05_CMS_VALIDATOR=READY','DEV05_CMS_VALIDATOR=UNAVAILABLE'}
              else 'DEV05_CMS_VALIDATOR=UNAVAILABLE',flush=True)
        for action in ('initial','draft','withdraw','outage','finish'):
            if action=='draft':
                verify_audit(directory,state)
                before=read_audit(directory,state)['count']
                owner_fixture(directory,state,'unentitled')
                dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py','unentitled',timeout=90)
                dev.require(read_audit(directory,state)['count']==before,'DEV05_DENIED_RESOURCE_EFFECT')
                report=dev.read(directory/'cms-report.json');report['component_checks']['denied_resource_no_read_effect']=True;dev.write(directory/'cms-report.json',report)
                owner_fixture(directory,state,'regrant')
                dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py','rebound',timeout=90)
                verify_audit(directory,state)
            if action=='draft':fixture(directory,state,'draft')
            if action=='withdraw':fixture(directory,state,'withdraw')
            if action=='outage':
                fixture(directory,state,'publish');dev.compose(directory,state,'stop','cp')
            dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py',action,timeout=180)
            if action=='outage':
                dev.compose(directory,state,'up','-d','cp');time.sleep(3)
                dev.compose(directory,state,'exec','-T','probe','python','/cms_probe.py','restored',timeout=30)
    except Exception:
        estate_diagnostics(directory,state)
        raise
    finally:
        if (directory/'cms-report.json').exists():
            report=dev.read(directory/'cms-report.json');cms_contract.validate(report,run);state['cms']=report;dev.persist(directory,state,'TESTED')
    return state['cms']


def owner_fixture(directory,state,phase):
    subjects=dev.read(directory/'subjects.json')
    print('DEV05_PHASE=OWNER_'+phase.upper(),flush=True)
    raw=dev.compose(directory,state,'run','--rm','--no-deps','--user',str(state['uid'])+':'+str(state['gid']),
        '--volume',adapter.host(directory/'cms-source.json')+':/cms-source.json:ro','-e','BAOBAB_DEV_BOOTSTRAP_ENABLED=true',
        '--entrypoint','/development-bootstrap','cp','--run-id',state['run_id'],'--issuer',adapter.ISSUER,
        '--maker-subject',subjects['maker'],'--checker-subject',subjects['checker'],'--lease',str(state['bootstrap_lease'])+'s',
        '--cms-capability-phase',phase,'--cms-capability-source','/cms-source.json',timeout=120)
    actual=json.loads(raw.splitlines()[-1]);dev.require(actual['run_id']==state['run_id'],'DEV05_OWNER_FIXTURE_IDENTITY')
    if phase in ('activate','regrant','restore','read'):
        dev.require(all(actual[k] for k in ('source_present','source_active','grant_active','binding_active','projection_current','provider_active')),'DEV05_NORMAL_AUTHORITY_REQUIRED')
    dev.write(directory/'cms-capability.json',actual)
    return actual


def literal(value):
    return "'"+value.replace("'","''")+"'"


def read_audit(directory,state):
    owner=dev.read(directory/'cms-capability.json')
    where="tenant="+literal(owner['tenant_id'])+" AND action='content.entry.resolve' AND outcome='ALLOWED'"
    # Metadata reads may finish last. Verify a core NAB-03 content audit while
    # counting every allowed read for the denial/no-effect comparison.
    sql="SELECT json_build_object('count',(SELECT count(*) FROM payload.audit_logs WHERE "+where+"),'latest',(SELECT row_to_json(a) FROM (SELECT actor_id,correlation_id,resource_id,resulting_state FROM payload.audit_logs WHERE "+where+" AND resulting_state->>'content_key' IN ('home','navigation','footer') ORDER BY created_at DESC,id DESC LIMIT 1) a))"
    raw=dev.compose(directory,state,'exec','-T','cms-db','psql','-U','payload','-d','cms_int03_'+state['run_id'][:16],'-tAc',sql)
    return json.loads(raw)


def verify_audit(directory,state):
    owner=dev.read(directory/'cms-capability.json');actual=read_audit(directory,state);last=actual['latest']
    dev.require(actual['count']>0 and isinstance(last,dict) and last['actor_id']==CONSUMER,'DEV05_NATIVE_READ_AUDIT_REQUIRED')
    proof=last['resulting_state']
    expected={'grant_id':'grant_'+owner['grant_id'].replace('-',''),'binding_id':'bind_'+owner['binding_id'].replace('-',''),
        'provider_id':'provider_'+owner['provider_id'].replace('-',''),'engine_instance_id':'ei_'+owner['engine_instance_id'].replace('-','')}
    dev.require(all(proof.get(k)==v for k,v in expected.items()) and proof.get('content_key') in {'home','navigation','footer'}
        and proof.get('record_id')==last['resource_id'] and isinstance(proof.get('resolution_id'),str)
        and re.fullmatch(r'res_[0-9a-f]{32}',proof['resolution_id']),'DEV05_NATIVE_READ_AUDIT_IDENTITY')
    clauses=["decision='RESOLVED'","capability_key='content.entry.resolve'","resolution_id="+literal(proof['resolution_id']),
        "tenant_id="+literal(owner['tenant_id']),"context_id="+literal(proof['context_id']),"correlation_id::text="+literal(last['correlation_id'])]
    clauses += [key+'::text='+literal(owner[key]) for key in ('grant_id','binding_id','provider_id','engine_instance_id')]
    sql='SELECT EXISTS(SELECT 1 FROM capability.capability_resolution WHERE '+' AND '.join(clauses)+')'
    found=dev.compose(directory,state,'exec','-T','cp-db','psql','-U','baobab_dev','-d','baobab_dev_'+state['run_id'],'-tAc',sql)
    dev.require(found=='t','DEV05_INDEPENDENT_CP_AUDIT_REQUIRED')
    report=dev.read(directory/'cms-report.json');report['component_checks'].update(native_read_audit_persisted=True,independent_cp_resolution_readback=True)
    dev.write(directory/'cms-report.json',report)



def estate_diagnostics(directory,state):
    """Classify captured private logs; never publish lines or error bodies."""
    try:
        raw=dev.compose(directory,state,'logs','--no-color','--tail','200','nabhold',timeout=15)
    except Exception:
        print('DEV05_ESTATE_DIAGNOSTIC=UNAVAILABLE',flush=True);return
    keys={'home','navigation','footer','site-settings','group-profile'}
    outcomes={'none','unavailable:PROVIDER_SCOPE_REJECTED','unavailable:PROVIDER_RECORD_REJECTED',
        'unavailable:RECORD_DATA_INVALID','unavailable:CONTENT_TOKEN_UNAVAILABLE',
        'unavailable:CAPABILITY_NOT_RESOLVED','unavailable:CAPABILITY_UNAVAILABLE',
        'unavailable:CONTEXT_UNAVAILABLE','unavailable:PROVIDER_UNREACHABLE',
        'unavailable:PROVIDER_RESPONSE_INVALID','unavailable:PROVIDER_RESPONSE_NOT_JSON',
        'unavailable:PROOF_WINDOW_CLOSED'} | {'unavailable:PROVIDER_HTTP_'+str(c) for c in (400,401,403,404,500,502,503,504)}
    seen=set()
    diagnostic_markers={
        'NABHOLD_DEV05_WORKLOAD='+audience+'_'+phase for audience in ('CP','CMS')
        for phase in ('TOKEN_REQUEST','TOKEN_RESPONSE','INTROSPECTION_CLAIMS','AUDIENCES','EXPIRY_SUBJECT')
    } | {'NABHOLD_DEV05_CONTEXT='+phase for phase in ('TOKEN','RESPONSE_SHAPE','FRESHNESS')} | {
        'NABHOLD_DEV05_CAPABILITY='+phase for phase in ('TRANSPORT','BODY','CONTRACT','REQUEST_BINDING','EXPIRY','VERSION',
            'PROTOCOL','SERVICE_MAPPING','ORIGIN','SERVICE_REFERENCE','ROUTE','AUTH_OR_UNAVAILABLE',
            'DECISION_DENIED','DECISION_UNAVAILABLE','DECISION_AMBIGUOUS','DECISION_INCOMPATIBLE')}
    for line in raw.splitlines():
        for marker in diagnostic_markers:
            if re.search(r'(?<![A-Z0-9_=])'+re.escape(marker)+r'(?![A-Z0-9_=])',line):seen.add(marker)

        start=line.find('{"event":"content.capability"')
        if start>=0:
            try:value=json.loads(line[start:])
            except (ValueError,TypeError):continue
            if value.get('key') in keys and value.get('outcome') in outcomes:
                seen.add(value['key'].upper().replace('-','_')+'_'+value['outcome'].upper().replace(':','_'))
    for fixed,label in [('Required published content incomplete','INCOMPLETE_CONTENT'),
        ('Required published content unavailable','UNAVAILABLE_CONTENT'),
        ('Failed to download `Inter`','FONT_FETCH_FAILED'),
        ('Module not found','MODULE_UNAVAILABLE')]:
        if fixed in raw:seen.add(label)
    for label in sorted(seen or {'UNCLASSIFIED'}):print('DEV05_ESTATE_DIAGNOSTIC='+label,flush=True)
