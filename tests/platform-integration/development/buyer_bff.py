"""DEV-07 actual confidential estate HTTP composition on the common lifecycle.

Source tools and synthetic CP-owned identities only. No provider activation,
canonical SQL, fake bearer/Principal, insecure Redis or historical-case rewrite.
"""
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import secrets
import os
import re
import sys
import time

import adapter
import buyer_identity
import buyer_bff_contract as contract
import cms_vertical
import dev
from dev07_checkout_witness import verify_checkout

BASE = Path(__file__).resolve().parent
HTTP_HOPS = {
    'hydra.int03.test:/.well-known/openid-configuration': 'IAM_DISCOVERY',
    'hydra.int03.test:/oauth2/token': 'IAM_TOKEN',
    'hydra.int03.test:/oauth2/introspect/dev07': 'IAM_INTROSPECTION',
    'hydra.int03.test:/.well-known/jwks.json': 'IAM_JWKS',
    'cp.baobab-dev.test:/internal/identity/v1/principals/resolve': 'CP_PRINCIPAL',
    'cp.baobab-dev.test:/internal/estate/v1/client-bindings/resolve': 'CP_ESTATE',
    'cp.baobab-dev.test:/v1/platform-context/resolve': 'CP_CONTEXT',
    'engine.baobab-dev.test:/store/b2b/buyer-context': 'TRADE_CONTEXT',
}


def lock():
    value = json.loads((BASE / 'buyer-bff-owner-lock.json').read_text(), object_pairs_hook=dev.unique)
    dev.require(set(value) == {'schema', 'sources', 'redis'}
        and value['schema'] == 'infrastructure.dev07-bff-owners.v1'
        and set(value['sources']) == {'baobab-trade', 'zuribeans'}
        and all(dev.SHA.fullmatch(x) for x in value['sources'].values())
        and '@sha256:' in value['redis'] and dev.DIGEST.fullmatch(value['redis']), 'DEV07_BFF_LOCK_REFUSED')
    # Candidate mode is explicit, development-only, and requires immutable
    # SHA pins for BOTH native owners. It is not a new authority path or a
    # replacement for the accepted locked DEV-07 baseline.
    if os.environ.get('DEV11_CONNECTED_BFF_REQUIRED') == 'true':
        dev.require(os.environ.get('BAOBAB_ENVIRONMENT') == 'development'
                    and os.environ.get('GITHUB_ACTIONS') == 'true',
                    'DEV11_CANDIDATE_TRUST_BOUNDARY')
        # Match the same immutable, independently reviewed source tuple as
        # the JVM owner and trace observer. A caller cannot quietly choose a
        # different Trade or estate SHA for a seemingly connected result.
        six = json.loads((BASE / 'dev11-six-owner-lock.json').read_text(),
                         object_pairs_hook=dev.unique)
        dev.require(six.get('schema') == 'infrastructure.dev11.six-owner-source-lock.v1'
                    and isinstance(six.get('sources'), dict),
                    'DEV11_SIX_OWNER_SOURCE_LOCK_INVALID')
        candidate = {
            'baobab-trade': six['sources']['baobab-trade'],
            'zuribeans': six['sources']['zuribeans'],
        }
        dev.require(all(dev.SHA.fullmatch(v) for v in candidate.values())
                    and os.environ.get('DEV11_TRADE_SHA') == candidate['baobab-trade']
                    and os.environ.get('DEV11_ZURIBEANS_SHA') == candidate['zuribeans'],
                    'DEV11_IMMUTABLE_CANDIDATE_PINS_REQUIRED')
        # The lifecycle base lock also owns CP/IAM, not only HTTP assets.
        # Require it to agree with the exact six-owner manifest.
        runtime = dev.load_lock('dev11-buyer-bff-base-lock.json')
        dev.require(all(runtime['sources'].get(owner) == six['sources'][owner]
                        for owner in ('baobab-cp', 'baobab-iam')),
                    'DEV11_BFF_ISSUER_CP_SOURCE_DRIFT')
        value['sources'] = candidate
    if os.environ.get('DEV07_GENUINE_CHECKOUT_REQUIRED') == 'true':
        dev.require(os.environ.get('BAOBAB_ENVIRONMENT') == 'development'
                    and os.environ.get('DEV11_CONNECTED_BFF_REQUIRED') != 'true',
                    'DEV07_GENUINE_CHECKOUT_PROFILE_MUST_BE_ISOLATED')
        candidate = json.loads((BASE / 'dev07-checkout-source-lock.json').read_text(),
                               object_pairs_hook=dev.unique)
        sources = candidate.get('sources', {})
        dev.require(candidate.get('schema') == 'infrastructure.dev07.checkout-source-lock.v1'
                    and candidate.get('scope') == 'DEVELOPMENT_DISPOSABLE_ONLY'
                    and candidate.get('protected_acceptance') is False
                    and set(sources) == {'baobab-trade', 'zuribeans', 'baobab-cp', 'baobab-iam'}
                    and all(dev.SHA.fullmatch(x) for x in sources.values()),
                    'DEV07_CHECKOUT_SOURCE_TUPLE_INVALID')
        runtime = dev.load_lock('dev07-checkout-base-lock.json')
        dev.require(all(runtime['sources'].get(owner) == sources[owner]
                        for owner in ('baobab-cp', 'baobab-iam'))
                    and os.environ.get('DEV07_CHECKOUT_TRADE_SHA') == sources['baobab-trade']
                    and os.environ.get('DEV07_CHECKOUT_ZURIBEANS_SHA') == sources['zuribeans'],
                    'DEV07_CHECKOUT_CURRENT_SOURCE_PINS_NOT_APPROVED')
        value['sources'] = {name: sources[name] for name in ('baobab-trade', 'zuribeans')}
    return value


def prepare():
    candidate = os.environ.get('DEV11_CONNECTED_BFF_REQUIRED') == 'true'
    checkout_candidate = os.environ.get('DEV07_GENUINE_CHECKOUT_REQUIRED') == 'true'
    run = dev.prepare(lock_name=('dev11-buyer-bff-base-lock.json' if candidate
                                 else 'dev07-checkout-base-lock.json' if checkout_candidate
                                 else 'buyer-bff-base-lock.json'))
    try:
        directory, state = dev.current(run)
        state.update(buyer_identity_profile=True, buyer_bff_http_profile=True)
        for name in ('dev07_trade_db', 'bff_redis', 'bff_store_key'):
            state['secrets'][name] = secrets.token_hex(32)
        path = directory / 'sources/baobab-iam/scripts/dev07_buyer_fixture.py'
        spec = importlib.util.spec_from_file_location('iam_dev07_bff_http', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        import yaml
        registry = yaml.safe_load((directory / 'sources/shared/contracts/identity/v1/workload-registry.yaml').read_text())
        docs = module.build_clients(registry, run, datetime.fromtimestamp(state['deadline'], timezone.utc),
            {buyer_identity.BFF: secrets.token_urlsafe(32), buyer_identity.VALIDATOR: secrets.token_urlsafe(32)}, bff_http=True)
        dev.write(directory / 'buyer-client-spec.json', docs)
        for repo, sha in lock()['sources'].items():
            source = directory / 'sources' / repo
            dev.call(['git', 'init', '-q', str(source)], state=state)
            dev.call(['git', '-C', str(source), 'fetch', '--quiet', '--depth', '1',
                'https://github.com/baobab-platform/' + repo + '.git', sha], state=state, timeout=180)
            dev.call(['git', '-C', str(source), 'checkout', '--quiet', '--detach', 'FETCH_HEAD'], state=state)
            state['sources'][repo] = sha
        dev.write(directory / 'bff-source-pins.json', state['sources'])
        dev.persist(directory, state, 'PREPARED')
        return run
    except BaseException:
        dev.down(run); raise


def commit_config(directory, state, config):
    dev.write(directory / 'compose.json', config)
    state['compose_sha256'] = hashlib.sha256((directory / 'compose.json').read_bytes()).hexdigest()
    dev.persist(directory, state, 'RUNNING')


def build(directory, state):
    for service, repo, dockerfile in (
        ('trade-bff-http', 'baobab-trade', 'Dockerfile.dev07-http'),
        ('zuribeans-bff', 'zuribeans', 'Dockerfile.dev07')):
        print('DEV07_BFF_STAGE=BUILD_' + repo.upper().replace('-', '_'), flush=True)
        source = directory / 'sources' / repo
        dev.check_dockerfile(source / dockerfile)
        image = state['project'] + '-' + service
        state['images'][service] = image; dev.persist(directory, state, 'RUNNING')
        args = ['docker', 'build', '--tag', image, '--file', str(source / dockerfile)]
        for name, val in {**dev.labels(state), 'org.opencontainers.image.revision': state['sources'][repo]}.items():
            args += ['--label', name + '=' + val]
        if repo == 'baobab-trade':
            args += ['--build-arg', 'BAOBAB_DEV07_UID=' + str(state['uid']),
                     '--build-arg', 'BAOBAB_DEV07_GID=' + str(state['gid'])]
            dev.call([*args, str(source)], state=state, timeout=1800)
        else:
            args += ['--build-arg', 'REVISION=' + state['sources'][repo],
                     '--build-arg', 'MEDUSA_BACKEND_URL=http://127.0.0.1:9000',
                     '--build-arg', 'NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY=pk_build_only_no_authority',
                     '--build-arg', 'NEXT_PUBLIC_SITE_URL=' + contract.ORIGIN]
            with cms_vertical.package_access(directory, state) as (env, token):
                dev.call([*args, '--secret', 'id=npm_token,src=' + str(token), str(source)],
                         env=env, state=state, timeout=1800)
        state['image_ids'][service] = dev.call(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'], state=state)
        dev.require(dev.DIGEST.fullmatch(state['image_ids'][service]), 'DEV07_BFF_IMAGE_REQUIRED')
        dev.persist(directory, state, 'RUNNING')


def verify_profile(directory, state):
    dev.verify_sources(directory, state)
    for name, digest in state.get('dev07_bff_config_hashes', {}).items():
        dev.require(hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest,
                    'DEV07_BFF_CONFIGURATION_DRIFT')
    owner = state.get('dev07_bff_owner_sha256')
    if owner:
        dev.require(hashlib.sha256((directory / 'dev07-bff-owner.json').read_bytes()).hexdigest() == owner,
                    'DEV07_BFF_OWNER_DESCRIPTOR_DRIFT')


def native(directory, state, phase):
    verify_profile(directory, state)
    dev.compose(directory, state, 'run', '--rm', '--no-deps', '-e', 'BAOBAB_DEV07_NATIVE_PHASE=' + phase,
        'trade-bff-http', 'node', '/app/node_modules/@medusajs/cli/cli.js', 'exec',
        '/app/src/scripts/fixture-dev07-bff-http.ts', timeout=180)


def probe(directory, state, action, timeout=90):
    verify_profile(directory, state)
    return dev.compose(directory, state, 'exec', '-T', 'probe', 'python', '/buyer_bff_probe.py', action, timeout=timeout)


def independent_checkout_witness(directory, state):
    """Run Trade's unchanged native-origin verifier in its own disposable image.

    No raw token, cookie, CP SQL, issuer secret or bearer leaves its owner.
    The verifier reads Trade PostgreSQL over a separate connection after the
    confidential BFF response and after a replay, never inside checkout's XID.
    This is source-SQL evidence only, not a full DEV-07 or ERP acceptance.
    """
    verify_profile(directory, state)
    source = directory / 'sources/baobab-trade'
    observer = source / 'scripts/dev11_native_business_origin.py'
    dockerfile = source / 'Dockerfile.dev11-rabbit-dispatcher'
    dev.require(observer.is_file() and dockerfile.is_file()
                and 'COPY scripts/dev11_native_business_origin.py /opt/baobab-trade/native_origin.py'
                    in dockerfile.read_text(),
                'DEV07_GENUINE_NATIVE_ORIGIN_OBSERVER_NOT_PINNED')
    image = state['project'] + '-trade-native-witness'
    args = ['docker', 'build', '--tag', image, '--file', str(dockerfile)]
    for name, value in {**dev.labels(state),
                        'org.opencontainers.image.revision': state['sources']['baobab-trade']}.items():
        args += ['--label', name + '=' + value]
    dev.call([*args, str(source)], state=state, timeout=1200)
    actual_image = dev.call(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'], state=state)
    dev.require(dev.DIGEST.fullmatch(actual_image), 'DEV07_WITNESS_IMAGE_ID_REQUIRED')
    state['images']['trade-native-witness'] = image
    state['image_ids']['trade-native-witness'] = actual_image
    dev.persist(directory, state, 'RUNNING')
    config = dev.read(directory / 'compose.json')
    db_url = config['services']['trade-bff-http']['environment']['DATABASE_URL']
    config['services']['trade-native-witness'] = {
        'image': image,
        'environment': {'NODE_ENV': 'test', 'BAOBAB_ENVIRONMENT': 'development',
                        'DATABASE_URL': db_url},
        'user': '65532:65532', 'networks': ['lab'],
        'profiles': ['dev07-checkout-witness'], 'read_only': True,
        'tmpfs': ['/tmp:rw,nosuid,noexec,size=4m'],
        'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
        'labels': dev.labels(state), 'restart': 'no',
    }
    commit_config(directory, state, config)
    bff = dev.read(directory / 'bff-checkout-observation.json')
    dev.require(isinstance(bff, dict) and isinstance(bff.get('order_id'), str)
                and re.fullmatch(r'order_[A-Za-z0-9_-]{6,128}', bff['order_id'])
                and isinstance(bff.get('idempotency_key'), str)
                and re.fullmatch(r'[A-Za-z0-9._:-]{16,128}', bff['idempotency_key']),
                'DEV07_BFF_OBSERVATION_SELECTORS_REFUSED')
    shell = ('python -B /opt/baobab-trade/native_origin.py "$@" '
             '--output /tmp/dev07-origin.json >/dev/null '
             '&& cat /tmp/dev07-origin.json')
    # The original Trade Python verifier selects the event from the real
    # order+idempotency pair and demands exact one native order/seller/buyer/
    # spend/outbox transaction. No user-controlled SQL or shell interpolation.
    raw = dev.compose(directory, state, 'run', '--rm', '--no-deps', '--entrypoint', 'sh',
                      'trade-native-witness', '-ec', shell, 'sh',
                      '--order-id', bff['order_id'],
                      '--idempotency-key', bff['idempotency_key'], timeout=90)
    origin = json.loads(raw)
    witness = verify_checkout(bff, origin,
                              trade_sha=state['sources']['baobab-trade'],
                              image_id=actual_image, run_id=state['run_id'])
    # Keep identifiers, event digest, correlation and source custody private.
    # The outgoing publication path may consume the original event_id after
    # its own independent IAM/CP and publisher gates are satisfied.
    dev.write(directory / 'dev07-checkout-native-origin.json', origin)
    dev.write(directory / 'dev07-checkout-witness.json', witness)
    state['dev07_checkout_sql_witnessed'] = True
    dev.persist(directory, state, 'RUNNING')
    print('DEV07_BFF_NATIVE_SAME_XID_SQL_WITNESSED_DEVELOPMENT_ONLY', flush=True)


def checkout(run, reference):
    """Operate on a prepared checkout inside the existing development lab."""
    dev.require(os.environ.get('BAOBAB_ENVIRONMENT') == 'development'
                and re.fullmatch(r'[A-Za-z0-9._:/-]{8,200}', reference),
                'DEV07_CHECKOUT_APPROVAL_REFERENCE_REQUIRED')
    with dev.guarded(run):
        directory, state = dev.current(run)
        dev.require(state.get('buyer_bff_http_profile') is True, 'DEV07_CHECKOUT_WRONG_PROFILE')
        # A baseline buyer-context run cannot become an executable checkout by
        # changing environment variables after provisioning. All four owners
        # must be the immutable disposable candidate tuple.
        source_lock = json.loads((BASE / 'dev07-checkout-source-lock.json').read_text(),
                                      object_pairs_hook=dev.unique)['sources']
        dev.require(all(state['sources'].get(owner) == sha for owner, sha in source_lock.items()),
                    'DEV07_CHECKOUT_REQUIRES_EXACT_FOUR_OWNER_CANDIDATE')
        verify_profile(directory, state)
        runtime_identity(directory, state)
        config = dev.read(directory / 'compose.json')['services']
        trade = config['trade-bff-http']['environment']
        bff = config['zuribeans-bff']['environment']
        dev.require(trade.get('BAOBAB_NATIVE_BUYER_COMMIT_ENABLED') == 'true'
                    and trade.get('BAOBAB_NATIVE_PRICE_ISSUER_ENDPOINT', '').startswith('https://')
                    and bff.get('ZURIBEANS_BUYER_COMMIT_ENABLED') == 'true',
                    'DEV07_CHECKOUT_RUNTIME_NOT_PROVISIONED')
        selection = dev.read(directory / 'bff-checkout-selection.json')
        cart = selection.get('cart_id', '')
        dev.require(re.fullmatch(r'cart_[A-Za-z0-9_-]{6,128}', cart),
                    'DEV07_CHECKOUT_CART_REFUSED')
        medusa = ('trade-bff-http', 'node', '/app/node_modules/@medusajs/cli/cli.js', 'exec')
        dev.compose(directory, state, 'run', '--rm', '--no-deps',
                    '-e', 'BAOBAB_DEV07_NATIVE_PHASE=enforce-checkout',
                    '-e', 'BAOBAB_DEV07_DISPOSABLE_CHECKOUT_APPROVED_RUN=' + run,
                    '-e', 'BAOBAB_DEV07_CHECKOUT_CHANGE_REFERENCE=' + reference,
                    *medusa, '/app/src/scripts/fixture-dev07-bff-http.ts', timeout=180)
        if not (directory / 'bff-browser.json').exists():
            probe(directory, state, 'login')
        # The price lease is short. Start issuance only after login and
        # enforcement are ready, then submit without another setup stage.
        dev.compose(directory, state, 'run', '--rm', '--no-deps',
                    '-e', 'BAOBAB_DEV07_NATIVE_PHASE=price-and-reserve',
                    '-e', 'BAOBAB_DEV07_DISPOSABLE_CHECKOUT_APPROVED_RUN=' + run,
                    '-e', 'BAOBAB_DEV07_CHECKOUT_CHANGE_REFERENCE=' + reference,
                    '-e', 'BAOBAB_NATIVE_PRICE_CART_ID=' + cart,
                    *medusa, '/app/src/scripts/fixture-dev07-bff-http.ts', timeout=90)
        probe(directory, state, 'checkout')
        independent_checkout_witness(directory, state)


def start_checkout_candidate():
    """Start a leased, isolated candidate; never report a buyer commitment."""
    dev.require(os.environ.get('BAOBAB_ENVIRONMENT') == 'development'
                and os.environ.get('DEV07_GENUINE_CHECKOUT_REQUIRED') == 'true',
                'DEV07_EXPLICIT_CHECKOUT_CANDIDATE_REQUIRED')
    run = prepare()
    try:
        with dev.guarded(run):
            up(run)
    except BaseException:
        # Failed bring-up must never orphan the source-pinned IAM/CP runtime.
        with dev.guarded(run):
            dev.down(run)
        raise
    print('DEV07_DISPOSABLE_CHECKOUT_RUN_ID=' + run, flush=True)


def finish_checkout_candidate(run):
    """Independently clean the private native and CP fixture, then host resources."""
    failed = False
    try:
        with dev.guarded(run):
            directory, state = dev.current(run)
            source_lock = json.loads((BASE / 'dev07-checkout-source-lock.json').read_text(),
                                      object_pairs_hook=dev.unique)['sources']
            dev.require(all(state['sources'].get(owner) == sha
                            for owner, sha in source_lock.items()),
                        'DEV07_CHECKOUT_TEARDOWN_WRONG_OWNER')
            for action in (
                lambda: native(directory, state, 'cleanup'),
                lambda: dev.compose(directory, state, 'exec', '-T', 'probe', 'python',
                                    '/buyer_identity_probe.py', 'binding-control', timeout=30),
                lambda: buyer_identity.cleanup_owners(run),
            ):
                try:
                    action()
                except Exception:
                    failed = True
    finally:
        # All owner cleanup is best-effort; host teardown is unconditional.
        with dev.guarded(run):
            dev.down(run)
    dev.require(not dev.resources(run) and not dev.run_dir(run).exists(),
                'DEV07_CHECKOUT_HOST_TEARDOWN_INCOMPLETE')
    dev.require(not failed, 'DEV07_CHECKOUT_OWNER_CLEANUP_INCOMPLETE')
    print('DEV07_DISPOSABLE_CHECKOUT_CLEANED_NO_PROTECTED_ACCEPTANCE', flush=True)


def runtime_identity(directory, state):
    for service in ('trade-bff-http', 'zuribeans-bff', 'trade-bff-db', 'bff-redis'):
        cid = dev.compose(directory, state, 'ps', '-q', service)
        actual = json.loads(dev.call(['docker', 'inspect', cid], state=state))[0]
        dev.require(not actual['HostConfig']['PortBindings'] and not actual['HostConfig']['Privileged']
            and actual['Config']['Labels'].get('io.baobab.dev.run') == state['run_id']
            and actual['Config']['Labels'].get('io.baobab.dev.namespace') == dev.NAMESPACE,
            'DEV07_BFF_UNSAFE_RUNTIME')
        networks = actual['NetworkSettings']['Networks']
        dev.require(len(networks) == 1 and json.loads(dev.call(['docker', 'network', 'inspect', next(iter(networks))]))[0]['Internal'] is True,
            'DEV07_BFF_NETWORK_MISMATCH')
        expected = state['image_ids'].get(service)
        if not expected:
            image = lock()['redis'] if service == 'bff-redis' else dev.load_lock('buyer-bff-base-lock.json')['images']['postgres']
            expected = dev.call(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'])
        dev.require(actual['Image'] == expected, 'DEV07_BFF_RUNTIME_IMAGE_MISMATCH')
        if service in ('zuribeans-bff', 'trade-bff-http'):
            dev.require(actual['Config']['User'] not in ('', '0', 'root', '0:0'), 'DEV07_BFF_ROOT_FORBIDDEN')
            mounts = [m for m in actual['Mounts'] if m['Destination'] == '/tls']
            dev.require(len(mounts) == 1 and mounts[0]['Source'] == adapter.host(directory / 'bff-ca')
                and mounts[0]['RW'] is False, 'DEV07_BFF_PRIVATE_TLS_KEY_EXPOSURE')
    state['dev07_bff_runtime_identity_verified'] = True
    dev.persist(directory, state, 'RUNNING')


def up(run):
    dev.up(run); dev.test(run)
    directory, state = dev.current(run)
    fixture = buyer_identity.cp_fixture(directory, state, 'prepare')
    dev.require(buyer_identity.cp_fixture(directory, state, 'read') == fixture, 'DEV07_BFF_CP_READBACK_CHANGED')
    build(directory, state)
    # Consumer engines receive the public CA, never the issuer/edge private
    # keys. The private owner/probe retains native issuer administration.
    ca = directory / 'bff-ca'; ca.mkdir(mode=0o755)
    (ca / 'ca.pem').write_bytes((directory / 'tls/ca.pem').read_bytes()); (ca / 'ca.pem').chmod(0o644)
    state['dev07_bff_config_hashes'] = {'bff-ca/ca.pem': hashlib.sha256((ca / 'ca.pem').read_bytes()).hexdigest()}
    bootstrap = dev.read(directory / 'bootstrap.json')
    owner = {key: fixture[key] for key in ('run_id', 'tenant_id', 'organisation_id', 'engine_instance_id',
                                          'expires_at', 'synthetic_only', 'protected_acceptance')}
    owner['principal_id'] = bootstrap['maker_id']
    dev.write(directory / 'dev07-bff-owner.json', owner)
    state['dev07_bff_owner_sha256'] = hashlib.sha256((directory / 'dev07-bff-owner.json').read_bytes()).hexdigest()
    output = directory / 'bff-native'; output.mkdir(mode=0o700)
    secret = state['secrets']; specs = dev.read(directory / 'buyer-client-spec.json')
    db = 'dev07_bff_' + run[:12] + '_test'; labels = dev.labels(state)
    config = dev.read(directory / 'compose.json'); services = config['services']
    tls = adapter.host(directory / 'tls')
    env = {'NODE_ENV': 'test', 'BAOBAB_ENVIRONMENT': 'development',
        'DATABASE_URL': 'postgres://dev07_bff:' + secret['dev07_trade_db'] + '@trade-bff-db:5432/' + db + '?sslmode=disable',
        'BAOBAB_DEV07_TEST_DB': db, 'BAOBAB_DEV07_RUN_ID': run,
        'BAOBAB_BUYER_IDENTITY_ENABLED': 'true', 'BAOBAB_IAM_BUYER_ISSUER': adapter.ISSUER,
        'BAOBAB_IAM_BUYER_AUTHORISED_PARTIES': buyer_identity.BFF,
        'BAOBAB_BUYER_ACCEPTED_ACR': 'aal1', 'BAOBAB_BUYER_ASSURANCE_APPROVAL_REFERENCE': 'ADR-SHARED-043:' + run,
        'BAOBAB_TRADE_ENGINE_INSTANCE_ID': fixture['engine_instance_id'],
        'BAOBAB_CONTROL_PLANE_BASE_URL': 'https://cp.baobab-dev.test',
        'BAOBAB_IAM_WORKLOAD_TOKEN_URL': adapter.ISSUER + '/oauth2/token',
        'BAOBAB_IAM_WORKLOAD_CLIENT_ID': buyer_identity.VALIDATOR,
        'BAOBAB_IAM_WORKLOAD_CLIENT_SECRET': specs[buyer_identity.VALIDATOR]['client_secret'],
        'NODE_EXTRA_CA_CERTS': '/tls/ca.pem', 'JWT_SECRET': secrets.token_hex(32), 'COOKIE_SECRET': secrets.token_hex(32), 'PORT': '9000'}
    services['trade-bff-db'] = {'image': dev.load_lock('buyer-bff-base-lock.json')['images']['postgres'],
        'environment': {'POSTGRES_DB': db, 'POSTGRES_USER': 'dev07_bff', 'POSTGRES_PASSWORD': secret['dev07_trade_db']},
        'volumes': ['trade-bff-data:/var/lib/postgresql/data'],
        'healthcheck': {'test': ['CMD-SHELL', 'pg_isready -U dev07_bff -d ' + db], 'interval': '3s', 'timeout': '3s', 'retries': 40}}
    services['trade-bff-http'] = {'image': state['image_ids']['trade-bff-http'], 'environment': env,
        'user': str(state['uid']) + ':' + str(state['gid']),
        'volumes': [adapter.host(ca) + ':/tls:ro', adapter.host(directory / 'dev07-bff-owner.json') + ':/run/dev07-bff-owner.json:ro',
                    adapter.host(output) + ':/run/dev07-bff-native']}
    config['volumes']['trade-bff-data'] = {'labels': labels}
    for name in ('trade-bff-db', 'trade-bff-http'):
        services[name].update(labels=labels, restart='no', networks=['lab'])
    commit_config(directory, state, config)
    print('DEV07_BFF_STAGE=MIGRATE', flush=True)
    dev.compose(directory, state, 'up', '-d', '--wait', '--wait-timeout', '120', 'trade-bff-db', timeout=180)
    for cmd in ('migrate', 'migrate:search'):
        dev.compose(directory, state, 'run', '--rm', '--no-deps', 'trade-bff-http', 'npm', 'run', cmd, timeout=240)
    native(directory, state, 'prepare')
    key = dev.read(output / 'store-key.json')['publishable_key']
    epoch = cms_vertical.bff_epoch(run)
    acl = directory / 'bff-redis.acl'
    acl.write_text('user default off\nuser zuribeans on >' + secret['bff_redis'] +
        ' ~zuribeans:bff:v1:' + epoch + ':* +@connection +set +get +getdel +del\n'); acl.chmod(0o644)
    services['bff-redis'] = {'image': lock()['redis'], 'command': ['redis-server', '--save', '', '--appendonly', 'no',
        '--aclfile', '/redis.acl', '--port', '0', '--tls-port', '6380', '--tls-cert-file', '/tls/edge.pem',
        '--tls-key-file', '/tls/edge.key', '--tls-ca-cert-file', '/tls/ca.pem', '--tls-auth-clients', 'no'],
        'volumes': [adapter.host(acl) + ':/redis.acl:ro', tls + ':/tls:ro'],
        'networks': {'lab': {'aliases': ['redis.baobab-dev.test']}}}
    services['zuribeans-bff'] = {'image': state['image_ids']['zuribeans-bff'],
        'volumes': [adapter.host(ca) + ':/tls:ro'], 'environment': {
            'NODE_EXTRA_CA_CERTS': '/tls/ca.pem', 'HOSTNAME': '0.0.0.0',
            'ZURIBEANS_IAM_BFF_ENABLED': 'true', 'ZURIBEANS_IAM_ENVIRONMENT': 'development',
            'ZURIBEANS_IAM_ORIGIN': contract.ORIGIN, 'ZURIBEANS_IAM_TRUST_PROXY': 'true',
            'BAOBAB_IAM_ISSUER': adapter.ISSUER, 'BAOBAB_IAM_AUDIENCE': 'baobab-trade',
            'BAOBAB_IAM_CLIENT_ID': buyer_identity.BFF,
            'ZURIBEANS_IAM_CLIENT_SECRET': specs[buyer_identity.BFF]['client_secret'],
            'BAOBAB_IAM_INTROSPECTION_ENDPOINT': adapter.ISSUER + '/oauth2/introspect/dev07',
            'ZURIBEANS_BFF_STORE_ENABLED': 'true', 'ZURIBEANS_BFF_STORE_ACTIVE_KEY': 'development',
            'ZURIBEANS_BFF_STORE_KEYS_JSON': json.dumps({'development': base64.b64encode(bytes.fromhex(secret['bff_store_key'])).decode()}),
            'ZURIBEANS_BFF_STORE_EPOCH': epoch, 'ZURIBEANS_BFF_REDIS_HOST': 'redis.baobab-dev.test',
            'ZURIBEANS_BFF_REDIS_PORT': '6380', 'ZURIBEANS_BFF_REDIS_USERNAME': 'zuribeans',
            'ZURIBEANS_BFF_REDIS_PASSWORD': secret['bff_redis'], 'ZURIBEANS_BFF_REDIS_CA_PEM': (ca / 'ca.pem').read_text(),
            'ZURIBEANS_BUYER_HANDOFF_ENABLED': 'true', 'ZURIBEANS_TRADE_BASE_URL': 'https://engine.baobab-dev.test',
            'ZURIBEANS_TRADE_PUBLISHABLE_KEY': key,
            'MEDUSA_BACKEND_URL': 'https://engine.baobab-dev.test',
            'NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY': key,
            'NEXT_PUBLIC_SITE_URL': contract.ORIGIN,
            'NEXT_PUBLIC_ENABLED_MARKETS': 'zuribeans_ug,zuribeans_za',
            'NEXT_PUBLIC_DEFAULT_MARKET': 'zuribeans_za'}}
    for name in ('bff-redis', 'zuribeans-bff'):
        services[name].update(labels=labels, restart='no'); services[name].setdefault('networks', ['lab'])
    services['edge']['networks']['lab']['aliases'].append('engine.baobab-dev.test')
    edge = adapter.EDGE.replace(' location = /oauth2/introspect {',
        ' location = /oauth2/introspect/dev07 {\n limit_except POST { deny all; }\n set $reader http://probe:8090; proxy_pass $reader/introspect;\n }\n location = /oauth2/introspect {', 1)
    # The private file contains only source-owned endpoint labels and numeric
    # statuses, never request paths, query parameters, headers or token bodies.
    status_log = 'map_hash_bucket_size 128;\nmap "$server_name:$uri" $dev07_hop { default "";\n' + ''.join(
        '"' + endpoint + '" ' + name + ';\n' for endpoint, name in HTTP_HOPS.items()) + '}\n'
    status_log += 'map $dev07_hop $dev07_log { "" 0; default 1; }\n'
    status_log += "log_format dev07_status '$dev07_hop $status $upstream_status';\n"
    status_log += 'access_log /tmp/dev07-http.status dev07_status if=$dev07_log;'
    edge = edge.replace('access_log off;', status_log, 1)
    extra = ''
    for host, upstream in (('rp.baobab-dev.test', 'zuribeans-bff:3000'), ('engine.baobab-dev.test', 'trade-bff-http:9000')):
        extra += ' server { listen 443 ssl; server_name ' + host + '; ssl_certificate /tls/edge.pem; ssl_certificate_key /tls/edge.key; location / { set $target http://' + upstream + '; proxy_pass $target; proxy_set_header Host ' + host + '; proxy_set_header X-Forwarded-Host ' + host + '; proxy_set_header X-Forwarded-Proto https; } }\n'
    (directory / 'nginx.conf').write_text(edge[:-2] + extra + '}\n')
    state['dev07_bff_config_hashes'] = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ('nginx.conf', 'bff-redis.acl', 'bff-ca/ca.pem')}
    commit_config(directory, state, config)
    dev.compose(directory, state, 'up', '-d', 'trade-bff-http', 'bff-redis', 'zuribeans-bff', 'edge', timeout=120)
    # The changed network aliases recreate edge with the new configuration.
    # Wait for HTTP readiness below instead of racing its initial PID with reload.
    print('DEV07_BFF_STAGE=HTTP_HEALTH', flush=True)
    for attempt in range(60):
        try:
            if json.loads(probe(directory, state, 'health', timeout=20)) == {'trade': 200, 'bff': 200}:
                break
        except (dev.Refused, ValueError):
            # Startup can briefly refuse connections or return a non-JSON response.
            # Keep the delay below so every failed attempt remains bounded.
            pass
        time.sleep(2)
    else:
        raise dev.Refused('DEV07_BFF_HTTP_HEALTH_REQUIRED')
    runtime_identity(directory, state)


def qualify(run):
    directory, state = dev.current(run)
    for action in ('login', 'positive', 'csrf', 'foreign'):
        probe(directory, state, action)
    if os.environ.get('DEV11_CONNECTED_BFF_REQUIRED') == 'true':
        dev11_connected_http_observation(directory, state)
    native(directory, state, 'suspend'); probe(directory, state, 'suspended')
    native(directory, state, 'resume'); probe(directory, state, 'positive')
    dev.compose(directory, state, 'pause', 'bff-redis', timeout=30)
    try: probe(directory, state, 'custody')
    finally: dev.compose(directory, state, 'unpause', 'bff-redis', timeout=30)
    probe(directory, state, 'recovery'); probe(directory, state, 'revoke')


def dev11_connected_http_observation(directory, state):
    """Observe the *actual* private BFF -> Trade -> CP process logs.

    Raw logs and technical trace IDs remain in the owned disposable runtime.
    Only bounded status booleans and exact immutable source pins are released.
    """
    report = json.loads(probe(directory, state, 'dev11-trace'))
    expected = {'dev11_bff_authorised_route_w3c', 'dev11_bff_csrf_denied_w3c',
                'dev11_bff_missing_session_denied_w3c'}
    dev.require(report.get('scope') == 'NATIVE_NEXT_TRADE_HTTP_WITH_CURRENT_IAM_CP'
                and report.get('outbox_consumer_qualified') is False
                and report.get('production_authorized') is False
                and isinstance(report.get('checks'), dict)
                and set(report['checks']) == expected
                and all(type(x) is bool for x in report['checks'].values()),
                'DEV11_BFF_TRACE_REPORT_REFUSED')
    marker = dev.read(directory / 'dev11-trace-marker.json')
    trace = marker.get('trace')
    dev.require(type(trace) is str and len(trace) == 32
                and all(x in '0123456789abcdef' for x in trace),
                'DEV11_PRIVATE_TRACE_ID_INVALID')
    checks = report['checks']
    for service, name, log_marker in (
        ('zuribeans-bff', 'dev11_native_bff_log_joined', 'bff request completed'),
        ('trade-bff-http', 'dev11_native_trade_log_joined', 'trade HTTP completed'),
        ('cp', 'dev11_native_cp_log_joined', 'request completed'),
    ):
        # Never output, upload or persist the raw docker logs. The corresponding
        # status/trace observations are produced by actual running services.
        log = dev.compose(directory, state, 'logs', '--no-color', '--tail', '1800',
                          service, timeout=30)
        index = 0
        joined = False
        while True:
            index = log.find(log_marker, index)
            if index < 0:
                break
            end = log.find(log_marker, index + len(log_marker))
            snippet = log[index:end if end > index else index + 1200]
            if trace in snippet:
                joined = True
                break
            index += len(log_marker)
        checks[name] = joined
    state['dev11_bff_connected'] = {
        'scope': 'LIVE_NEXT_IAM_CP_MEDUSA_HTTP_ONLY',
        'source_pins': {name: state['sources'][name] for name
                        in ('baobab-cp', 'baobab-trade', 'zuribeans')},
        'checks': checks, 'outbox_consumer_qualified': False,
        'runtime_qualified': False, 'production_authorized': False,
    }
    dev.persist(directory, state, 'RUNNING')
    dev.require(all(checks.values()), 'DEV11_REAL_BFF_TRADE_CP_CAUSAL_PATH_FAILED')


def cleanup(run):
    failed = False
    try:
        with dev.guarded(run):
            directory, state = dev.current(run)
            cleanup_stage = 'NATIVE_FIXTURES'
            try:
                native(directory, state, 'cleanup')
                cleanup_stage = 'COMPONENT_RECEIPT_READ'
                value = dev.read(directory / 'bff-report.json')
                value['checks']['native-fixture-cleanup'] = True
                cleanup_stage = 'COMPONENT_RECEIPT_VALIDATE'
                contract.validate(value, run, state['sources'])
                state['dev07_bff_http'] = value
                cleanup_stage = 'COMPONENT_RECEIPT_PERSIST'
                dev.persist(directory, state, 'RUNNING')
            except Exception:
                # Finite source-owned labels only; exception text can contain
                # private native output, credentials or paths and stays private.
                print('DEV07_BFF_CLEANUP_FAILED=' + cleanup_stage, flush=True)
                failed = True
            try:
                dev.compose(directory, state, 'exec', '-T', 'probe', 'python', '/buyer_identity_probe.py', 'binding-control', timeout=30)
                buyer_identity.cleanup_owners(run)
            except Exception:
                failed = True
    except Exception:
        failed = True
    finally:
        # Host teardown is independent of lease, CP, IAM and native CLI health.
        with dev.guarded(run): dev.down(run)
    return failed


def private_http_diagnostics(run):
    try:
        directory, state = dev.current(run)
        verify_profile(directory, state)
        raw = dev.compose(directory, state, 'exec', '-T', 'edge', 'tail', '-n', '64', '/tmp/dev07-http.status', timeout=10)
        for line in contract.http_status_diagnostics(raw): print(line, flush=True)
    except Exception:
        # Diagnostic availability is never qualification or a cleanup condition.
        return


def main():
    run = None; failed = False
    for name in ('dev07-bff-http-suite.json', 'dev07-bff-http-suite.sha256.json'):
        (dev.EVIDENCE / name).unlink(missing_ok=True)
    try:
        run = prepare()
        with dev.guarded(run):
            up(run); qualify(run)
    except Exception:
        if run: private_http_diagnostics(run)
        failed = True; print('DEV07_BFF_HTTP_NOT_QUALIFIED', flush=True)
    finally:
        if run:
            failed = cleanup(run) or failed
    dev.require(run is not None, 'DEV07_BFF_PREPARATION_FAILED')
    receipt = dev.read(dev.EVIDENCE / ('dev01-' + run) / 'completed/receipt.json')
    dev.require(receipt['teardown_verified'] and not dev.resources(run) and not dev.run_dir(run).exists(), 'DEV07_BFF_HOST_TEARDOWN_REQUIRED')
    component = receipt.get('dev07_bff_http')
    if component: contract.validate(component, run, receipt['source_pins'])
    qualified = (not failed and component and all(component['checks'].values())
        and receipt.get('dev07_bff_runtime_identity_verified') is True
        and receipt.get('dev07_binding_revocation_verified') is True and receipt.get('dev07_issuer_cleanup') is True)
    if os.environ.get('DEV11_CONNECTED_BFF_REQUIRED') == 'true':
        observed = receipt.get('dev11_bff_connected')
        dev.require(isinstance(observed, dict) and observed.get('runtime_qualified') is False
                    and observed.get('outbox_consumer_qualified') is False
                    and isinstance(observed.get('checks'), dict)
                    and all(observed['checks'].values())
                    and receipt['teardown_verified'] and qualified,
                    'DEV11_BFF_CP_TRADE_CONNECTED_QUALIFICATION_FAILED')
    result = {'schema': 'infrastructure.dev07-bff-http-qualified.v1', 'lifecycle': receipt,
              'bff_http_qualified': bool(qualified), 'int05_qualified': False,
              'provider_qualified': False, 'protected_acceptance': False, 'production_authorized': False}
    path = dev.EVIDENCE / 'dev07-bff-http-suite.json'
    dev.write(path, result)
    dev.write(path.with_name('dev07-bff-http-suite.sha256.json'), {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    dev.require(qualified, 'DEV07_BFF_HTTP_CASES_INCOMPLETE')
    print('DEV07_BFF_ACTUAL_NEXT_IAM_REDIS_CP_TRADE_HTTP_AND_TEARDOWN_PASS', flush=True)


if __name__ == '__main__':
    try:
        if len(sys.argv) == 2 and sys.argv[1] == 'start-checkout':
            start_checkout_candidate()
        elif len(sys.argv) == 4 and sys.argv[1] == 'checkout':
            checkout(sys.argv[2], sys.argv[3])
        elif len(sys.argv) == 3 and sys.argv[1] == 'finish-checkout':
            finish_checkout_candidate(sys.argv[2])
        else:
            dev.require(len(sys.argv) == 1, 'DEV07_BFF_UNKNOWN_COMMAND')
            main()
    except Exception:
        raise SystemExit('DEV07_BFF_HTTP_FAILED; owned recovery retained') from None
