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


def call(args, *, timeout=120, stdin=None, state=None):
    if state is not None:
        timeout = min(timeout, state['deadline'] - time.time())
        require(timeout > 0, 'LEASE_EXPIRED')
    try:
        result = subprocess.run(args, input=stdin, text=True, capture_output=True,
                                check=False, timeout=timeout)
        if result.returncode != 0:
            # Closed diagnostics only: never print command arguments, env or logs.
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
            raise Refused(classification)
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError) as error:
        raise Refused('COMMAND_UNAVAILABLE_OR_TIMED_OUT') from error


def load_lock():
    data = json.loads((BASE / 'lock.json').read_text(), object_pairs_hook=unique)
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


def doctor(static=False):
    data = load_lock()
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
        require(data['lock_sha256'] == hashlib.sha256((BASE / 'lock.json').read_bytes()).hexdigest()
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
         '-addext', 'basicConstraints=critical,CA:TRUE', '-keyout', str(directory / 'ca.key'), '-out', str(folder / 'ca.pem')],
        ['req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=baobab-dev.test',
         '-keyout', str(folder / 'edge.key'), '-out', str(directory / 'edge.csr')],
    ]
    (directory / 'edge.ext').write_text('subjectAltName=DNS:hydra.int03.test,DNS:kratos.baobab-dev.test,DNS:cp.baobab-dev.test,DNS:rp.baobab-dev.test\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n')
    for command in commands:
        call(['openssl', *command], state=state)
    call(['openssl', 'x509', '-req', '-in', str(directory / 'edge.csr'), '-CA', str(folder / 'ca.pem'),
          '-CAkey', str(directory / 'ca.key'), '-CAcreateserial', '-days', '1', '-extfile', str(directory / 'edge.ext'),
          '-out', str(folder / 'edge.pem')], state=state)
    for path in (directory / 'ca.key', directory / 'edge.csr', directory / 'edge.ext', folder / 'ca.srl'):
        path.unlink(missing_ok=True)
    for path in folder.iterdir():
        path.chmod(0o644)  # enclosing private run directory is never shared


def prepare(lease=3600):
    require(os.environ.get('BAOBAB_ENVIRONMENT') == 'development', 'EXPLICIT_DEVELOPMENT_REQUIRED')
    lock = load_lock()
    require(type(lease) is int and 60 <= lease <= lock['max_lease_seconds'], 'LEASE_RANGE')
    doctor()
    run_id = secrets.token_hex(16)
    directory = run_dir(run_id)
    directory.mkdir(mode=0o700)
    data = {'run_id': run_id, 'project': 'dev01-' + run_id, 'namespace': NAMESPACE,
            'uid': os.getuid(), 'gid': os.getgid(), 'environment': 'development',
            'deadline': int(time.time()) + lease, 'lease_seconds': lease, 'harness_sha': source_identity(),
            'lock_sha256': hashlib.sha256((BASE / 'lock.json').read_bytes()).hexdigest(),
            'sources': lock['sources'], 'runtime_images': lock['images'],
            'secrets': {k: secrets.token_hex(32) for k in ('cp_db', 'iam_db', 'admin', 'hook', 'introspection')},
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
        for path in ('development/v1/enterprise-profiles.schema.json', 'development/v1/examples/nabhold-group.json',
                     'identity/v1/workload-registry.yaml'):
            require((cp / 'internal/contracts/shared' / path).read_bytes() ==
                    (shared / 'contracts' / path).read_bytes(), 'EMBEDDED_CONTRACT_DRIFT')
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


def verify_sources(directory, state):
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
    lock = load_lock()
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
        for _ in range(90):
            try:
                compose(directory, state, 'exec', '-T', 'probe', 'python', '-c',
                        "import ssl,urllib.request; c=ssl.create_default_context(cafile='/tls/ca.pem'); "
                        "r=urllib.request.urlopen('https://hydra.int03.test/.well-known/openid-configuration',context=c,timeout=3); "
                        "assert r.status==200; "
                        "r=urllib.request.urlopen('https://kratos.baobab-dev.test/health/ready',context=c,timeout=3); "
                        "assert r.status==200", timeout=8)
                ready = True
                break
            except Refused:
                time.sleep(2)
        require(ready, 'IAM_HEALTH_UNAVAILABLE')
        print('DEV03_PHASE=NATIVE_IDENTITIES',flush=True)
        compose(directory, state, 'exec', '-T', 'probe', 'python', '/probe.py', 'subjects')
        result = bootstrap(directory, state)
        write(directory / 'bootstrap.json', result)
        # Up never registers or activates a domain provider.
        compose(directory, state, 'up', '-d', 'cp')
        persist(directory, state, 'RUNNING')
    except BaseException:
        try:
            logs=compose(directory,state,'logs','--no-color','--tail','40','edge','hydra','kratos','hydra-migrate','kratos-migrate')
            markers=[]
            for text,code in (('read-only file system','READ_ONLY_FILESYSTEM'),('unknown flag','PROVIDER_COMMAND_REFUSED'),
                              ('additional propert','PROVIDER_CONFIG_PROPERTY_REFUSED'),('permission denied','RUNTIME_PERMISSION_DENIED'),
                              ('connection refused','DEPENDENCY_NOT_READY'),('does not validate','PROVIDER_CONFIG_REFUSED'),
                              ('error opening config','PROVIDER_CONFIG_UNREADABLE')):
                if text in logs.lower(): markers.append(code)
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
                  '--lease', str(state['bootstrap_lease']) + 's', *(['--check-fixtures'] if check_fixtures else []))
    value = json.loads(raw, object_pairs_hook=unique)
    if check_fixtures:
        validate_fixture_report(value, state['run_id'])
        return value
    require(value['schema'] == 'baobab.development-bootstrap.v1' and value.get('fixture_version') == 2 and value['run_id'] == state['run_id']
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


def test(run_id):
    directory, state = current(run_id)
    verify_sources(directory, state)
    require(state['phase'] in {'RUNNING', 'TESTED'}, 'RUNNING_PROFILE_REQUIRED')
    # Clear a former success before probing; failure cannot preserve old green.
    state['tests'] = False
    persist(directory, state, 'RUNNING')
    for _ in range(45):
        try:
            compose(directory, state, 'exec', '-T', 'probe', 'python', '/probe.py', 'health', timeout=20)
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
    compose(directory,state,'exec','-T','probe','python','/probe.py','authority',timeout=180)
    report=read(directory/'authority.json')
    require(set(report)=={'schema','checks','synthetic_only','canonical_provider_qualified','int03c_qualified','nab03_qualified','protected_acceptance'}
            and report['schema']=='infrastructure.dev03.authority-observed.v1'
            and set(report['checks'])==AUTHORITY_CASES and all(v is True for v in report['checks'].values())
            and report['synthetic_only'] is True and all(report[k] is False for k in
            ('canonical_provider_qualified','int03c_qualified','nab03_qualified','protected_acceptance')),'DEV03_REPORT_INVALID')
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
        report = {'schema': 'infrastructure.dev01.lifecycle.observed.v1', 'run_id': run_id,
                  'harness_sha': state['harness_sha'], 'source_pins': state['sources'],
                  'image_ids': state['image_ids'], 'runtime_images': state.get('runtime_images', {}),
                  'lock_sha256': state['lock_sha256'],
                  'evidence_class': 'REAL_COMPONENT_SYNTHETIC_DATA' if state['tests'] else 'SOURCE',
                  'lifecycle_passed': state['tests'], 'teardown_verified': True,
                  'domain_qualification': 'NOT_EXECUTED', 'int03c_qualified': False,
                  'nab03_qualified': False, 'protected_acceptance': False, 'production_authorized': False}
        folder = EVIDENCE / ('dev01-' + run_id)
        private_directory(folder)
        pending = folder / '.pending'
        if pending.exists():
            private_directory(pending)
            shutil.rmtree(pending)
        private_directory(pending)
        write(pending / 'receipt.json', report)
        write(pending / 'receipt.sha256.json',
              {'sha256': hashlib.sha256((pending / 'receipt.json').read_bytes()).hexdigest()})
        os.rename(pending, folder / 'completed')
    if directory.exists():
        shutil.rmtree(directory)


def recover(all_runs=False):
    private_directory(STATE)
    ids = {path.name for path in STATE.iterdir() if NONCE.fullmatch(path.name)}
    owned = resources()
    ids.update(labels['io.baobab.dev.run'] for _, _, labels in owned)
    for run_id in sorted(ids):
        deadlines = [int(v['io.baobab.dev.deadline']) for _, _, v in owned if v['io.baobab.dev.run'] == run_id]
        state_path = run_dir(run_id) / 'state.json'
        if state_path.exists():
            deadlines.append(read(state_path)['deadline'])
        if all_runs or (deadlines and min(deadlines) <= time.time()):
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
                                         'evidence', 'down', 'recover', 'run', 'watch', 'qualify'])
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
        elif args.action == 'run':
            run_id = prepare(args.lease_seconds)
            try:
                with guarded(run_id):
                    up(run_id)
                    test(run_id)
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
