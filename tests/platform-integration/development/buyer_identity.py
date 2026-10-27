"""DEV-07 real issuer/CP/native-handler composition on the common lifecycle.

Uses owner commands and pinned source. No canonical topology SQL, stub bearer,
synthetic CP response or provider activation. The Trade tool image is explicitly
separate from its production runtime. Original INT-05 acceptance stays open.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import sys
from datetime import datetime, timezone

import dev
import adapter
import buyer_identity_contract as contract

BASE=Path(__file__).resolve().parent
BFF='baobab-dev-zuribeans-bff'
VALIDATOR='baobab-dev-trade-buyer-validator'


def lock():
    value=json.loads((BASE/'buyer-identity-owner-lock.json').read_text(),object_pairs_hook=dev.unique)
    dev.require(set(value)=={'schema','trade_source_sha'} and value['schema']=='infrastructure.dev07-buyer-owner.v1' and dev.SHA.fullmatch(value['trade_source_sha']),'DEV07_TRADE_PIN_REQUIRED')
    return value


def prepare():
    run=dev.prepare(lock_name='buyer-identity-base-lock.json')
    try:
        directory,state=dev.current(run)
        state['buyer_identity_profile']=True
        state['secrets']['dev07_trade_db']=secrets.token_hex(32)
        # Import only the exact IAM-owned source; engine code never runs in
        # the host's privileged orchestration process.
        path=directory/'sources/baobab-iam/scripts/dev07_buyer_fixture.py'
        spec=importlib.util.spec_from_file_location('iam_dev07_buyer',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        import yaml
        registry=yaml.safe_load((directory/'sources/shared/contracts/identity/v1/workload-registry.yaml').read_text())
        docs=module.build_clients(registry,run,datetime.fromtimestamp(state['deadline'],timezone.utc),
            {BFF:secrets.token_urlsafe(32),VALIDATOR:secrets.token_urlsafe(32)})
        dev.write(directory/'buyer-client-spec.json',docs)
        dev.persist(directory,state,'PREPARED')
        return run
    except BaseException:
        dev.down(run);raise


def cp_fixture(directory,state,phase):
    subjects=dev.read(directory/'subjects.json')
    raw=dev.compose(directory,state,'run','--rm','--no-deps','-e','BAOBAB_DEV_BOOTSTRAP_ENABLED=true',
        '--entrypoint','/development-bootstrap','cp','--buyer-identity-phase',phase,
        '--run-id',state['run_id'],'--issuer',adapter.ISSUER,'--maker-subject',subjects['maker'],
        '--checker-subject',subjects['checker'],'--lease',str(state['bootstrap_lease'])+'s',timeout=120)
    value=json.loads(raw,object_pairs_hook=dev.unique)
    dev.require(value['run_id']==state['run_id'] and value['synthetic_only'] is True
        and value['protected_acceptance'] is False and value['status'] in {'ACTIVE','SUSPENDED','REVOKED'},'DEV07_CP_OWNER_FIXTURE_REFUSED')
    dev.require(datetime.fromisoformat(value['expires_at'].replace('Z','+00:00')).timestamp()<=state['deadline'],'DEV07_CP_LEASE_EXCEEDED')
    dev.write(directory/'buyer-fixture.json',value)
    return value


def run_native(run):
    print("DEV07_STAGE=BASE_UP",flush=True)
    dev.up(run)
    print("DEV07_STAGE=BASE_TEST",flush=True)
    dev.test(run)
    print("DEV07_STAGE=CP_FIXTURE",flush=True)
    directory,state=dev.current(run)
    fixture=cp_fixture(directory,state,'prepare')
    dev.require(cp_fixture(directory,state,'read')==fixture,'DEV07_CP_READBACK_CHANGED')
    print('DEV07_STAGE=TRADE_SOURCE',flush=True)
    source=directory/'sources/baobab-trade'
    # Clone precisely the reviewed owner source into this run's private tree.
    dev.call(['git','init','-q',str(source)],state=state)
    sha=lock()['trade_source_sha']
    dev.call(['git','-C',str(source),'fetch','--quiet','--depth','1','https://github.com/baobab-platform/baobab-trade.git',sha],state=state,timeout=180)
    dev.call(['git','-C',str(source),'checkout','--quiet','--detach','FETCH_HEAD'],state=state)
    dev.require(dev.call(['git','-C',str(source),'rev-parse','HEAD'])==sha and not dev.call(['git','-C',str(source),'status','--porcelain']),'DEV07_TRADE_SOURCE_DRIFT')
    state['sources']['baobab-trade']=sha
    image=state['project']+'-trade-buyer-tool'
    state['images']['trade-buyer-tool']=image;dev.persist(directory,state,'RUNNING')
    dockerfile=source/'Dockerfile.dev07';dev.check_dockerfile(dockerfile)
    # The disposable tool runs as the private packet owner, not root and not
    # an image's hardcoded node UID (Codespaces remaps the remote user).
    args=['docker','build','--tag',image,'--file',str(dockerfile),
          '--build-arg','BAOBAB_DEV07_UID='+str(state['uid']),
          '--build-arg','BAOBAB_DEV07_GID='+str(state['gid'])]
    for key,value in {**dev.labels(state),'org.opencontainers.image.revision':sha}.items():args+=['--label',key+'='+value]
    print('DEV07_STAGE=TRADE_BUILD',flush=True)
    dev.call([*args,str(source)],state=state,timeout=1800)
    state['image_ids']['trade-buyer-tool']=dev.call(['docker','image','inspect',image,'--format','{{.Id}}'],state=state)
    dev.require(dev.DIGEST.fullmatch(state['image_ids']['trade-buyer-tool']),'DEV07_IMAGE_ID_REQUIRED')
    config=dev.read(directory/'compose.json');labels=dev.labels(state);tls=adapter.host(directory/'tls')
    database='dev07_trade_'+run[:12]+'_test'
    dbsecret=state['secrets']['dev07_trade_db']
    config['services']['trade-buyer-db']={'image':dev.load_lock('buyer-identity-base-lock.json')['images']['postgres'],
        'environment':{'POSTGRES_DB':database,'POSTGRES_USER':'dev07_trade','POSTGRES_PASSWORD':dbsecret},
        'volumes':['trade-buyer-data:/var/lib/postgresql/data'],
        'healthcheck':{'test':['CMD-SHELL','pg_isready -U dev07_trade -d '+database],'interval':'3s','timeout':'3s','retries':40}}
    # Private source tool receives only its own DB and issuer/client evidence;
    # no CP database credentials or Docker socket are mounted into it.
    specs=dev.read(directory/'buyer-client-spec.json');output=directory/'buyer-report';output.mkdir(mode=0o700)
    env={'NODE_ENV':'test','BAOBAB_ENVIRONMENT':'development',# This is an isolated Docker-internal PG17 service without TLS.
        # Medusa treats non-localhost hosts as remote and otherwise forces SSL,
        # unlike the explicitly sslmode=disable CP integration configuration.
        # Never copy this development-only setting into staging/production.
        'DATABASE_URL':f'postgres://dev07_trade:{dbsecret}@trade-buyer-db:5432/{database}?sslmode=disable',
        'BAOBAB_DEV07_TEST_DB':database,'BAOBAB_DEV07_CODE_PACKET':'/run/buyer-code-packet.json',
        'BAOBAB_BUYER_IDENTITY_ENABLED':'true','BAOBAB_IAM_BUYER_ISSUER':adapter.ISSUER,'BAOBAB_IAM_BUYER_AUTHORISED_PARTIES':BFF,
        'BAOBAB_BUYER_ACCEPTED_ACR':'aal1','BAOBAB_BUYER_ASSURANCE_APPROVAL_REFERENCE':'ADR-SHARED-043:'+run,
        'BAOBAB_TRADE_ENGINE_INSTANCE_ID':fixture['engine_instance_id'],'BAOBAB_CONTROL_PLANE_BASE_URL':'https://cp.baobab-dev.test',
        'BAOBAB_IAM_WORKLOAD_TOKEN_URL':adapter.ISSUER+'/oauth2/token','BAOBAB_IAM_WORKLOAD_CLIENT_ID':VALIDATOR,
        'BAOBAB_IAM_WORKLOAD_CLIENT_SECRET':specs[VALIDATOR]['client_secret'],'NODE_EXTRA_CA_CERTS':'/tls/ca.pem',
        'JWT_SECRET':secrets.token_hex(32),'COOKIE_SECRET':secrets.token_hex(32)}
    # Migrations do not read a code packet. Use a separate overlay after codes
    # exist, avoiding Docker's file-mount autovivification and OAuth expiry.
    config['services']['trade-buyer-tool']={'image':state['image_ids']['trade-buyer-tool'],'user':str(state['uid'])+':'+str(state['gid']),
        'environment':env,'volumes':[tls+':/tls:ro',adapter.host(output)+':/app/artifacts/dev07-iam-cp']}
    config['volumes']['trade-buyer-data']={'labels':labels}
    for name in ('trade-buyer-db','trade-buyer-tool'):
        config['services'][name].update(labels=labels,restart='no',networks=['lab'])
    dev.write(directory/'compose.json',config);state['compose_sha256']=hashlib.sha256((directory/'compose.json').read_bytes()).hexdigest();dev.persist(directory,state,'RUNNING')
    dev.compose(directory,state,'up','-d','--wait','--wait-timeout','120','trade-buyer-db',timeout=180)
    print('DEV07_STAGE=TRADE_MIGRATE',flush=True)
    # Prove the actual non-root run UID and its writable Medusa/npm paths
    # before migration; no credentials or directory content are emitted.
    dev.require(dev.compose(directory,state,'run','--rm','--no-deps','trade-buyer-tool','id','-u',timeout=30)
        == str(state['uid']),'DEV07_TOOL_UID_MISMATCH')
    try:
        dev.compose(directory,state,'run','--rm','--no-deps','trade-buyer-tool','sh','-c',
            'test -w /app && test -w /app/node_modules && test -w "$HOME"',timeout=30)
    except dev.Refused:
        raise dev.Refused('DEV07_TOOL_FILESYSTEM_NOT_WRITABLE') from None
    dev.compose(directory,state,'run','--rm','--no-deps','trade-buyer-tool','npm','run','migrate',timeout=240)
    print('DEV07_STAGE=NATIVE_PACKET',flush=True)
    dev.compose(directory,state,'exec','-T','probe','python','/buyer_identity_probe.py','packet',timeout=60)
    packet=directory/'buyer-code-packet.json'
    dev.require(packet.is_file() and packet.stat().st_mode & 0o077==0,'DEV07_PRIVATE_PACKET_REQUIRED')
    config['services']['trade-buyer-tool']['volumes'].append(adapter.host(packet)+':/run/buyer-code-packet.json:ro')
    dev.write(directory/'compose.json',config);state['compose_sha256']=hashlib.sha256((directory/'compose.json').read_bytes()).hexdigest();dev.persist(directory,state,'RUNNING')
    print('DEV07_STAGE=TRADE_QUALIFIER',flush=True)
    try:
        dev.compose(directory,state,'run','--rm','--no-deps','trade-buyer-tool',timeout=180)
    finally:
        # Even a failed assertion may produce sanitized BLOCKED/FAIL evidence.
        path=output/'report.json'
        if path.is_file():
            raw=path.read_bytes();value=json.loads(raw,object_pairs_hook=dev.unique)
            sidecar=json.loads(path.with_name('report.sha256.json').read_text(),object_pairs_hook=dev.unique)
            dev.require(hashlib.sha256(raw).hexdigest()==sidecar['sha256'],'DEV07_COMPONENT_HASH_MISMATCH')
            contract.validate(value,sha);state['dev07_buyer']=value
            dev.persist(directory,state,'RUNNING')
    dev.require(state.get('dev07_buyer',{}).get('iam_cp_component_qualified') is True,'DEV07_COMPONENT_NOT_QUALIFIED')
    dev.compose(directory,state,'exec','-T','probe','python','/buyer_identity_probe.py','binding-control',timeout=30)


def cleanup_owners(run):
    directory,state=dev.current(run)
    failed=False
    # Attempt every owner cleanup independently. An unavailable CP witness
    # must not prevent native issuer client deletion, or host teardown later.
    try:
        cp_fixture(directory,state,'revoke')
        dev.require(cp_fixture(directory,state,'read')['status']=='REVOKED','DEV07_CP_BINDING_SURVIVED')
        dev.compose(directory,state,'exec','-T','probe','python','/buyer_identity_probe.py','binding-revoked',timeout=30)
        state['dev07_binding_revocation_verified']=True
    except Exception:failed=True
    try:
        dev.compose(directory,state,'exec','-T','probe','python','/buyer_identity_probe.py','cleanup',timeout=60)
        state['dev07_issuer_cleanup']=True
    except Exception:failed=True
    dev.persist(directory,state,state['phase'])
    dev.require(not failed,'DEV07_OWNER_CLEANUP_INCOMPLETE')


def main():
    for name in ('dev07-buyer-suite.json','dev07-buyer-suite.sha256.json'):(dev.EVIDENCE/name).unlink(missing_ok=True)
    run=None;failed=False
    try:
        run=prepare()
        with dev.guarded(run):run_native(run)
    except Exception as error:
        failed=True
        # Closed orchestration classifications; no provider error text escapes.
        reason=str(error)
        if reason in {'IAM_CP_HEALTH_FAILED','COMMAND_FAILED','COMMAND_TIMEOUT','BOOTSTRAP_REPLAY_MISMATCH','LEASE_EXPIRED',
                      'DEV07_MIGRATE_DEPENDENCY_MISSING','DEV07_MIGRATE_DATABASE_CONNECT','DEV07_MIGRATE_PERMISSION',
                      'DEV07_MIGRATE_CONFIG','DEV07_MIGRATE_NATIVE_MODULE','DEV07_MIGRATE_UNKNOWN',
                      'DEV07_MIGRATE_HOME_PERMISSION','DEV07_MIGRATE_APP_PERMISSION',
                      'DEV07_MIGRATE_DATABASE_PERMISSION','DEV07_MIGRATE_MOUNT_PERMISSION',
                      'DEV07_MIGRATE_EXEC_PERMISSION','DEV07_TOOL_UID_MISMATCH',
                      'DEV07_TOOL_FILESYSTEM_NOT_WRITABLE'}:
            print('DEV07_FAILURE_CLASS='+reason,flush=True)
        print('DEV07_RUNTIME_NOT_QUALIFIED',flush=True)
    finally:
        if run:
            try:
                with dev.guarded(run):cleanup_owners(run)
            except Exception:
                failed=True
                print('DEV07_OWNER_CLEANUP_NOT_OBSERVED',flush=True)
            finally:
                with dev.guarded(run):dev.down(run)
    dev.require(run is not None,'DEV07_PREPARATION_FAILED')
    receipt=dev.read(dev.EVIDENCE/('dev01-'+run)/'completed/receipt.json')
    dev.require(receipt['teardown_verified'] is True and not dev.resources(run) and not dev.run_dir(run).exists(),'DEV07_HOST_TEARDOWN_REQUIRED')
    component=receipt.get('dev07_buyer')
    if component:contract.validate(component,lock()['trade_source_sha'])
    result={'schema':'infrastructure.dev07-buyer-qualified.v1','lifecycle':receipt,
        'iam_cp_native_component_qualified':not failed and bool(component and component['iam_cp_component_qualified']) and receipt.get('dev07_issuer_cleanup') is True and receipt.get('dev07_binding_revocation_verified') is True,
        'int05_qualified':False,'bff_http_qualified':False,'provider_qualified':False,'protected_acceptance':False,'production_authorized':False}
    path=dev.EVIDENCE/'dev07-buyer-suite.json';dev.write(path,result)
    dev.write(path.with_suffix('.sha256.json'),{'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    dev.require(result['iam_cp_native_component_qualified'],'DEV07_NOT_QUALIFIED')
    print('DEV07_IAM_CP_NATIVE_COMPONENTS_AND_HOST_TEARDOWN_PASS')


if __name__=='__main__':
    sys.dont_write_bytecode=True
    try:main()
    except Exception:raise SystemExit('DEV07_QUALIFICATION_FAILED; recover the owned development run') from None
