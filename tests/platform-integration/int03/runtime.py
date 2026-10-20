"""Private INT-03 overlay of the unchanged, separately requalified INT-02 lab.

All product services are real. Only records/identities are disposable fixtures.
This module never approves protected C4, full INT-03, staging or a release.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

BASE = Path(__file__).resolve().parent
PREVIOUS = BASE.parent / 'int02'
sys.path.insert(0, str(PREVIOUS))
spec = importlib.util.spec_from_file_location('int03_prerequisite', PREVIOUS / 'orchestrate.py')
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)
engine.SESSION = engine.STATE / 'int03-session.json'
# The reused qualifier hashes this separately reviewed prerequisite manifest;
# never pair rewritten pins with the frozen INT-02 manifest's digest.
engine.LOCK = BASE / 'prerequisite-lock.json'
base_compose = engine.compose


def compose_arguments(p, envfile):
    return ['docker', 'compose', '--env-file', str(envfile),
        '-f', str(PREVIOUS / 'compose.yaml'), '-f', str(BASE / 'compose.yaml'),
        '-p', p['project']]


def compose(p, envfile, *args, capture=False, stdin=None, timeout=600, command_env=None):
    """Preserve bounded Compose operation identity without leaking stderr.

    The INT-02 runner wraps its Compose errors. This overlay uses a second
    Compose file and must retain that fail-closed diagnostic contract. Only
    fixed operation/target names and explicitly allowlisted readiness codes
    may leave this layer; arbitrary subprocess errors stay private.
    """
    try:
        return engine.execute([*compose_arguments(p, envfile), *args], capture=capture,
                              input_text=stdin, timeout=timeout, env=command_env)
    except engine.Blocked as cause:
        operation = args[0] if args and args[0] in {'up', 'exec', 'wait', 'build', 'config', 'down'} else 'unknown'
        target = (args[2] if len(args) > 2 and args[0] == 'exec' and args[1] == '-T'
                  and args[2] in {'keycloak', 'probe', 'cp-db'} else 'service')
        # The inherited INT-02 execute() already removes raw command output.
        # Forward only a recognized closed IAM readiness token, not cause text.
        match = re.search(r'\bstep=iam_readiness discovery=(unavailable|tls_unverified|issuer_mismatch|[1-5][0-9]{2})\b',
                          str(cause))
        diagnostic = '; IAM diagnostics: step=iam_readiness discovery=' + match[1] if match else ''
        raise engine.Blocked(f'Compose {operation}/{target} failed' + diagnostic) from cause


CONSUMER_FAILURES = frozenset({'ENTRY', 'CONFIG', 'CA_TRUST', 'BROWSER_DISCOVERY',
                               'CHILD_LAUNCH', 'RECEIPT_UNAVAILABLE', 'CHILD_NONZERO'})


def consumer_failure_class(raw):
    """Parse only our own complete, fixed-code stderr lines; discard all else."""
    if type(raw) is not str:
        return 'UNKNOWN'
    found = []
    for line in raw.splitlines()[-100:]:
        match = re.fullmatch(r'INT03_CONSUMER_FAILURE=([A-Z_]{1,32})', line)
        if match and match[1] in CONSUMER_FAILURES:
            found.append(match[1])
    # A missing receipt is more diagnostic than the child process exit code.
    if 'RECEIPT_UNAVAILABLE' in found:
        return 'RECEIPT_UNAVAILABLE'
    return found[-1] if found else 'UNKNOWN'


def consume(p, envfile):
    # Keep the actual nonzero process result and sanitized receipt separate.
    # Browser stderr/stdout, callback codes and Node errors are never exported.
    result = subprocess.run([*compose_arguments(p, envfile), 'run', '--rm', '--no-deps',
                             'nabhold', 'test'], capture_output=True, text=True,
                            timeout=400, check=False)
    must(len(result.stdout.encode()) <= 16384, 'Consumer receipt exceeds bound')
    return result.returncode, result.stdout, consumer_failure_class(result.stderr)


engine.compose = compose
must = engine.must
original_build_class = engine.build_failure_class


def build_class(output):
    for marker, code in [('ERR_PNPM_FETCH_403', 'PACKAGE_READ_FORBIDDEN'),
                         ('ERR_PNPM_FETCH_401', 'PACKAGE_READ_UNAUTHORIZED'),
                         ('ERR_PNPM_FETCH_404', 'PACKAGE_NOT_VISIBLE'),
                         ('ERR_PNPM_OUTDATED_LOCKFILE', 'DEPENDENCY_LOCK'),
                         ('ERR_PNPM_BAD_PM_VERSION', 'PACKAGE_MANAGER_VERSION'),
                         ('not a git repository', 'SOURCE_METADATA_MISSING'),
                         ('detected dubious ownership', 'SOURCE_OWNER_REFUSED'),
                         ('corepack: not found', 'PACKAGE_MANAGER_MISSING'),
                         ('Cannot find matching keyid', 'PACKAGE_MANAGER_SIGNATURE')]:
        if marker in output:
            return code
    known = original_build_class(output)
    if known != 'OTHER':
        return known
    # The last failing BuildKit instruction, mapped to a closed vocabulary.
    # Never expose its command text or registry responses to a receipt/log.
    failures = [line for line in output.splitlines() if 'ERROR: process' in line]
    failed = failures[-1] if failures else ''
    for marker, code in [('pnpm install', 'PACKAGE_INSTALL_FAILED'),
                         ('corepack prepare', 'PACKAGE_MANAGER_PREPARE_FAILED'),
                         ('apt-get', 'SYSTEM_PACKAGES_FAILED'),
                         ('git diff', 'SOURCE_VERIFICATION_FAILED')]:
        if marker in failed:
            return code
    return 'OTHER'


engine.build_failure_class = build_class


def load():
    value = json.loads((BASE / 'lock.json').read_text())
    must(set(value) == {'schema', 'profile', 'sources', 'redis_image',
         'nabhold_base_image', 'synthetic_only', 'full_int03_acceptance'} and
         value['schema'] == 'infrastructure.int03.identity.v1' and
         value['profile'] == 'keycloak-identity-smoke' and
         value['synthetic_only'] is True and value['full_int03_acceptance'] is False,
         'Invalid identity-only source boundary')
    must(set(value['sources']) == {'baobab-iam', 'baobab-cp', 'shared', 'nabhold'} and
         all(engine.SHA40.fullmatch(v) for v in value['sources'].values()), 'Unpinned INT-03 sources')
    must(all(re.fullmatch(r'[a-z0-9][a-z0-9./:_-]*@sha256:[0-9a-f]{64}', value[k])
         for k in ('redis_image', 'nabhold_base_image')), 'Unpinned INT-03 images')
    must(not any(os.environ.get(k) for k in ('INT02_CANDIDATE_REPOSITORY', 'INT02_CANDIDATE_SHA')),
         'INT-03 does not permit unreviewed candidate overrides')
    must(not re.search(r'(?m)^\s+ports\s*:', (BASE / 'compose.yaml').read_text()), 'No host ports')
    must('FROM ' + value['nabhold_base_image'] in (BASE / 'nabhold.Dockerfile').read_text().splitlines(),
         'Nabhold builder differs from reviewed base image')
    prerequisite = engine.load()
    must(all(prerequisite['sources'][k] == v for k, v in value['sources'].items() if k != 'nabhold'),
         'Identity and prerequisite source locks disagree')
    return value, prerequisite


def tls(directory):
    """Separate edge/Redis leaf keys; destroy the signer before service launch."""
    directory.mkdir(mode=0o755)
    signer = directory.parent / 'int03-ca.key'
    ca = directory / 'ca.pem'
    try:
        engine.execute(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
            '-subj', '/CN=Disposable INT03 CA', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign', '-keyout', str(signer), '-out', str(ca)], timeout=60)
        for name, hosts in (('edge', ['iam.int02.test', 'cp.int02.test', 'human.int02.test',
                                    'pulse.int02.test', 'nabhold.int03.test']),
                            ('redis', ['redis.int03.test'])):
            leaf = directory if name == 'edge' else directory.parent / 'redis-tls'
            leaf.mkdir(mode=0o700, exist_ok=True)
            key, csr, ext = leaf / (name + '.key'), directory.parent / (name + '.csr'), directory.parent / (name + '.ext')
            engine.execute(['openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=' + hosts[0],
                            '-keyout', str(key), '-out', str(csr)], timeout=60)
            os.chmod(key, 0o600)
            ext.write_text('subjectAltName=' + ','.join('DNS:' + h for h in hosts) +
                           '\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n')
            engine.execute(['openssl', 'x509', '-req', '-in', str(csr), '-CA', str(ca), '-CAkey', str(signer),
                '-CAserial', str(directory.parent / 'int03-ca.srl'), '-CAcreateserial', '-days', '1',
                '-extfile', str(ext), '-out', str(leaf / (name + '.pem'))], timeout=60)
        (directory.parent / 'redis-tls' / 'ca.pem').write_bytes(ca.read_bytes())
    finally:
        for path in [signer, directory.parent / 'int03-ca.srl', *directory.parent.glob('*.csr'), *directory.parent.glob('*.ext')]:
            path.unlink(missing_ok=True)


engine.throwaway_tls = tls


def materialise(value, prerequisite, token):
    must(os.getuid() != 0, 'Run the connected profile as the non-root laboratory user')
    must(type(token) is str and 16 <= len(token) <= 4096 and
         not re.search(r'[\x00-\x20\x7f]', token), 'Package-read credential unavailable')
    engine.materialise(prerequisite)
    p, directory, envfile = engine.current()
    checkout = directory / 'nabhold'
    engine.execute(['git', 'clone', '--quiet', '--no-checkout', '--',
                    'https://github.com/baobab-platform/nabhold.git', str(checkout)], timeout=300)
    engine.execute(['git', '-C', str(checkout), 'checkout', '--quiet', '--detach', value['sources']['nabhold']], timeout=60)
    verify_checkout(checkout, value['sources']['nabhold'])
    prepare_templates(checkout, directory / 'tracked-templates')
    # This path is never mounted into a service as a dedicated secret, and is
    # blanked immediately after BuildKit consumes it. The run directory is
    # private; none of it is an evidence artifact.
    engine.private(directory / 'npm-token', token)
    extra = {
        'INT03_RUNTIME_HOST': engine.host_path(directory), 'INT03_RUNTIME_PATH': str(directory),
        'INT03_UID': str(os.getuid()), 'INT03_GID': str(os.getgid()),
        'INT03_NABHOLD_SOURCE': str(checkout), 'INT03_NABHOLD_DOCKERFILE': str(BASE / 'nabhold.Dockerfile'),
        'INT03_TRACKED_TEMPLATES': str(directory / 'tracked-templates'),
        'INT03_BASE_IMAGE': value['nabhold_base_image'], 'INT03_REDIS_IMAGE': value['redis_image'],
        'INT03_NABHOLD_IMAGE': 'l4-nabhold-' + p['project'],
        'INT03_TOKEN_FILE': str(directory / 'npm-token'), 'INT03_LAB_SOURCE': engine.host_path(BASE),
    }
    text = envfile.read_text()
    text = re.sub(r'(?m)^L4_EDGE_CONFIG=.*$', 'L4_EDGE_CONFIG=' + engine.host_path(BASE / 'edge.conf'), text)
    replace_private(envfile, text + ''.join(k + '=' + v + '\n' for k, v in extra.items()))
    p['sources']['nabhold'] = value['sources']['nabhold']
    # Unlike the frozen baseline field, this is the independently observed
    # clean integration checkout actually executing this runner.
    sha = harness_sha()
    must(engine.SHA40.fullmatch(sha), 'Harness revision unavailable')
    require_clean_harness()
    p['sources']['infrastructure'] = sha
    replace_private(engine.SESSION, json.dumps(p) + '\n')



def prepare_templates(checkout, destination):
    # Product Docker ignore rules exclude .env*. Preserve only the two public,
    # committed examples for the image's full Git worktree verification. No
    # operator dotenv, generated handoff or build credential is copied here.
    import handoff
    destination.mkdir(mode=0o700)
    for name in ('.env.example', '.env.integration.example'):
        engine.private(destination / name, handoff.read_file(checkout / name, private=False))


def replace_private(path, content):
    """Publish recovery handles atomically; preserve the prior version on failure."""
    pending = path.with_name(path.name + '.pending-' + secrets.token_hex(8))
    try:
        engine.private(pending, content)
        with pending.open('rb') as handle:
            os.fsync(handle.fileno())
        os.replace(pending, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        pending.unlink(missing_ok=True)


def require_clean_harness():
    git = ['git', '-c', 'safe.directory=' + str(engine.ROOT), '-C', str(engine.ROOT)]
    status = engine.execute([*git, 'status', '--porcelain', '--untracked-files=normal'], capture=True).rstrip()
    if status:
        # Emit only public HEAD-tracked paths or closed generated categories;
        # never arbitrary untracked names or private filenames.
        tracked = set(engine.execute([*git, 'ls-tree', '-r', '--name-only', 'HEAD'], capture=True).splitlines())
        for line in status.splitlines():
            path = line[3:]
            if path in tracked and re.fullmatch(r'[A-Za-z0-9_./-]{1,200}', path):
                print('INT-03 dirty tracked source: ' + path, flush=True)
            else:
                category = ('PYTHON_BYTECODE' if '__pycache__' in path else
                            'DEVCONTAINER_GENERATED' if path.startswith('.devcontainer/') else
                            'DEPENDENCY_INSTALL' if 'node_modules' in path else 'UNTRACKED_SOURCE')
                print('INT-03 dirty category: ' + category, flush=True)
    must(not status, 'Integration source must be clean')


def harness_sha():
    # Actions' bind-mounted checkout may belong to a different host UID.
    # Trust only this exact reviewed workspace for these read-only Git calls;
    # never disable safe.directory globally or use a wildcard.
    return engine.execute(['git', '-c', 'safe.directory=' + str(engine.ROOT),
                           '-C', str(engine.ROOT), 'rev-parse', 'HEAD'], capture=True).strip()


engine.harness_sha = harness_sha


def verify_checkout(path, sha):
    must(engine.execute(['git', '-c', 'safe.directory=' + str(path), '-C', str(path), 'rev-parse', 'HEAD'], capture=True).strip() == sha,
         'Runtime source checkout mismatch')
    must(not engine.execute(['git', '-c', 'safe.directory=' + str(path), '-C', str(path), 'status', '--porcelain', '--untracked-files=normal'], capture=True).strip(),
         'Runtime source checkout is dirty')


def source_manifest(p, directory, value):
    for name, sha in p['sources'].items():
        if name == 'infrastructure':
            verify_checkout(engine.ROOT, sha)
        else:
            verify_checkout(directory / name, sha)
    image_variables = ['L4_IAM_IMAGE', 'L4_CP_IMAGE', 'L4_HUMAN_IMAGE', 'L4_PULSE_IMAGE', 'INT03_NABHOLD_IMAGE']
    env = dict(line.split('=', 1) for line in (directory / 'runtime.env').read_text().splitlines())
    built = {}
    for variable in image_variables:
        image = env[variable]
        digest = engine.execute(['docker', 'image', 'inspect', '--format', '{{.Id}}', image], capture=True).strip()
        must(re.fullmatch(r'sha256:[0-9a-f]{64}', digest), 'Built image identity unavailable')
        built[variable] = digest
    # Bind the actual running service to the image built from the verified
    # source, independently of a caller-declared SHA or mutable image tag.
    for service, variable in [('keycloak', 'L4_IAM_IMAGE'), ('cp', 'L4_CP_IMAGE'), ('nabhold', 'INT03_NABHOLD_IMAGE')]:
        container = compose(p, directory / 'runtime.env', 'ps', '-q', service, capture=True).strip()
        must(re.fullmatch(r'[0-9a-f]{12,64}', container), 'Running component unavailable')
        actual = engine.execute(['docker', 'inspect', '--format', '{{.Image}}', container], capture=True).strip()
        must(actual == built[variable], 'Running image differs from built image')
    return {'sources': p['sources'], 'built_image_config_ids': built,
            'locked_runtime_images': {**engine.load()['runtime_images'], 'redis': value['redis_image'],
                                      'nabhold_base': value['nabhold_base_image']},
            'lock_sha256': hashlib.sha256((BASE / 'lock.json').read_bytes()).hexdigest(),
            'prerequisite_lock_sha256': hashlib.sha256(engine.LOCK.read_bytes()).hexdigest()}
