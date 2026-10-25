#!/usr/bin/env python3
"""Minimal authentic IAM/CP/Subscriptions/PG17 run, with shared crash cleanup."""
import hashlib
import json
from pathlib import Path
import sys
import time
sys.dont_write_bytecode=True
import adapter
import dev
import subscriptions_contract as contract

BASE=Path(__file__).resolve().parent

def fixture(directory,state,phase):
    subjects=dev.read(directory/'subjects.json')
    raw=dev.compose(directory,state,'run','--rm','--no-deps','-e','BAOBAB_DEV_BOOTSTRAP_ENABLED=true',
        '--entrypoint','/development-bootstrap','cp','--run-id',state['run_id'],'--issuer',adapter.ISSUER,
        '--maker-subject',subjects['maker'],'--checker-subject',subjects['checker'],
        '--lease',str(state['bootstrap_lease'])+'s','--subscriptions-phase',phase)
    value=json.loads(raw,object_pairs_hook=dev.unique)
    dev.require(set(value)=={'tenant_id','other_tenant_id','organisation_id','product_subscription_id',
        'classification_id','classification_reference','legal_entity_id','authoritative_revision','status'}
        and value['tenant_id']!=value['other_tenant_id'],'SUBSCRIPTIONS_CP_FIXTURE_INVALID')
    return value

def probe(directory,state,action):
    return dev.compose(directory,state,'exec','-T','probe','python','/subscriptions_probe.py',action,timeout=90)

def validate_owner_flags(environment,application):
    # Unknown environment switches are silently ignored by Java. Refuse a
    # misspelled feature flag before claiming the intended native route ran.
    for key in environment:
        if key.endswith('_ENABLED'):
            dev.require('System.getenv("'+key+'")' in application,'SUBSCRIPTIONS_UNKNOWN_OWNER_FEATURE_FLAG')

def wait_ready(directory,state):
    """Bounded readiness polling, never retries a failed acceptance case."""
    for _ in range(60):
        try:
            if json.loads(probe(directory,state,'health'))=={'subscriptions':200}:return
        except (dev.Refused,ValueError):
            # Transport/non-JSON errors are expected only during startup.
            # They cannot advance readiness and the bounded loop still fails.
            pass
        time.sleep(2)
    raise dev.Refused('SUBSCRIPTIONS_SERVICE_UNAVAILABLE')

def verify(directory,state):
    dev.verify_sources(directory,state)
    for name in ('subscriptions','subscriptions-db'):
        container=dev.compose(directory,state,'ps','-q',name)
        actual=json.loads(dev.call(['docker','inspect',container]))[0]
        expected=state['image_ids'].get(name) or dev.call(['docker','image','inspect',state['runtime_images']['postgres'],'--format','{{.Id}}'])
        dev.require(actual['Image']==expected and not actual['HostConfig']['PortBindings']
            and not actual['HostConfig']['Privileged'] and actual['Config']['Labels'].get('io.baobab.dev.run')==state['run_id'],
            'SUBSCRIPTIONS_RUNTIME_IDENTITY')
        nets=actual['NetworkSettings']['Networks'];dev.require(len(nets)==1,'SUBSCRIPTIONS_NETWORK_COUNT')
        dev.require(json.loads(dev.call(['docker','network','inspect',next(iter(nets))]))[0]['Internal'] is True,
            'SUBSCRIPTIONS_PUBLIC_NETWORK')

def up(run):
    directory,state=dev.current(run)
    state['subscriptions_profile']=True
    state['secrets']['subscriptions_db']=__import__('secrets').token_hex(32)
    dev.persist(directory,state,'PREPARED')
    dev.up(run)
    dev.test(run);directory,state=dev.current(run)
    pin=json.loads((BASE/'subscriptions-lock.json').read_text(),object_pairs_hook=dev.unique)
    dev.require(set(pin)=={'schema','source'} and pin['schema']=='infrastructure.subscriptions.sources.v1'
        and set(pin['source'])=={'baobab-subscriptions'} and dev.SHA.fullmatch(pin['source']['baobab-subscriptions']),
        'SUBSCRIPTIONS_SOURCE_LOCK')
    target=directory/'sources/baobab-subscriptions';sha=pin['source']['baobab-subscriptions']
    dev.call(['git','init','-q',str(target)])
    dev.call(['git','-C',str(target),'fetch','--quiet','--depth','1','https://github.com/baobab-platform/baobab-subscriptions.git',sha],timeout=180,state=state)
    dev.call(['git','-C',str(target),'checkout','--quiet','--detach','FETCH_HEAD'],state=state)
    state['sources']['baobab-subscriptions']=sha
    image=state['project']+'-subscriptions';state['images']['subscriptions']=image;dev.persist(directory,state,'TESTED')
    dev.check_dockerfile(target/'Dockerfile')
    arguments=['docker','build','--tag',image,'--file',str(target/'Dockerfile')]
    for key,value in {**dev.labels(state),'org.opencontainers.image.revision':sha}.items(): arguments+=['--label',key+'='+value]
    print('SUBSCRIPTIONS_PHASE=OWNER_BUILD',flush=True)
    dev.call([*arguments,str(target)],timeout=1800,state=state)
    state['image_ids']['subscriptions']=dev.call(['docker','image','inspect',image,'--format','{{.Id}}'])
    identity=directory/'subscriptions-identity';identity.mkdir(mode=0o700)
    for name,value in [('cp-token','pending'),('introspection-secret',state['secrets']['introspection'])]:
        (identity/name).write_text(value);(identity/name).chmod(0o644)
    dev.call(['docker','run','--rm','--user',str(state['uid'])+':'+str(state['gid']),
        '-v',adapter.host(directory/'tls')+':/tls:ro','-v',adapter.host(identity)+':/identity',
        '--entrypoint','keytool',image,'-importcert','-noprompt','-alias','development-ca',
        '-file','/tls/ca.pem','-keystore','/identity/truststore.p12','-storepass','changeit'],timeout=60,state=state)
    (identity/'truststore.p12').chmod(0o644)
    composition=dev.read(directory/'compose.json');services=composition['services'];labels=dev.labels(state)
    services['subscriptions-db']={'image':state['runtime_images']['postgres'],
        'environment':{'POSTGRES_DB':'subscriptions','POSTGRES_USER':'subscriptions','POSTGRES_PASSWORD':state['secrets']['subscriptions_db']},
        'volumes':['subscriptions-data:/var/lib/postgresql/data'],
        'healthcheck':{'test':['CMD','pg_isready','-U','subscriptions','-d','subscriptions'],'interval':'3s','timeout':'3s','retries':40}}
    env={'BAOBAB_ENVIRONMENT':'development','DATABASE_URL':'jdbc:postgresql://subscriptions-db:5432/subscriptions',
        'DATABASE_USER':'subscriptions','DATABASE_PASSWORD':state['secrets']['subscriptions_db'],
        'WORKLOAD_ISSUER':adapter.ISSUER,'WORKLOAD_JWKS_URI':adapter.ISSUER+'/.well-known/jwks.json',
        'WORKLOAD_AUDIENCE':'baobab-subscriptions','WORKLOAD_ALLOWED_CLIENTS':'baobab-dev-cp-subscriptions',
        'CP_SUBSCRIPTION_PROJECTION_AUTHORITY_ENABLED':'true','CP_SUBSCRIPTION_CURRENT_AUTHORITY_BASE_URL':'https://cp.baobab-dev.test',
        'CP_SUBSCRIPTION_CURRENT_AUTHORITY_TOKEN_FILE':'/identity/cp-token',
        'PEO_INTERNAL_AUTHORITY_ENABLED':'true','PEO_CP_INTERNAL_AUTHORITY_BASE_URL':'https://cp.baobab-dev.test',
        'PEO_CP_INTERNAL_AUTHORITY_TOKEN_FILE':'/identity/cp-token',
        'CP_SUBSCRIPTION_LIFECYCLE_RECEIVER_ENABLED':'true','CP_SUBSCRIPTION_EVENT_CLIENT_ID':'baobab-dev-cp-subscriptions',
        'WORKLOAD_INTROSPECTION_ENDPOINT':adapter.ISSUER+'/oauth2/introspect',
        'WORKLOAD_INTROSPECTION_CLIENT_ID':'baobab-dev-introspection','WORKLOAD_INTROSPECTION_SECRET_FILE':'/identity/introspection-secret',
        'JAVA_TOOL_OPTIONS':'-Djavax.net.ssl.trustStore=/identity/truststore.p12 -Djavax.net.ssl.trustStorePassword=changeit'}
    validate_owner_flags(env,(target/'src/main/java/com/baobabplatform/subscriptions/Application.java').read_text())
    services['subscriptions']={'image':image,'pull_policy':'never','environment':env,
        'volumes':[adapter.host(identity/name)+':/identity/'+name+':ro' for name in ('cp-token','introspection-secret','truststore.p12')]}
    services['probe']['volumes'] += [adapter.host(BASE/name)+':/'+name+':ro' for name in ('subscriptions_probe.py','subscriptions_contract.py')]
    services['edge']['networks']['lab']['aliases']+=['subscriptions.baobab-dev.test']
    extra='server { listen 443 ssl; server_name subscriptions.baobab-dev.test; ssl_certificate /tls/edge.pem; ssl_certificate_key /tls/edge.key; location / { set $target http://subscriptions:8080; proxy_pass $target; proxy_set_header Host subscriptions.baobab-dev.test; proxy_set_header X-Forwarded-Proto https; } }\n'
    (directory/'nginx.conf').write_text(adapter.EDGE[:-2]+extra+'}\n')
    composition['volumes']['subscriptions-data']={'labels':labels}
    for name in ('subscriptions','subscriptions-db'):services[name].update(labels=labels,restart='no',networks=['lab'])
    dev.write(directory/'compose.json',composition);state['compose_sha256']=hashlib.sha256((directory/'compose.json').read_bytes()).hexdigest();dev.persist(directory,state,'TESTED')
    dev.compose(directory,state,'up','-d','--wait','--wait-timeout','120','subscriptions-db','probe','edge',timeout=180)
    dev.write(directory/'subscription-fixture.json',fixture(directory,state,'prepare'))
    probe(directory,state,'clients')
    dev.compose(directory,state,'up','-d','subscriptions')
    wait_ready(directory,state)
    verify(directory,state)
    return directory,state

def execute():
    run=None;cases=None;cleanup=None;failure=False
    for name in ('subscriptions-onboarding.json','subscriptions-onboarding.sha256.json'):
        (dev.EVIDENCE/name).unlink(missing_ok=True)
    try:
        run=dev.prepare(lock_name='subscriptions-base-lock.json')
        with dev.guarded(run):
            directory,state=up(run)
            print('SUBSCRIPTIONS_PHASE=NATIVE_CASES',flush=True)
            probe(directory,state,'initial')
            # The engine's credential must work for its own native store and
            # fail authentication at CP, even on this shared private network.
            # The exact server refusal proves this is not a network outage.
            database='baobab_dev_'+state['run_id']
            script='psql -h subscriptions-db -U subscriptions -d subscriptions -c "SELECT 1" >/dev/null; if psql -h cp-db -U baobab_dev -d '+database+' -c "SELECT 1" 2>/tmp/cp-auth-refusal; then exit 1; fi; grep -q "password authentication failed" /tmp/cp-auth-refusal'
            dev.compose(directory,state,'exec','-T','-e','PGPASSWORD='+state['secrets']['subscriptions_db'],
                'subscriptions-db','bash','-euo','pipefail','-c',script)
            observations=dev.read(directory/'subscriptions-cases.json')
            observations['engine-cp-database-denied']={'result':'PASS','reason':'OBSERVED'}
            dev.write(directory/'subscriptions-cases.json',observations)
            # Independent store readbacks prove actual persistence rather than
            # trusting the HTTP projection or an event receipt alone.
            count=dev.compose(directory,state,'exec','-T','subscriptions-db','psql','-U','subscriptions','-d','subscriptions','-tAc',
                "SELECT (SELECT count(*) FROM billing.projection)=1 AND (SELECT count(*) FROM billing.cp_subscription_lifecycle_inbox)=1")
            dev.require(count=='t','SUBSCRIPTIONS_NATIVE_PERSISTENCE')
            dev.compose(directory,state,'stop','subscriptions')
            dev.compose(directory,state,'restart','subscriptions-db')
            dev.compose(directory,state,'up','-d','--wait','--wait-timeout','120','subscriptions-db',timeout=180)
            dev.compose(directory,state,'up','-d','subscriptions')
            wait_ready(directory,state)
            probe(directory,state,'restart')
            dev.compose(directory,state,'stop','cp')
            try:probe(directory,state,'outage')
            finally:dev.compose(directory,state,'up','-d','cp')
            time.sleep(3);probe(directory,state,'recovery')
            fixture(directory,state,'advance');probe(directory,state,'revision')
            probe(directory,state,'finish')
            cases=contract.validate(dev.read(directory/'subscriptions-cases.json'))
            cleanup=dev.read(directory/'subscriptions-issuer-cleanup.json')
            verify(directory,state)
    except Exception:
        failure=True
        if run:
            path=dev.run_dir(run)/'subscriptions-cases.json'
            if path.exists():cases=contract.validate(dev.read(path))
    finally:
        if run:
            with dev.guarded(run):dev.down(run)
        dev.recover(all_runs=True)
    dev.require(run is not None,'SUBSCRIPTIONS_PREPARATION_FAILED')
    receipt=dev.read(dev.EVIDENCE/('dev01-'+run)/'completed/receipt.json')
    dev.require(receipt['teardown_verified'] and not dev.resources(run) and not dev.run_dir(run).exists(),
        'SUBSCRIPTIONS_TEARDOWN')
    cases=cases or contract.fresh()
    if cleanup=={'native_clients_deleted':True,'native_tokens_inactive':True}:cases['teardown']={'result':'PASS','reason':'OBSERVED'}
    contract.validate(cases)
    complete=not failure and all(cases[k]=={'result':'PASS','reason':'OBSERVED'} for k in contract.NATIVE)
    report={'schema':'infrastructure.subscriptions.onboarding.v1','source_sha':receipt['harness_sha'],
        'source_pins':receipt['source_pins'],'image_ids':receipt['image_ids'],'runtime_images':receipt['runtime_images'],
        'evidence_class':receipt['evidence_class'],'cases':cases,'result':'SUCCESS' if complete else 'FAILURE',
        'cleanup':'COMPLETE_RUN_OWNED_CONTAINERS_IMAGES_VOLUMES_NETWORKS_PRIVATE_STATE',
        'internal_authority_qualified':False,'full_onboarding_qualified':False,'int07_qualified':False,
        'provider_qualified':False,'protected_acceptance':False,'production_authorized':False,'money_moved':False}
    path=dev.EVIDENCE/'subscriptions-onboarding.json';dev.write(path,report)
    dev.write(path.with_name('subscriptions-onboarding.sha256.json'),{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    dev.require(complete,'SUBSCRIPTIONS_NATIVE_INCOMPLETE')
    print('SUBSCRIPTIONS_NATIVE_17_PASS_3_BLOCKED_INTERNAL_PREREQUISITE_UNQUALIFIED')

if __name__=='__main__':
    try:execute()
    except Exception as error:
        code=str(error) if isinstance(error,dev.Refused) else 'INVALID_OR_UNAVAILABLE_STATE'
        raise SystemExit('SUBSCRIPTIONS_ONBOARDING_FAILED '+code+'; private recovery retained on cleanup failure') from None
