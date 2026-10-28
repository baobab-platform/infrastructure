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
import time

import adapter
import buyer_identity
import buyer_bff_contract as contract
import cms_vertical
import dev

BASE = Path(__file__).resolve().parent


def lock():
    value = json.loads((BASE / 'buyer-bff-owner-lock.json').read_text(), object_pairs_hook=dev.unique)
    dev.require(set(value) == {'schema', 'sources', 'redis'}
        and value['schema'] == 'infrastructure.dev07-bff-owners.v1'
        and set(value['sources']) == {'baobab-trade', 'zuribeans'}
        and all(dev.SHA.fullmatch(x) for x in value['sources'].values())
        and '@sha256:' in value['redis'] and dev.DIGEST.fullmatch(value['redis']), 'DEV07_BFF_LOCK_REFUSED')
    return value


def prepare():
    run = dev.prepare(lock_name='buyer-bff-base-lock.json')
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
        if service == 'zuribeans-bff':
            dev.require(actual['Config']['User'] not in ('', '0', 'root', '0:0'), 'DEV07_BFF_ROOT_FORBIDDEN')
    state['dev07_bff_runtime_identity_verified'] = True
    dev.persist(directory, state, 'RUNNING')


def up(run):
    dev.up(run); dev.test(run)
    directory, state = dev.current(run)
    fixture = buyer_identity.cp_fixture(directory, state, 'prepare')
    dev.require(buyer_identity.cp_fixture(directory, state, 'read') == fixture, 'DEV07_BFF_CP_READBACK_CHANGED')
    build(directory, state)
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
        'volumes': [tls + ':/tls:ro', adapter.host(directory / 'dev07-bff-owner.json') + ':/run/dev07-bff-owner.json:ro',
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
    # The estate gets the public CA only, never the edge TLS private key.
    ca = directory / 'bff-ca'; ca.mkdir(mode=0o755)
    (ca / 'ca.pem').write_bytes((directory / 'tls/ca.pem').read_bytes()); (ca / 'ca.pem').chmod(0o644)
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
    extra = ''
    for host, upstream in (('rp.baobab-dev.test', 'zuribeans-bff:3000'), ('engine.baobab-dev.test', 'trade-bff-http:9000')):
        extra += ' server { listen 443 ssl; server_name ' + host + '; ssl_certificate /tls/edge.pem; ssl_certificate_key /tls/edge.key; location / { set $target http://' + upstream + '; proxy_pass $target; proxy_set_header Host ' + host + '; proxy_set_header X-Forwarded-Host ' + host + '; proxy_set_header X-Forwarded-Proto https; } }\n'
    (directory / 'nginx.conf').write_text(edge[:-2] + extra + '}\n')
    state['dev07_bff_config_hashes'] = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in ('nginx.conf', 'bff-redis.acl', 'bff-ca/ca.pem')}
    commit_config(directory, state, config)
    dev.compose(directory, state, 'up', '-d', 'trade-bff-http', 'bff-redis', 'zuribeans-bff', timeout=120)
    dev.compose(directory, state, 'exec', '-T', 'edge', 'nginx', '-s', 'reload', timeout=30)
    print('DEV07_BFF_STAGE=HTTP_HEALTH', flush=True)
    for attempt in range(60):
        try:
            if json.loads(probe(directory, state, 'health', timeout=20)) == {'trade': 200, 'bff': 200}:
                break
        except (dev.Refused, ValueError):
            pass
        time.sleep(2)
    else:
        raise dev.Refused('DEV07_BFF_HTTP_HEALTH_REQUIRED')
    runtime_identity(directory, state)


def qualify(run):
    directory, state = dev.current(run)
    for action in ('login', 'positive', 'csrf', 'foreign'):
        probe(directory, state, action)
    native(directory, state, 'suspend'); probe(directory, state, 'suspended')
    native(directory, state, 'resume'); probe(directory, state, 'positive')
    dev.compose(directory, state, 'pause', 'bff-redis', timeout=30)
    try: probe(directory, state, 'custody')
    finally: dev.compose(directory, state, 'unpause', 'bff-redis', timeout=30)
    probe(directory, state, 'recovery'); probe(directory, state, 'revoke')


def cleanup(run):
    failed = False
    try:
        with dev.guarded(run):
            directory, state = dev.current(run)
            try:
                native(directory, state, 'cleanup')
                value = dev.read(directory / 'bff-report.json')
                value['checks']['native-fixture-cleanup'] = True
                contract.validate(value, run, state['sources'])
                state['dev07_bff_http'] = value
                dev.persist(directory, state, 'RUNNING')
            except Exception:
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


def main():
    run = None; failed = False
    for name in ('dev07-bff-http-suite.json', 'dev07-bff-http-suite.sha256.json'):
        (dev.EVIDENCE / name).unlink(missing_ok=True)
    try:
        run = prepare()
        with dev.guarded(run):
            up(run); qualify(run)
    except Exception:
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
    result = {'schema': 'infrastructure.dev07-bff-http-qualified.v1', 'lifecycle': receipt,
              'bff_http_qualified': bool(qualified), 'int05_qualified': False,
              'provider_qualified': False, 'protected_acceptance': False, 'production_authorized': False}
    path = dev.EVIDENCE / 'dev07-bff-http-suite.json'
    dev.write(path, result)
    dev.write(path.with_name('dev07-bff-http-suite.sha256.json'), {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    dev.require(qualified, 'DEV07_BFF_HTTP_CASES_INCOMPLETE')
    print('DEV07_BFF_ACTUAL_NEXT_IAM_REDIS_CP_TRADE_HTTP_AND_TEARDOWN_PASS', flush=True)


if __name__ == '__main__':
    try: main()
    except Exception:
        raise SystemExit('DEV07_BFF_HTTP_FAILED; owned recovery retained') from None
