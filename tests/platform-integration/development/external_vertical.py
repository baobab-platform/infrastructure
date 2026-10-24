"""Minimal native external-client addon: IAM/CP + Pulse/PG17/Qdrant, no estate."""
import hashlib
import json
from pathlib import Path
import time
import adapter
import dev
import external_contract as contract

BASE=Path(__file__).resolve().parent
CLIENT='baobab-dev-external-api'
VALIDATOR='baobab-dev-pulse-validator'

def lock():
    value=json.loads((BASE/'external-lock.json').read_text(),object_pairs_hook=dev.unique)
    dev.require(set(value)=={'schema','source','qdrant'} and value['schema']=='infrastructure.dev06.sources.v1' and
        set(value['source'])=={'baobab-pulse'} and dev.SHA.fullmatch(value['source']['baobab-pulse']) and
        dev.DIGEST.fullmatch(value['qdrant']) and '@sha256:' in value['qdrant'],'DEV06_LOCK_INVALID')
    dev.check_dockerfile(BASE.parent/'int02/pulse.Dockerfile')
    return value

def prepare():
    value=lock();run=dev.prepare()
    try:
        directory,state=dev.current(run)
        state['external_api']=True;state['external']=contract.fresh(run)
        state['external_lock_sha256']=hashlib.sha256((BASE/'external-lock.json').read_bytes()).hexdigest()
        for key in ('external_caller','external_validator','pulse_db'):state['secrets'][key]=__import__('os').urandom(32).hex()
        state['runtime_images']['qdrant']=value['qdrant'];dev.persist(directory,state,'PREPARED')
        target=directory/'sources/baobab-pulse';sha=value['source']['baobab-pulse']
        dev.call(['git','init','-q',str(target)],state=state)
        dev.call(['git','-C',str(target),'fetch','--quiet','--depth','1','https://github.com/baobab-platform/baobab-pulse.git',sha],timeout=180,state=state)
        dev.call(['git','-C',str(target),'checkout','--quiet','--detach','FETCH_HEAD'],state=state)
        state['sources']['baobab-pulse']=sha;dev.persist(directory,state,'PREPARED')
        return run
    except BaseException:
        dev.down(run)
        raise

def check_facts(directory,state):
    subjects=dev.read(directory/'subjects.json')
    raw=dev.compose(directory,state,'run','--rm','--no-deps','-e','BAOBAB_DEV_BOOTSTRAP_ENABLED=true',
       '--entrypoint','/development-bootstrap','cp','--external-api','--check-external-api',
       '--run-id',state['run_id'],'--issuer',adapter.ISSUER,'--maker-subject',subjects['maker'],
       '--checker-subject',subjects['checker'],'--lease',str(state['bootstrap_lease'])+'s')
    facts=json.loads(raw)
    dev.require(set(facts)=={'schema','run_id','zero_estates','independent_tenant','own_assignment','validator_unassigned','synthetic_only','protected_acceptance'} and
        facts['schema']=='baobab.development-external-api.v1' and facts['run_id']==state['run_id'] and facts['protected_acceptance'] is False and
        all(facts[k] is True for k in ('zero_estates','independent_tenant','own_assignment','validator_unassigned','synthetic_only')),'DEV06_CP_FACTS_INVALID')
    return facts

def verify_runtime(directory,state):
    dev.verify_sources(directory,state)
    dev.require(hashlib.sha256((BASE/'external-lock.json').read_bytes()).hexdigest()==state['external_lock_sha256'],'DEV06_SOURCE_DRIFT')
    for name in ('pulse','pulse-db','pulse-qdrant'):
        container=dev.compose(directory,state,'ps','-q',name);dev.require(bool(container),'DEV06_NOT_RUNNING')
        actual=json.loads(dev.call(['docker','inspect',container]))[0]
        expected=state['image_ids'].get(name) or dev.call(['docker','image','inspect',state['runtime_images']['postgres' if name=='pulse-db' else 'qdrant'],'--format','{{.Id}}'])
        dev.require(actual['Image']==expected and not actual['HostConfig']['PortBindings'] and not actual['HostConfig']['Privileged'] and
            actual['Config']['Labels'].get('io.baobab.dev.run')==state['run_id'],'DEV06_RUNTIME_IDENTITY_INVALID')
        networks=actual['NetworkSettings']['Networks'];dev.require(len(networks)==1,'DEV06_NETWORK_INVALID')
        dev.require(json.loads(dev.call(['docker','network','inspect',next(iter(networks))]))[0]['Internal'] is True,'DEV06_PUBLIC_NETWORK_FORBIDDEN')

def up(run):
    dev.up(run);directory,state=dev.current(run);value=lock();secret=state['secrets'];labels=dev.labels(state)
    check_facts(directory,state)
    print('DEV06_PHASE=PULSE_BUILD',flush=True)
    image=state['project']+'-pulse';state['images']['pulse']=image;dev.persist(directory,state,'RUNNING')
    args=['docker','build','--tag',image,'--file',str(BASE.parent/'int02/pulse.Dockerfile')]
    for key,val in {**labels,'org.opencontainers.image.revision':state['sources']['baobab-pulse']}.items():args+=['--label',key+'='+val]
    dev.call([*args,str(directory/'sources/baobab-pulse')],timeout=1800,state=state)
    state['image_ids']['pulse']=dev.call(['docker','image','inspect',image,'--format','{{.Id}}']);dev.persist(directory,state,'RUNNING')
    own=next(e for e in dev.read(directory/'bootstrap.json')['enterprises'] if e['key']=='external-client')
    other=next(e for e in dev.read(directory/'bootstrap.json')['enterprises'] if e['key']=='nabhold')
    fixtures=directory/'pulse-fixtures';fixtures.mkdir(mode=0o700)
    dev.write(fixtures/'fixtures.json',{'tenant':own['tenant_id'],'other_tenant':other['tenant_id']})
    tls=adapter.host(directory/'tls')
    env={'PULSE_ENVIRONMENT':'development','PULSE_DATABASE_URL':'postgresql://pulse:'+secret['pulse_db']+'@pulse-db:5432/pulse',
      'PULSE_QDRANT_URL':'http://pulse-qdrant:6333','PULSE_QDRANT_COLLECTION_PREFIX':'dev06','PULSE_EMBEDDING_PROVIDER':'mock','PULSE_EMBEDDING_DIMENSION':'16',
      'PULSE_IAM_ISSUER_URL':adapter.ISSUER,'PULSE_IAM_JWKS_URL':adapter.ISSUER+'/.well-known/jwks.json','PULSE_IAM_TOKEN_URL':adapter.ISSUER+'/oauth2/token',
      'PULSE_IAM_CLIENT_ID':VALIDATOR,'PULSE_IAM_CLIENT_SECRET':secret['external_validator'],'PULSE_IAM_CLOCK_SKEW_SECONDS':'0',
      'PULSE_CONTROL_PLANE_CONTEXT_VALIDATION_URL':'https://cp.baobab-dev.test/v1/platform-context/validate','SSL_CERT_FILE':'/tls/ca.pem','HAYSTACK_TELEMETRY_ENABLED':'false'}
    composition=dev.read(directory/'compose.json');services=composition['services']
    services['pulse-db']={'image':dev.load_lock()['images']['postgres'],'environment':{'POSTGRES_DB':'pulse','POSTGRES_USER':'pulse','POSTGRES_PASSWORD':secret['pulse_db']},
      'volumes':['pulse-data:/var/lib/postgresql/data'],'healthcheck':{'test':['CMD','pg_isready','-U','pulse','-d','pulse'],'interval':'3s','timeout':'3s','retries':40}}
    services['pulse-qdrant']={'image':value['qdrant'],'volumes':['pulse-qdrant:/qdrant/storage']}
    # The fixture controller uses the owner's actual repositories. It is not
    # an HTTP replacement, an authority stub or a fabricated vector server.
    services['pulse-tool']={'image':image,'user':str(state['uid'])+':'+str(state['gid']),'entrypoint':['python'],'environment':env,
      'volumes':[tls+':/tls:ro',adapter.host(fixtures)+':/run/l4:ro',adapter.host(BASE.parent/'int02/pulse_native.py')+':/pulse_native.py:ro',adapter.host(BASE/'external_validator.py')+':/external_validator.py:ro']}
    services['pulse']={'image':image,'environment':env,'volumes':[tls+':/tls:ro']}
    services['probe']['volumes'] += [adapter.host(BASE/name)+':/'+name+':ro' for name in ('external_probe.py','external_contract.py')]
    services['edge']['networks']['lab']['aliases']+=['pulse.baobab-dev.test']
    extra='server { listen 443 ssl; server_name pulse.baobab-dev.test; ssl_certificate /tls/edge.pem; ssl_certificate_key /tls/edge.key; location / { set $target http://pulse:8000; proxy_pass $target; proxy_set_header Host pulse.baobab-dev.test; proxy_set_header X-Forwarded-Proto https; } }\n'
    (directory/'nginx.conf').write_text(adapter.EDGE[:-2]+extra+'}\n')
    composition['volumes'].update({name:{'labels':labels} for name in ('pulse-data','pulse-qdrant')})
    for item in services.values():item.update(labels=labels,restart='no');item.setdefault('networks',['lab'])
    dev.write(directory/'compose.json',composition);state['compose_sha256']=hashlib.sha256((directory/'compose.json').read_bytes()).hexdigest();dev.persist(directory,state,'RUNNING')
    print('DEV06_PHASE=NATIVE_PROVIDER',flush=True)
    dev.compose(directory,state,'up','-d','--wait','--wait-timeout','120','pulse-db','pulse-qdrant','probe','edge',timeout=180)
    dev.compose(directory,state,'exec','-T','probe','python','/external_probe.py','clients')
    dev.compose(directory,state,'run','--rm','--no-deps','pulse-tool','scripts/migrate.py',timeout=180)
    native=json.loads(dev.compose(directory,state,'run','--rm','--no-deps','pulse-tool','/pulse_native.py',timeout=180).splitlines()[-1])
    required={'pulse_native_persisted_search','pulse_native_canonical_hydration','pulse_native_classification_denied','pulse_native_neighbour_denied','pulse_native_stale_projection_observed','pulse_native_actual_dependencies'}
    dev.require(set(native)=={'checks'} and set(native['checks'])==required and all(v is True for v in native['checks'].values()),'DEV06_NATIVE_PROVIDER_FAILED')
    state['external']['component_checks'].update(native_pulse_dependencies=True,native_canonical_hydration=True,native_cross_tenant_no_leak=True)
    dev.persist(directory,state,'RUNNING')
    dev.compose(directory,state,'up','-d','pulse')
    for _ in range(60):
        try:
            if json.loads(dev.compose(directory,state,'exec','-T','probe','python','/external_probe.py','health',timeout=15))=={'pulse':200}:break
        except (dev.Refused,ValueError):pass  # Startup cannot advance readiness.
        time.sleep(2)
    else:raise dev.Refused('DEV06_PROVIDER_UNAVAILABLE')
    dev.test(run);directory,state=dev.current(run);verify_runtime(directory,state)
    state['external_runtime_identity_verified']=True;dev.persist(directory,state,'TESTED')

def qualify(run):
    directory,state=dev.current(run);verify_runtime(directory,state);check_facts(directory,state)
    previous=state['external']
    report=contract.fresh(run)
    report['component_checks']={key:previous['component_checks'][key] for key in ('native_pulse_dependencies','native_canonical_hydration','native_cross_tenant_no_leak') if key in previous['component_checks']}
    state['external']=report;dev.persist(directory,state,'TESTED')
    report['component_checks']['zero_estates_read_before']=True
    report['cases']['zero-estates']={'result':'PASS','reason':'OBSERVED'}
    dev.write(directory/'external-report.json',report)
    try:
        direct=dev.compose(directory,state,'exec','-T','probe','python','/external_probe.py','authority-input',timeout=30)
        if direct in {'DEV06_DIRECT_CP=READY','DEV06_DIRECT_CP=REFUSED'}:print(direct,flush=True)
        observed=json.loads(dev.compose(directory,state,'run','--rm','--no-deps','pulse-tool','/external_validator.py',timeout=30).splitlines()[-1])
        stages={'TOKEN','CONTEXT','READY'}
        reasons={'UNKNOWN','OBSERVED','TOKEN_TRANSPORT','TOKEN_PROFILE','VALIDATOR_AUTHENTICATION','CONTEXT_UNAVAILABLE','CONTEXT_DENIED','CONTEXT_UNKNOWN','CONTEXT_IDENTITY','CONTEXT_TENANT','CONTEXT_UNBOUNDED','CONTEXT_EXPIRY'}
        if set(observed)=={'stage','reason'} and observed['stage'] in stages and observed['reason'] in reasons:
            print('DEV06_OWNER_AUTHORITY='+observed['stage']+':'+observed['reason'],flush=True)
        dev.compose(directory,state,'exec','-T','probe','python','/external_probe.py','initial',timeout=180)
        dev.compose(directory,state,'stop','cp')
        try:dev.compose(directory,state,'exec','-T','probe','python','/external_probe.py','outage',timeout=30)
        finally:dev.compose(directory,state,'up','-d','cp')
        time.sleep(3)
        dev.compose(directory,state,'exec','-T','probe','python','/external_probe.py','restored',timeout=40)
        check_facts(directory,state)
        dev.compose(directory,state,'exec','-T','probe','python','/external_probe.py','finish',timeout=30)
        report=dev.read(directory/'external-report.json');report['component_checks']['zero_estates_read_after']=True
        dev.write(directory/'external-report.json',report)
    finally:
        if (directory/'external-report.json').exists():
            state['external']=contract.validate(dev.read(directory/'external-report.json'),run);dev.persist(directory,state,'TESTED')
