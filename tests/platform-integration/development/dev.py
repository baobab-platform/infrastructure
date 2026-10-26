#!/usr/bin/env python3
"""DEV-01 ordinary development lifecycle. Never a protected approval route."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import adapter
import int03c_contract

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STATE = BASE.parent / '.runtime/dev01'
EVIDENCE = BASE.parent / 'evidence'
NONCE = re.compile(r'[0-9a-f]{32}')
SHA = re.compile(r'[0-9a-f]{40}')
DIGEST = re.compile(r'(?:[a-z0-9./:_-]+@)?sha256:[0-9a-f]{64}')
NAMESPACE = hashlib.sha256((adapter.host(ROOT.resolve()) + ':' + str(os.getuid())).encode()).hexdigest()[:24]


class Refused(Exception):
    """Only fixed, non-sensitive diagnostic codes leave this process."""


def require(ok, code):
    if not ok:
        raise Refused(code)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def read(path):
    """Read one private regular inode without following a final symlink."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and info.st_nlink == 1 and not info.st_mode & 0o077
                and info.st_size <= 1024 * 1024, 'PRIVATE_STATE_REQUIRED')
        return json.load(stream, object_pairs_hook=unique)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name('.' + path.name + '.' + secrets.token_hex(8))
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'w') as out:
            out.write(json.dumps(data, indent=2, sort_keys=True) + '\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
        handle = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)
    finally:
        temp.unlink(missing_ok=True)


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o077, 'PRIVATE_DIRECTORY_REQUIRED')


def run_dir(run_id):
    require(isinstance(run_id, str) and NONCE.fullmatch(run_id), 'RUN_ID_REQUIRED')
    private_directory(STATE)
    directory = STATE / run_id
    if directory.exists() or directory.is_symlink():
        private_directory(directory)
    return directory


@contextmanager
def guarded(run_id, nonblocking=False):
    private_directory(STATE)
    handle = os.open(STATE / (run_id + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
        yield
    finally:
        os.close(handle)


def call(args, *, timeout=120, stdin=None, state=None, env=None):
    if state is not None:
        timeout = min(timeout, state['deadline'] - time.time())
        require(timeout > 0, 'LEASE_EXPIRED')
    try:
        result = subprocess.run(args, input=stdin, env=env, text=True, capture_output=True,
                                check=False, timeout=timeout)
        if result.returncode != 0:
            # Closed diagnostics only: never print command arguments, env or logs.
            # Only the native qualifier's closed binding diagnostics may leave
            # captured subprocess output. Provider bodies/commands remain private.
            for line in result.stdout.splitlines():
                # Closed DEV-06 diagnostics never expose arbitrary issuer or
                # engine bodies, token material, context IDs or credentials.
                if re.fullmatch(r'SUBSCRIPTIONS_REVOCATION=[1-5][0-9]{2}:[1-5][0-9]{2}:(true|false|unknown):[1-5][0-9]{2}',line):print(line,flush=True)
                if line in {prefix+'_OWNER_STAGE='+name for prefix in ('DEV05','DEV06') for name in ('REGISTER','OCI','READINESS','HEALTH','RELEASE','RELEASE_APPROVAL','PROVIDER_ACTIVATION','COMPOSITION','SUBSCRIPTION','EXPANSION','BINDING','CONTROL')}:print(line,flush=True)
                if line.startswith('SUBSCRIPTIONS_CASE='):
                    import subscriptions_contract
                    if line.removeprefix('SUBSCRIPTIONS_CASE=') in subscriptions_contract.NATIVE:print(line,flush=True)
                if line.startswith('DEV06_PROBE_CASE='):
                    import external_contract
                    if line[len('DEV06_PROBE_CASE='):] in external_contract.CASES:print(line,flush=True)
                if line in {'DEV06_RESOURCE_HTTP='+str(code) for code in (200,400,401,403,404,500,502,503,504)}:print(line,flush=True)
                if line in {'DEV06_RESOURCE_CODE='+code for code in ('AUTH_TOKEN_INVALID','CAPABILITY_AUTHORITY_UNAVAILABLE','CAPABILITY_ACCESS_DENIED','CONTEXT_NOT_FOUND','PULSE_INTERNAL_ERROR','CAPABILITY_RUNTIME_UNAVAILABLE','SEMANTIC_RETRIEVAL_UNAVAILABLE')}:print(line,flush=True)
                if line in {'DEV05_PROBE_STAGE='+name for name in ('BFF_LOGIN','BFF_KRATOS_FLOW','BFF_KRATOS_LOGIN','BFF_INITIATE','BFF_PKCE','BFF_AUTHORIZE','BFF_CALLBACK',
                        'BFF_SESSION','BFF_LOGOUT','CMS_CONTEXT','CMS_RECORDS','CANONICAL_RESOLUTION','ESTATE_PUBLISHED_CONTENT')}:
                    print(line,flush=True)
                if re.fullmatch(r'DEV05_ESTATE_HTTP=[1-5][0-9]{2}_MARKERS_(PRESENT|ABSENT)',line):print(line,flush=True)
                # Only static keys/reason classes may cross the native CMS
                # runner boundary; actual responses and identity data stay private.
                if re.fullmatch(r'DEV05_RECORD_DIAGNOSTIC=(HOME|NAVIGATION|FOOTER)_(CONFIG_NOT_READY|CALLER_STATUS_UNAVAILABLE|VALIDATOR_UNAVAILABLE|PROJECTION_UNAVAILABLE|CONTEXT_UNAVAILABLE|HTTP_500|HTTP_502|HTTP_503|HTTP_504|HTTP_DENIED|HTTP_UNAVAILABLE|INVALID_BODY|NO_RECORD|NOT_PUBLISHED|WRONG_CONTENT_KEY|WRONG_TENANT|UNEXPECTED)',line):
                    print(line,flush=True)
                if line in {'DEV05_VALIDATOR_PROFILE='+name for name in (
                        'UNAVAILABLE','ISSUANCE_REFUSED','INTROSPECTION_REFUSED','INACTIVE',
                        'ISSUER_MISMATCH','CLIENT_MISMATCH','ACTOR_MISMATCH','SCOPE_MISMATCH',
                        'AUDIENCE_MISMATCH','OWNER_MISMATCH','ENVIRONMENT_MISMATCH',
                        'SUBJECT_MISMATCH','TIME_MISMATCH','READY')}:
                    print(line,flush=True)
                if line.startswith('DEV04_BINDING='):
                    try:
                        value = json.loads(line[len('DEV04_BINDING='):], object_pairs_hook=unique)
                        keys = {'active','issuer_bound','subject_bound','client_bound','audience_bound','scope_bound',
                                'integer_times','expiry_bound','issued_at_bound','lifetime_bounded','current_time_bound'}
                        if (set(value) == keys | {'jwt_lifetime_seconds'} and all(type(value[k]) is bool for k in keys)
                                and (value['jwt_lifetime_seconds'] is None or type(value['jwt_lifetime_seconds']) is int
                                     and 0 <= value['jwt_lifetime_seconds'] <= 900)):
                            print('DEV04_BINDING=' + json.dumps(value, sort_keys=True), flush=True)
                    except (ValueError, TypeError, Refused):
                        pass  # Unknown diagnostics never cross the custody boundary.
            raw=(result.stdout+result.stderr).lower()
            classification='COMMAND_FAILED'
            for needle,code in (('toomanyrequests','IMAGE_RATE_LIMITED'),('429 too many','IMAGE_RATE_LIMITED'),
                                ('failed to resolve source metadata','IMAGE_UNAVAILABLE'),('failed to fetch oauth token','IMAGE_UNAVAILABLE'),
                                ('manifest unknown','IMAGE_UNAVAILABLE'),('invalid config','INVALID_PROVIDER_CONFIGURATION'),
                                ('field not found','INVALID_PROVIDER_CONFIGURATION'),('permission denied','RUNTIME_PERMISSION_DENIED')):
                if needle in raw: classification=code;break
            matched=re.search(r'DEV03_PROVIDER_PROBE_FAILED ([A-Z][A-Z0-9_]{0,80})',result.stderr)
            known={'NATIVE_PROTOCOL_FAILED','PROVIDER_OBSERVATION_FAILED','KRATOS_CREATE','KRATOS_READBACK',
                   'HYDRA_CREATE','HYDRA_READBACK','SIGNED_TOKEN_ISSUANCE','REAL_KRATOS_LOGIN','KRATOS_CURRENT_SESSION',
                   'REAL_AUTHORIZATION_REDIRECT','LOGIN_CHALLENGE_BINDING','CONSENT_BINDING','PKCE_STATE_CALLBACK',
                   'REAL_SIGNED_HUMAN_TOKEN','REAL_PKCE_MISMATCH_DENIED','CODE_REPLAY_DENIED','CP_PROVENANCE_PROPOSE',
                   'CP_PROVENANCE_APPROVE','CP_DEACTIVATION_PROPOSE','CP_DISTINCT_CHECKER','REAL_SHORT_LIVED_TOKEN_REQUIRED'}
            known.update('DEV03_'+name.upper() for name in AUTHORITY_CASES)
            if matched and matched[1] in known: classification='PROBE_'+matched[1]
            # CMS intentionally emits no raw error: only this finite, reviewed
            # stage vocabulary may cross the private subprocess boundary.
            # Reject provider-authored messages, unknown phases and embellishments.
            fixture_stages={'BOUNDARY','REFERENCE_DECLARATION','PAYLOAD_INIT','PG17_CHECK',
                            'ESTATE_PROJECTION','CONTENT_SEED','PUBLICATION','READBACK','DESTROY'}
            if 'scripts/qualification/int03-fixture.ts' in args:
                for line in (result.stdout+'\n'+result.stderr).splitlines():
                    prefix='CMS_INT03_STAGE_FAILED='
                    if line.startswith(prefix) and line[len(prefix):] in fixture_stages:
                        classification='CMS_FIXTURE_'+line[len(prefix):]
                        break
            raise Refused(classification)
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError) as error:
        raise Refused('COMMAND_UNAVAILABLE_OR_TIMED_OUT') from error


def load_lock(lock_name='lock.json'):
    require(lock_name in {'lock.json', 'subscriptions-base-lock.json', 'external-base-lock.json', 'cms-base-lock.json'}, 'UNKNOWN_SOURCE_LOCK')
    data = json.loads((BASE / lock_name).read_text(), object_pairs_hook=unique)
    require(set(data) == {'schema', 'profile', 'authority', 'infrastructure_baseline', 'sources',
                         'images', 'max_lease_seconds', 'synthetic_only', 'protected_acceptance'}, 'LOCK_SHAPE')
    require(data['schema'] == 'infrastructure.development-lifecycle.v1'
            and data['profile'] == 'iam-cp-development' and data['authority'] == 'ADR-SHARED-043'
            and data['synthetic_only'] is True and data['protected_acceptance'] is False
            and data['max_lease_seconds'] == 3600 and SHA.fullmatch(data['infrastructure_baseline']), 'LOCK_POLICY')
    require(set(data['sources']) == {'shared', 'baobab-cp', 'baobab-iam'}
            and all(isinstance(v, str) and SHA.fullmatch(v) for v in data['sources'].values()), 'SOURCE_PIN_REQUIRED')
    require(set(data['images']) == {'postgres', 'probe', 'edge', 'hydra', 'kratos'} and all(
        isinstance(v, str) and '@sha256:' in v and DIGEST.fullmatch(v) for v in data['images'].values()), 'IMAGE_DIGEST_REQUIRED')
    check_dockerfile(BASE / 'iam.Dockerfile')
    return data


def check_dockerfile(path):
    for line in path.read_text().splitlines():
        if line.startswith('FROM '):
            require('@sha256:' in line and DIGEST.fullmatch(line.split()[1]), 'BUILDER_DIGEST_REQUIRED')


def source_identity():
    sha = call(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'])
    require(SHA.fullmatch(sha) and not call(['git', '-C', str(ROOT), 'status', '--porcelain']), 'CLEAN_HARNESS_REQUIRED')
    return sha


def doctor(static=False, lock_name='lock.json'):
    data = load_lock(lock_name)
    if not static:
        for program in ('docker', 'git', 'openssl'):
            require(shutil.which(program), 'REQUIRED_TOOL_UNAVAILABLE')
        call(['docker', 'info'], timeout=20)
        call(['docker', 'compose', 'version'], timeout=20)
    return {'profile': data['profile'], 'sources': data['sources'], 'services': sorted(adapter.SERVICES),
            'images': data['images'], 'static_only': static, 'protected_acceptance': False,
            'scope': 'NATIVE_ORY_CP_DEVELOPMENT_AUTHORITY_CHAIN',
            'other_engine_capabilities': 'NOT_STARTED', 'cms_required': False}


def current(run_id, active=True):
    directory = run_dir(run_id)
    data = read(directory / 'state.json')
    require(data['run_id'] == run_id and data['project'] == 'dev01-' + run_id
            and data['namespace'] == NAMESPACE and data['uid'] == os.getuid()
            and data['environment'] == 'development', 'STATE_OWNER_MISMATCH')
    if active:
        require(os.environ.get('BAOBAB_ENVIRONMENT') == 'development', 'EXPLICIT_DEVELOPMENT_REQUIRED')
        require(time.time() < data['deadline'], 'LEASE_EXPIRED')
        lock_name=data.get('lock_file','lock.json')
        load_lock(lock_name)  # closed, reviewed lock selection; no arbitrary path
        require(data['lock_sha256'] == hashlib.sha256((BASE / lock_name).read_bytes()).hexdigest()
                and source_identity() == data['harness_sha'], 'SOURCE_DRIFT')
        watcher = data.get('watcher_pid')
        require(type(watcher) is int and watcher > 1, 'WATCHDOG_REQUIRED')
        cmdline = Path(f'/proc/{watcher}/cmdline').read_bytes().split(b'\x00')
        require(b'watch' in cmdline and run_id.encode() in cmdline, 'WATCHDOG_NOT_LIVE')
    return directory, data


def persist(directory, data, phase):
    data['phase'] = phase
    write(directory / 'state.json', data)


def tls(directory, state):
    folder = directory / 'tls'
    folder.mkdir(mode=0o755)
    commands = [
        ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=Baobab DEV-01 CA',
         '-addext', 'basicConstraints=critical,CA:TRUE',
         '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', str(directory / 'ca.key'), '-out', str(folder / 'ca.pem')],
        ['req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=baobab-dev.test',
         '-keyout', str(folder / 'edge.key'), '-out', str(directory / 'edge.csr')],
    ]
    (directory / 'edge.ext').write_text('subjectAltName=DNS:hydra.int03.test,DNS:kratos.baobab-dev.test,DNS:cp.baobab-dev.test,DNS:rp.baobab-dev.test,DNS:cms.baobab-dev.test,DNS:nabhold.baobab-dev.test,DNS:redis.baobab-dev.test,DNS:pulse.baobab-dev.test,DNS:subscriptions.baobab-dev.test\nextendedKeyUsage=serverAuth\nkeyUsage=critical,digitalSignature,keyEncipherment\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\nbasicConstraints=CA:FALSE\n')
    for command in commands:
        call(['openssl', *command], state=state)
    call(['openssl', 'x509', '-req', '-in', str(directory / 'edge.csr'), '-CA', str(folder / 'ca.pem'),
          '-CAkey', str(directory / 'ca.key'), '-CAcreateserial', '-days', '1', '-extfile', str(directory / 'edge.ext'),
          '-out', str(folder / 'edge.pem')], state=state)
    for path in (directory / 'ca.key', directory / 'edge.csr', directory / 'edge.ext', folder / 'ca.srl'):
        path.unlink(missing_ok=True)
    for path in folder.iterdir():
        path.chmod(0o644)  # enclosing private run directory is never shared


def prepare(lease=3600, lock_name='lock.json'):
    require(os.environ.get('BAOBAB_ENVIRONMENT') == 'development', 'EXPLICIT_DEVELOPMENT_REQUIRED')
    lock = load_lock(lock_name)
    require(type(lease) is int and 60 <= lease <= lock['max_lease_seconds'], 'LEASE_RANGE')
    doctor(lock_name=lock_name)
    run_id = secrets.token_hex(16)
    directory = run_dir(run_id)
    directory.mkdir(mode=0o700)
    data = {'run_id': run_id, 'project': 'dev01-' + run_id, 'namespace': NAMESPACE,
            'uid': os.getuid(), 'gid': os.getgid(), 'environment': 'development',
            'deadline': int(time.time()) + lease, 'lease_seconds': lease, 'harness_sha': source_identity(),
            'lock_sha256': hashlib.sha256((BASE / lock_name).read_bytes()).hexdigest(),
            'lock_file': lock_name,
            'sources': lock['sources'], 'runtime_images': lock['images'],
            'secrets': {k: secrets.token_hex(32) for k in ('cp_db', 'iam_db', 'admin', 'hook', 'introspection', 'verifier')},
            'images': {}, 'image_ids': {}, 'tests': False}
    # Durable recovery identity exists BEFORE a clone, build or Docker mutation.
    persist(directory, data, 'PREPARING')
    watcher = subprocess.Popen([sys.executable, '-B', str(BASE / 'dev.py'), 'watch', '--run-id', run_id],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    data['watcher_pid'] = watcher.pid
    persist(directory, data, 'PREPARING')
    try:
        source_root = directory / 'sources'
        source_root.mkdir(mode=0o700)
        for repo, sha in lock['sources'].items():
            target = source_root / repo
            call(['git', 'init', '-q', str(target)], state=data)
            call(['git', '-C', str(target), 'fetch', '--quiet', '--depth', '1',
                  'https://github.com/baobab-platform/' + repo + '.git', sha], timeout=180, state=data)
            call(['git', '-C', str(target), 'checkout', '--quiet', '--detach', 'FETCH_HEAD'], state=data)
            require(call(['git', '-C', str(target), 'rev-parse', 'HEAD']) == sha, 'SOURCE_CHECKOUT_MISMATCH')
        cp = source_root / 'baobab-cp'
        shared = source_root / 'shared'
        data['contract_hashes'] = {}
        for path in ('development/v1/enterprise-profiles.schema.json', 'development/v1/examples/nabhold-group.json',
                     'identity/v1/workload-registry.yaml'):
            require((cp / 'internal/contracts/shared' / path).read_bytes() ==
                    (shared / 'contracts' / path).read_bytes(), 'EMBEDDED_CONTRACT_DRIFT')
            data['contract_hashes'][path] = hashlib.sha256((shared / 'contracts' / path).read_bytes()).hexdigest()
        tls(directory, data)
        (directory / 'nginx.conf').write_text(adapter.EDGE)
        persist(directory, data, 'PREPARED')
        return run_id
    except BaseException:
        down(run_id)
        raise


def compose(directory, state, *args, timeout=180):
    path = directory / 'compose.json'
    require(hashlib.sha256(path.read_bytes()).hexdigest() == state['compose_sha256'], 'COMPOSITION_DRIFT')
    return call(['docker', 'compose', '-f', str(path), '-p', state['project'], *args], timeout=timeout, state=state)


NATIVE_FILES={'hydra.yml','kratos/kratos.yml','kratos/identity.schema.json','introspection.htpasswd'}

def verify_sources(directory, state):
    if state.get('phase') in {'RUNNING','TESTED'}:
        anchors=state.get('native_config_hashes',{})
        require(set(anchors)==NATIVE_FILES and all(hashlib.sha256((directory/path).read_bytes()).hexdigest()==digest for path,digest in anchors.items()),'NATIVE_CONFIGURATION_DRIFT')
    for repo, sha in state['sources'].items():
        source = directory / 'sources' / repo
        require(call(['git', '-C', str(source), 'rev-parse', 'HEAD']) == sha
                and not call(['git', '-C', str(source), 'status', '--porcelain']), 'DEPENDENCY_SOURCE_DRIFT')


def labels(state):
    return {'io.baobab.dev.namespace': NAMESPACE, 'io.baobab.dev.run': state['run_id'],
            'io.baobab.dev.deadline': str(state['deadline'])}


def up(run_id):
    directory, state = current(run_id)
    verify_sources(directory, state)
    require(state['phase'] == 'PREPARED', 'RECOVER_BEFORE_RETRY')
    lock = load_lock(state.get('lock_file', 'lock.json'))
    persist(directory, state, 'BUILDING')
    try:
        print('DEV03_PHASE=CP_IMAGE',flush=True)
        for name, repo, dockerfile in [('cp', 'baobab-cp', directory / 'sources/baobab-cp/Dockerfile.development')]:
            image = state['project'] + '-' + name
            check_dockerfile(dockerfile)
            state['images'][name] = image
            persist(directory, state, 'BUILDING')
            arguments = ['docker', 'build', '--tag', image, '--file', str(dockerfile)]
            for key, value in {**labels(state), 'org.opencontainers.image.revision': state['sources'][repo]}.items():
                arguments += ['--label', key + '=' + value]
            call([*arguments, str(directory / 'sources' / repo)], timeout=1800, state=state)
            state['image_ids'][name] = call(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'])
            require(DIGEST.fullmatch(state['image_ids'][name]), 'BUILT_IMAGE_DIGEST_REQUIRED')
            persist(directory, state, 'BUILDING')
        print('DEV03_PHASE=ORY_CONFIG',flush=True)
        adapter.configure(directory, state)
        state['native_config_hashes']={path:hashlib.sha256((directory/path).read_bytes()).hexdigest() for path in NATIVE_FILES}
        write(directory / 'compose.json', adapter.composition(state, directory, lock['images'], NAMESPACE))
        state['compose_sha256'] = hashlib.sha256((directory / 'compose.json').read_bytes()).hexdigest()
        persist(directory, state, 'STARTING')
        compose(directory, state, 'config', '--quiet')
        print('DEV03_PHASE=ORY_START',flush=True)
        compose(directory, state, 'up', '-d', '--wait', '--wait-timeout', '240',
                'hydra', 'kratos', 'cp-db', 'edge', 'probe', timeout=300)
        database = 'baobab_dev_' + run_id
        # Infrastructure creates/marks its fresh store only. All canonical
        # state and migrations are owned by the CP command below, never SQL.
        compose(directory, state, 'exec', '-T', 'cp-db', 'psql', '-U', 'baobab_dev', '-d', database,
                '-v', 'ON_ERROR_STOP=1', '-c', f"COMMENT ON DATABASE {database} IS 'baobab.disposable-development.v1'")
        # Native IAM reads require actual readiness, not a container-start flag.
        ready = False
        for attempt in range(90):
            try:
                status=json.loads(compose(directory,state,'exec','-T','probe','python','/native_probe.py','provider-ready',timeout=12))
                require(set(status)=={'hydra','kratos'} and all(type(value) is int and 0<=value<600 for value in status.values()),'READINESS_SHAPE')
                if all(value==200 for value in status.values()): ready=True;break
                if attempt % 15==0: print('DEV03_READINESS='+json.dumps(status,sort_keys=True),flush=True)
            except Refused:
                # A transient or malformed probe cannot advance readiness.
                pass
            time.sleep(2)
        require(ready, 'IAM_HEALTH_UNAVAILABLE')
        print('DEV03_PHASE=NATIVE_IDENTITIES',flush=True)
        compose(directory, state, 'exec', '-T', 'probe', 'python', '/native_probe.py', 'subjects')
        result = bootstrap(directory, state)
        write(directory / 'bootstrap.json', result)
        # Up never registers or activates a domain provider.
        compose(directory, state, 'up', '-d', 'cp')
        persist(directory, state, 'RUNNING')
    except BaseException:
        try:
            raw=compose(directory,state,'ps','--all','--format','json')
            values=json.loads(raw) if raw.startswith('[') else [json.loads(line) for line in raw.splitlines()]
            for item in values:
                name=item.get('Service');phase=item.get('State');code=item.get('ExitCode')
                if name in adapter.SERVICES and phase in {'running','exited','created','restarting','dead'} and type(code) is int:
                    print('DEV03_CONTAINER='+name+':'+phase+':'+str(code),flush=True)
            logs=compose(directory,state,'logs','--no-color','--tail','40','edge','hydra','kratos','hydra-migrate','kratos-migrate')
            markers=[]
            for text,code in (('read-only file system','READ_ONLY_FILESYSTEM'),('unknown flag','PROVIDER_COMMAND_REFUSED'),
                              ('additional propert','PROVIDER_CONFIG_PROPERTY_REFUSED'),('permission denied','RUNTIME_PERMISSION_DENIED'),
                              ('connection refused','DEPENDENCY_NOT_READY'),('does not validate','PROVIDER_CONFIG_REFUSED'),
                              ('error opening config','PROVIDER_CONFIG_UNREADABLE')):
                if text in logs.lower(): markers.append(code)
            paths=set(re.findall(r'\b(?:oauth2|serve|urls|secrets|strategies|ttl|session|identity|hashers|selfservice|courier)(?:\.[a-z_]{1,40}){0,5}',logs))
            print('DEV03_CONFIG_PATHS='+','.join(sorted(paths)),flush=True)
            print('DEV03_STARTUP_CLASSES='+','.join(markers or ['UNCLASSIFIED']),flush=True)
        except (Refused,OSError):
            print('DEV03_STARTUP_CLASSES=DIAGNOSTICS_UNAVAILABLE',flush=True)
        down(run_id)
        raise


def bootstrap(directory, state, check_fixtures=False):
    subjects = read(directory / 'subjects.json')
    require(set(subjects) == {'maker', 'checker'} and subjects['maker'] != subjects['checker'], 'IAM_SUBJECT_READBACK_REQUIRED')
    remaining = min(state['lease_seconds'], int(state['deadline'] - time.time()) - 15)
    # Freeze the narrower CP lease once; replay must use identical inputs.
    if 'bootstrap_lease' not in state:
        require(remaining >= 60, 'LEASE_EXPIRED')
        state['bootstrap_lease'] = remaining
        persist(directory, state, state['phase'])
    raw = compose(directory, state, 'run', '--rm', '--no-deps',
                  '-e', 'BAOBAB_DEV_BOOTSTRAP_ENABLED=true', '--entrypoint', '/development-bootstrap', 'cp',
                  '--run-id', state['run_id'], '--issuer', adapter.ISSUER,
                  '--maker-subject', subjects['maker'], '--checker-subject', subjects['checker'],
                  '--lease', str(state['bootstrap_lease']) + 's', *(['--external-api'] if state.get('external_api') else []), *(['--check-fixtures'] if check_fixtures else []))
    value = json.loads(raw, object_pairs_hook=unique)
    if check_fixtures:
        validate_fixture_report(value, state['run_id'])
        return value
    require(value['schema'] == 'baobab.development-bootstrap.v1' and value.get('fixture_version') == (3 if state.get('external_api') else 2) and value['run_id'] == state['run_id']
            and value['synthetic_only'] is True and value['protected_acceptance'] is False
            and value['maker_id'] != value['checker_id'] and len(value['enterprises']) == 5, 'CP_BOOTSTRAP_RESULT_INVALID')
    require(datetime.fromisoformat(value['expires_at'].replace('Z', '+00:00')).timestamp() <= state['deadline'],
            'CP_LEASE_EXCEEDS_RUN_DEADLINE')
    external = [e for e in value['enterprises'] if e['key'] == 'external-client']
    require(len(external) == 1 and not external[0].get('digital_estate_id'), 'EXTERNAL_CLIENT_ESTATE_FORBIDDEN')
    return value


def validate_fixture_report(value, run_id):
    require(set(value) == {'schema', 'run_id', 'synthetic_only', 'official_actor_verified',
                           'provider_permissions_granted', 'protected_acceptance', 'scope', 'observations'},
            'DEV02_REPORT_FIELDS_INVALID')
    expected = {
        'valid_scoped': 'ACTOR_NOT_VERIFIED', 'missing': 'NO_APPLICABLE_MANDATE',
        'stale': 'REVOKED_OR_EXPIRED', 'revoked': 'REVOKED_OR_EXPIRED',
        'wrong_market': 'NO_APPLICABLE_MANDATE', 'pending': 'NO_APPLICABLE_MANDATE',
        **{'boundary_wrong_' + field: 'NO_APPLICABLE_MANDATE'
           for field in ('role', 'activity', 'capability', 'tenant', 'organisation', 'market')},
    }
    inventory = [(enterprise, case, outcome) for enterprise in ('zuribeans', 'equator-estate')
                 for case, outcome in expected.items()]
    require(value.get('schema') == 'baobab.development-fixture-checks.v1'
            and value.get('run_id') == run_id and value.get('synthetic_only') is True
            and value.get('scope') == 'DEV02_NON_AUTHORISING_SCOPE_AND_LIFECYCLE'
            and all(value.get(key) is False for key in ('official_actor_verified',
                    'provider_permissions_granted', 'protected_acceptance')), 'DEV02_REPORT_INVALID')
    observations = value.get('observations', [])
    require(len(observations) == 24 and all(set(row) == {'enterprise', 'case', 'policy_outcome', 'passed'}
            and row.get('passed') is True for row in observations)
            and sorted((row.get('enterprise'), row.get('case'), row.get('policy_outcome')) for row in observations)
            == sorted(inventory), 'DEV02_INVENTORY_OR_OUTCOME_INVALID')


def test(run_id, health_attempts=45):
    directory, state = current(run_id)
    verify_sources(directory, state)
    require(state['phase'] in {'RUNNING', 'TESTED'}, 'RUNNING_PROFILE_REQUIRED')
    # Clear a former success before probing; failure cannot preserve old green.
    state['tests'] = False
    persist(directory, state, 'RUNNING')
    require(type(health_attempts) is int and 1 <= health_attempts <= 45, 'HEALTH_ATTEMPT_BOUND')
    for _ in range(health_attempts):
        try:
            compose(directory, state, 'exec', '-T', 'probe', 'python', '/native_probe.py', 'health', timeout=20)
            break
        except Refused:
            time.sleep(2)
    else:
        raise Refused('IAM_CP_HEALTH_FAILED')
    require(bootstrap(directory, state) == read(directory / 'bootstrap.json'), 'BOOTSTRAP_REPLAY_MISMATCH')
    for name in adapter.SERVICES - adapter.MIGRATIONS:
        container = compose(directory, state, 'ps', '-q', name)
        require(re.fullmatch(r'[0-9a-f]{12,64}', container), 'CONTAINER_NOT_RUNNING')
        actual = json.loads(call(['docker', 'inspect', container]))[0]
        require(not actual['HostConfig']['PortBindings'] and not actual['HostConfig']['Privileged'], 'UNSAFE_RUNTIME')
        require(actual['Config']['Labels'].get('io.baobab.dev.namespace') == NAMESPACE
                and actual['Config']['Labels'].get('io.baobab.dev.run') == run_id, 'RESOURCE_OWNER_MISMATCH')
        networks = actual['NetworkSettings']['Networks']
        require(len(networks) == 1, 'UNEXPECTED_NETWORK_ATTACHMENT')
        network = json.loads(call(['docker', 'network', 'inspect', next(iter(networks))]))[0]
        require(network['Internal'] is True, 'PUBLIC_NETWORK_FORBIDDEN')
        expected = state['image_ids'].get(name)
        if not expected:
            image = state['runtime_images']['postgres' if name.endswith('-db') else name]
            expected = call(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'])
        if expected:
            require(actual['Image'] == expected, 'RUNTIME_IMAGE_MISMATCH')
    fixture_checks = bootstrap(directory, state, check_fixtures=True)
    state['tests'] = True
    persist(directory, state, 'TESTED')
    return {'lifecycle_checks': 'PASS', 'domain_qualification': 'NOT_EXECUTED', 'fixture_checks': fixture_checks}


AUTHORITY_CASES = {'actual_signed_issuer_and_cp_context','wrong_sibling_tenant_denied','wrong_external_tenant_denied',
 'wrong_audience_denied','absent_capability_grant_denied','expired_issuer_token_denied','issuer_revocation_while_unexpired',
 'fresh_credential_after_revoke_succeeds','real_kratos_hydra_pkce_distinct_humans','same_principal_provenance_approval_denied',
 'same_principal_deactivation_approval_denied','cp_principal_deactivation_while_unexpired','cp_denial_independent_of_issuer_status','wrong_pkce_denied_by_issuer','wrong_state_denied_by_relying_party','authorization_code_replay_denied'}

def qualify(run_id):
    directory,state=current(run_id)
    verify_sources(directory,state)
    require(state['phase']=='TESTED','TESTED_PROFILE_REQUIRED')
    state['authority']=None
    persist(directory,state,'TESTED')
    compose(directory,state,'exec','-T','probe','python','/native_probe.py','authority',timeout=180)
    report=read(directory/'authority.json')
    require(set(report)=={'schema','checks','synthetic_only','canonical_provider_qualified','int03c_qualified','nab03_qualified','protected_acceptance'}
            and report['schema']=='infrastructure.dev03.authority-observed.v1'
            and set(report['checks'])==AUTHORITY_CASES and all(v is True for v in report['checks'].values())
            and report['synthetic_only'] is True and all(report[k] is False for k in
            ('canonical_provider_qualified','int03c_qualified','nab03_qualified','protected_acceptance')),'DEV03_REPORT_INVALID')
    state['authority']=report
    persist(directory,state,'TESTED')
    return report



def qualify_int03c(run_id):
    directory, state = current(run_id)
    verify_sources(directory, state)
    require(state['phase'] == 'TESTED' and not state.get('authority'), 'FRESH_TESTED_PROFILE_REQUIRED')
    # Invalidate persisted success before any subprocess/read. Preserve valid partial
    # observations on failure, but a prior PASS can never survive a failed retry.
    state['int03c'] = int03c_contract.fresh(run_id)
    persist(directory, state, 'TESTED')
    (directory / 'int03c-report.json').unlink(missing_ok=True)
    try:
        compose(directory, state, 'exec', '-T', 'probe', 'python', '/int03c_probe.py', timeout=180)
    finally:
        if (directory / 'int03c-report.json').exists():
            report = read(directory / 'int03c-report.json')
            int03c_contract.validate(report, run_id)
            state['int03c'] = report
            persist(directory, state, 'TESTED')
    report = state['int03c']
    require(all(row['result'] == 'PASS' for name, row in report['cases'].items()
                if name != 'complete-teardown'), 'DEV04_RUNTIME_CASES_INCOMPLETE')
    require(report['cases']['complete-teardown']['reason'] == 'TEARDOWN_PENDING', 'DEV04_PROVIDER_TEARDOWN_INCOMPLETE')
    return report


def resources(run_id=None):
    filters = ['--filter', 'label=io.baobab.dev.namespace=' + NAMESPACE]
    if run_id:
        filters += ['--filter', 'label=io.baobab.dev.run=' + run_id]
    result = []
    for kind, command in [('container', ['docker', 'ps', '-aq']), ('network', ['docker', 'network', 'ls', '-q']),
                          ('volume', ['docker', 'volume', 'ls', '-q']), ('image', ['docker', 'image', 'ls', '-q', '--no-trunc'])]:
        for resource in set(call([*command, *filters]).splitlines()):
            actual = json.loads(call(['docker', kind, 'inspect', resource]))[0]
            found = (actual.get('Config') or {}).get('Labels') or actual.get('Labels') or {}
            require(found.get('io.baobab.dev.namespace') == NAMESPACE
                    and NONCE.fullmatch(found.get('io.baobab.dev.run', ''))
                    and (run_id is None or found['io.baobab.dev.run'] == run_id), 'RESOURCE_OWNER_MISMATCH')
            result.append((kind, resource, found))
    return result


def down(run_id):
    directory = run_dir(run_id)
    state = read(directory / 'state.json') if (directory / 'state.json').exists() else None
    # Independent of Compose, source availability, DB credentials or expiry.
    # Thus a crash during up or a lost envfile cannot destroy the cleanup handle.
    for kind, resource, _ in resources(run_id):
        call(['docker', kind, 'rm', *(['-f'] if kind == 'container' else []), resource], timeout=120)
    require(not resources(run_id), 'TEARDOWN_SURVIVORS')
    if state:
        qualification = state.get('int03c')
        if qualification:
            int03c_contract.validate(qualification, run_id)
        report = {'schema': 'infrastructure.dev01.lifecycle.observed.v1', 'run_id': run_id,
                  'harness_sha': state['harness_sha'], 'source_pins': state['sources'],
                  'image_ids': state['image_ids'], 'runtime_images': state.get('runtime_images', {}),
                  'lock_sha256': state['lock_sha256'], 'native_config_hashes':state.get('native_config_hashes',{}),
                  'evidence_class': 'REAL_COMPONENT_SYNTHETIC_DATA' if state['tests'] else 'SOURCE',
                  'lifecycle_passed': state['tests'], 'teardown_verified': True,
                  'domain_qualification': 'DEV03_NATIVE_CP_AUTHORITY_ONLY' if state.get('authority') else 'NOT_EXECUTED',
                  'external_oci_manifest_digest':state.get('external_oci_manifest_digest'), 'external':state.get('external'), 'external_lock_sha256':state.get('external_lock_sha256'), 'external_runtime_identity_verified':state.get('external_runtime_identity_verified',False), 'cms_oci_manifest_digest':state.get('cms_oci_manifest_digest'), 'cms_config_hashes':state.get('cms_config_hashes'), 'cms_runtime_identity_verified':state.get('cms_runtime_identity_verified',False), 'cms':state.get('cms'), 'cms_lock_sha256':state.get('cms_lock_sha256'), 'authority':state.get('authority'), 'int03c': qualification, 'int03c_qualified': False,
                  'contract_hashes': state.get('contract_hashes', {}),
                  'nab03_qualified': False, 'protected_acceptance': False, 'production_authorized': False}
        folder = EVIDENCE / ('dev01-' + run_id)
        private_directory(folder)
        pending = folder / '.pending'
        private_directory(pending)
        # Phase 1: fsync a sanitized recovery candidate BEFORE destroying the
        # private run. It is not uploaded or authoritative; no final-case PASS.
        write(pending / 'receipt.json', report)
    else:
        folder = EVIDENCE / ('dev01-' + run_id)
    if directory.exists():
        shutil.rmtree(directory)
    if (folder / '.pending/receipt.json').exists():
        publish_receipt(folder, run_id)


def publish_receipt(folder, run_id):
    """Phase 2, replayable after process/host interruption without private state.

    A candidate lives outside the run's secret tree. Recovery re-observes host
    absence, completes only the host-owned assertions, rewrites/hash-checks the
    final bytes and atomically renames them into custody. Nothing under .pending
    is published by Actions. A write/rename failure keeps the recovery candidate.
    """
    private_directory(folder)
    pending = folder / '.pending'
    private_directory(pending)
    report = read(pending / 'receipt.json')
    require(report.get('run_id') == run_id and report.get('schema') ==
            'infrastructure.dev01.lifecycle.observed.v1', 'PENDING_RECEIPT_IDENTITY_INVALID')
    require(not run_dir(run_id).exists() and not resources(run_id), 'TEARDOWN_SURVIVORS')
    qualification = report.get('int03c')
    if qualification:
        int03c_contract.validate(qualification, run_id)
        row = qualification['cases']['complete-teardown']
        for key in ('accepting_runtime_absent', 'owned_resources_absent', 'private_state_absent'):
            row['assertions'][key] = True
        if row['reason'] == 'TEARDOWN_PENDING' and all(row['assertions'].values()):
            row.update(result='PASS', reason='OBSERVED')
        int03c_contract.validate(qualification, run_id)
        report['int03c_qualified'] = report['lifecycle_passed'] and all(
            item['result'] == 'PASS' for item in qualification['cases'].values())
        report['domain_qualification'] = 'DEV04_INT03C_DEVELOPMENT_ONLY'
    if report.get('external'):
        import external_contract
        external = external_contract.validate(report['external'], run_id)
        external['component_checks'].update(private_state_absent=True, owned_resources_absent=True)
        if external['cases']['teardown']['reason']=='TEARDOWN_PENDING' and external['component_checks'].get('native_clients_deleted') and external['component_checks'].get('native_tokens_inactive'):
            external['cases']['teardown']={'result':'PASS','reason':'OBSERVED'}
        external_contract.validate(external,run_id)
        report['domain_qualification']='DEV06_EXTERNAL_COMPONENT_ONLY_INT07_UNQUALIFIED'
    if report.get('cms'):
        import cms_contract
        cms = cms_contract.validate(report['cms'], run_id)
        cms['component_checks'].update(private_state_absent=True, owned_resources_absent=True)
        if cms['cases']['teardown']['reason'] == 'TEARDOWN_PENDING' and cms['component_checks'].get('native_clients_deleted') and cms['component_checks'].get('native_tokens_inactive'):
            cms['cases']['teardown'] = {'result':'PASS','reason':'OBSERVED'}
        cms['nab03_qualified'] = (all(row['result']=='PASS' for row in cms['cases'].values())
            and cms['component_checks'].get('provider_declared_partial') is False
            and all(cms['component_checks'].get(key) is True for key in cms_contract.BOUND_COMPONENTS))
        cms_contract.validate(cms, run_id)
        report['nab03_qualified'] = cms['nab03_qualified']
        report['domain_qualification'] = 'DEV05_NATIVE_CMS_DEVELOPMENT_ONLY'
    write(pending / 'receipt.json', report)
    write(pending / 'receipt.sha256.json',
          {'sha256': hashlib.sha256((pending / 'receipt.json').read_bytes()).hexdigest()})
    os.rename(pending, folder / 'completed')
    handle = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def recover(all_runs=False):
    private_directory(STATE)
    ids = {path.name for path in STATE.iterdir() if NONCE.fullmatch(path.name)}
    pending_ids = {path.name[6:] for path in EVIDENCE.glob('dev01-*')
                   if NONCE.fullmatch(path.name[6:]) and (path / '.pending/receipt.json').exists()}
    ids.update(pending_ids)
    owned = resources()
    ids.update(labels['io.baobab.dev.run'] for _, _, labels in owned)
    for run_id in sorted(ids):
        deadlines = [int(v['io.baobab.dev.deadline']) for _, _, v in owned if v['io.baobab.dev.run'] == run_id]
        state_path = run_dir(run_id) / 'state.json'
        if state_path.exists():
            deadlines.append(read(state_path)['deadline'])
        if all_runs or (run_id in pending_ids and not state_path.exists()) or (deadlines and min(deadlines) <= time.time()):
            with guarded(run_id):
                down(run_id)


def watch(run_id):
    while True:
        try:
            directory, state = current(run_id, active=False)
        except (OSError, Refused):
            return
        if time.time() >= state['deadline']:
            try:
                with guarded(run_id, nonblocking=True):
                    down(run_id)
                    return
            except (BlockingIOError, Refused, OSError):
                pass  # retain durable state and retry; host restart uses recover
        time.sleep(1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['doctor', 'preflight', 'plan', 'prepare', 'up', 'test',
                                         'evidence', 'down', 'recover', 'run', 'watch', 'qualify', 'qualify-int03c', 'run-int03c', 'run-cms', 'run-external'])
    parser.add_argument('--run-id')
    parser.add_argument('--lease-seconds', type=int, default=3600)
    parser.add_argument('--static', action='store_true')
    parser.add_argument('--all', action='store_true', help='recover every run owned by this checkout/user')
    args = parser.parse_args(argv)
    try:
        require(not args.static or args.action in {'doctor', 'preflight', 'plan'}, 'STATIC_CANNOT_MUTATE')
        require(not args.all or args.action == 'recover', 'ALL_REQUIRES_RECOVERY')
        if args.action in {'doctor', 'preflight', 'plan'}:
            print(json.dumps(doctor(static=args.static), sort_keys=True))
        elif args.action == 'prepare':
            print(prepare(args.lease_seconds))
        elif args.action == 'recover':
            recover(args.all)
        elif args.action == 'watch':
            watch(args.run_id)
        elif args.action == 'run-external':
            import ci_external
            ci_external.main()
        elif args.action == 'run-cms':
            import cms_vertical
            run_id = cms_vertical.prepare()
            try:
                with guarded(run_id):
                    cms_vertical.up(run_id)
                    cms_vertical.qualify(run_id)
            finally:
                with guarded(run_id): down(run_id)
            print('DEV05_COMPLETED_RECEIPT ' + run_id)
        elif args.action in {'run', 'run-int03c'}:
            run_id = prepare(args.lease_seconds)
            try:
                with guarded(run_id):
                    up(run_id)
                    test(run_id)
                    if args.action == 'run-int03c':
                        qualify_int03c(run_id)
                    else:
                        qualify(run_id)
            finally:
                with guarded(run_id):
                    down(run_id)
            print('DEV01_LIFECYCLE_COMPLETE ' + run_id)
        else:
            run_dir(args.run_id)
            with guarded(args.run_id):
                if args.action == 'up':
                    up(args.run_id)
                elif args.action == 'qualify':
                    print(json.dumps(qualify(args.run_id),sort_keys=True))
                elif args.action == 'qualify-int03c':
                    print(json.dumps(qualify_int03c(args.run_id), sort_keys=True))
                elif args.action == 'test':
                    print(json.dumps(test(args.run_id)))
                elif args.action == 'down':
                    down(args.run_id)
                else:
                    receipt = EVIDENCE / ('dev01-' + args.run_id) / 'completed/receipt.json'
                    digest = read(receipt.with_name('receipt.sha256.json'))
                    require(hashlib.sha256(receipt.read_bytes()).hexdigest() == digest['sha256'], 'EVIDENCE_HASH_MISMATCH')
                    print(json.dumps(read(receipt), sort_keys=True))
        return 0
    except (Refused, OSError, ValueError, KeyError, TypeError) as error:
        print('DEV01_BLOCKED ' + (str(error) if isinstance(error, Refused) else 'INVALID_OR_UNAVAILABLE_STATE'), file=sys.stderr)
        return 2


if __name__ == '__main__':
    if 'watch' not in sys.argv:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    raise SystemExit(main())
