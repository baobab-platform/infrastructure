#!/usr/bin/env python3
"""Real source-built CMS/PG17 preparation while the registry activation is held.

This component never provisions an IAM principal and cannot qualify NAB-03.
Its disposable provider/storage/probe ports are reused by the connected lane;
all fourteen connected case results remain BLOCKED in this component receipt.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import cms_gate
import handoff
import runtime as lab

o = lab.engine
BASE = Path(__file__).resolve().parent
SESSION = o.STATE / 'int03-cms-component-session.json'
PROJECT = re.compile(r'cms-int03-[0-9a-f]{16}')
IMAGE = re.compile(r'[a-z0-9][a-z0-9./:_-]*@sha256:[0-9a-f]{64}')


def must(value, reason):
    o.must(value, reason)


def pinned_checkout(directory, name, sha):
    must(name in {'shared', 'baobab-cms'} and re.fullmatch('[0-9a-f]{40}', sha), 'Invalid CMS source pin')
    o.execute(['git', 'clone', '--quiet', '--no-checkout', '--',
               'https://github.com/baobab-platform/' + name + '.git', str(directory)], timeout=300)
    o.execute(['git', '-C', str(directory), 'checkout', '--quiet', '--detach', sha], timeout=60)
    must(o.execute(['git', '-C', str(directory), 'rev-parse', 'HEAD'], capture=True).strip() == sha,
         'CMS source checkout differs')
    must(not o.execute(['git', '-C', str(directory), 'status', '--porcelain', '--untracked-files=all'], capture=True).strip(),
         'CMS source checkout is not clean')


def load():
    lock = handoff.document((BASE / 'cms-lock.json').read_text())
    must(set(lock) == {'schema', 'profile', 'decision', 'sources', 'synthetic_only', 'full_int03_acceptance', 'runtime_images'} and
         lock['profile'] == 'cms-capability-proof' and set(lock['sources']) == {'shared', 'baobab-cms', 'baobab-iam', 'baobab-cp', 'nabhold'}, 'CMS lock shape differs')
    must(lock['schema'] == 'infrastructure.int03.cms.v1' and lock['synthetic_only'] is True
         and lock['full_int03_acceptance'] is False, 'Invalid CMS profile boundary')
    must(set(lock['runtime_images']) == {'node', 'postgres'} and
         all(IMAGE.fullmatch(v) for v in lock['runtime_images'].values()), 'CMS runtime images not pinned')
    must(lock['runtime_images']['node'].startswith('node:24.') and
         lock['runtime_images']['postgres'].startswith('postgres:17'), 'Unsupported CMS toolchain/storage')
    must(all(re.fullmatch('[0-9a-f]{40}', v) for v in lock['sources'].values()), 'Invalid CMS source pins')
    must(not re.search(r'(?m)^\s+ports\s*:', (BASE / 'cms-compose.yaml').read_text()), 'CMS host ports forbidden')
    return lock


def current():
    must(SESSION.is_file() and not SESSION.is_symlink() and SESSION.stat().st_size <= 8192,
         'CMS recovery state unavailable')
    p = handoff.document(handoff.read_file(SESSION))
    must(set(p) == {'project', 'run_id', 'deadline', 'source_sha'} and PROJECT.fullmatch(p['project']) and
         p['project'] == 'cms-int03-' + p['run_id'] and re.fullmatch('[0-9a-f]{40}', p['source_sha']), 'Invalid CMS recovery state')
    directory = o.STATE / p['project']
    must(not directory.is_symlink() and directory.resolve().parent == o.STATE.resolve() and
         (not directory.exists() or directory.is_dir() and directory.stat().st_uid == os.getuid() and not directory.stat().st_mode & 0o077),
         'CMS recovery directory invalid')
    envfile = directory / 'compose.env'
    return p, directory, envfile


def compose(p, envfile, *args, capture=False, timeout=300, stdin=None):
    return o.execute(['docker', 'compose', '--env-file', str(envfile), '-f', str(BASE / 'cms-compose.yaml'),
                      '-p', p['project'], *args], capture=capture, timeout=timeout, input_text=stdin)


def cleanup(expected=None):
    if not SESSION.exists():
        if expected is None:
            return
        # The running process still knows its project if its recovery file was
        # removed. Never turn a missing handle into a successful no-op teardown.
        p = expected
        must(PROJECT.fullmatch(p['project']) and p['project'] == 'cms-int03-' + p['run_id'], 'Invalid in-memory CMS owner')
        directory = o.STATE / p['project']
        must(not directory.is_symlink() and directory.resolve().parent == o.STATE.resolve() and
             (not directory.exists() or directory.is_dir() and directory.stat().st_uid == os.getuid() and
              not directory.stat().st_mode & 0o077), 'CMS directory escaped')
    else:
        p, directory, _envfile = current()
        must(expected is None or p == expected, 'CMS recovery owner changed')
    # Same ownership-label recovery strategy as INT-03 host_cleanup.py: this
    # does not need a surviving Compose envfile, source checkout or healthy DB.
    for kind, listing, remove in [
        ('container', ['docker', 'ps', '-aq'], ['docker', 'rm', '-f']),
        ('network', ['docker', 'network', 'ls', '-q'], ['docker', 'network', 'rm']),
        ('volume', ['docker', 'volume', 'ls', '-q'], ['docker', 'volume', 'rm']),
    ]:
        query = [*listing, '--filter', 'label=com.docker.compose.project=' + p['project']]
        for identifier in o.execute(query, capture=True).strip().splitlines():
            valid = re.fullmatch('[0-9a-f]{12,64}', identifier) or kind == 'volume' and re.fullmatch(re.escape(p['project']) + r'_[a-z0-9_-]+', identifier)
            must(valid, 'Untrusted CMS resource identifier')
            o.execute([*remove, identifier], timeout=120)
        must(not o.execute(query, capture=True).strip(), 'CMS teardown incomplete')
    for kind in ['runtime', 'tool']:
        tag = 'int03-cms-' + kind + ':' + p['run_id']
        if o.execute(['docker', 'image', 'ls', '-q', '--filter', 'reference=' + tag], capture=True).strip():
            o.execute(['docker', 'image', 'rm', tag], timeout=120)
    if directory.exists():
        shutil.rmtree(directory)
    SESSION.unlink(missing_ok=True)


def materialise(lock):
    must(not SESSION.exists(), 'An earlier CMS component session needs cleanup')
    run_id = secrets.token_hex(8)
    p = {'project': 'cms-int03-' + run_id, 'run_id': run_id, 'deadline': time.time() + 80 * 60,
         'source_sha': lock['sources']['baobab-cms']}
    directory = o.STATE / p['project']
    directory.mkdir(mode=0o700, parents=True)
    envfile = directory / 'compose.env'
    values = {'CMS_PROJECT': p['project'], 'CMS_RUN_ID': run_id,
              'CMS_SOURCE': str(directory / 'baobab-cms'), 'CMS_SOURCE_SHA': p['source_sha'],
              'CMS_LAB_SOURCE': o.host_path(BASE), 'CMS_POSTGRES_IMAGE': lock['runtime_images']['postgres'],
              'CMS_RUNTIME_IMAGE': 'int03-cms-runtime:' + run_id, 'CMS_TOOL_IMAGE': 'int03-cms-tool:' + run_id,
              'CMS_DB_PASSWORD': secrets.token_hex(32), 'CMS_PAYLOAD_SECRET': secrets.token_hex(48)}
    try:
        o.private(envfile, ''.join(k + '=' + v + '\n' for k, v in values.items()))
        o.private(SESSION, json.dumps(p) + '\n')
    except BaseException:
        # No process/container has been started before the recovery handle.
        shutil.rmtree(directory)
        raise
    # Publish the recovery handle before clone/build/start can allocate services.
    pinned_checkout(directory / 'shared', 'shared', lock['sources']['shared'])
    pinned_checkout(directory / 'baobab-cms', 'baobab-cms', p['source_sha'])
    gate = cms_gate.evaluate(directory / 'shared', lock)
    must(gate['gate']['verdict'] != 'REFUSED', 'CMS canonical registry refused')
    source = directory / 'baobab-cms'
    must('FROM ' + lock['runtime_images']['node'] + ' AS base' in (source / 'Dockerfile').read_text().splitlines(),
         'CMS builder differs from locked Node image')
    must((source / 'scripts/qualification/int03-fixture.ts').is_file(), 'CMS runtime fixture source not implemented at pin')
    return p, directory, envfile, gate


def document(raw, schema):
    must(isinstance(raw, str) and len(raw.encode()) <= 1024 * 1024, 'CMS observation exceeds bound')
    # Payload's normal logs are discarded, not exported as evidence.
    value = handoff.document(raw.strip().splitlines()[-1])
    must(type(value) is dict and value.get('schema') == schema, 'CMS observation shape differs')
    return value


def fixture(p, envfile, action):
    value = document(compose(p, envfile, 'run', '--rm', '--no-deps', 'cms-tool',
        'node', '--import', 'tsx', 'scripts/qualification/int03-fixture.ts', action, capture=True, timeout=90), 'cms.int03.fixture.v1')
    must(value['run_id'] == p['run_id'] and value['action'] == action and value['converged'] is True and
         value['identities_created'] is False and value['cp_issuance_proven'] is False and
         value['human_editorial_approval'] is False and value['connected_qualification'] is False and
         value['evidence_class'] == 'CMS_COMPONENT_SYNTHETIC_DATA' and value['full_int03_acceptance'] is False and
         value['production_authorized'] is False and
         value['canonical_references'] == dict.fromkeys(['tenant', 'organisation', 'legalEntity', 'market', 'digitalEstate'], 'UNRESOLVED'),
         'CMS fixture crossed component boundary')
    expected = {'seed': ('draft', 'DRAFT'), 'publish': ('published', 'PUBLISHED'),
                'withdraw': ('archived', 'UNPUBLISHED'), 'draft': ('draft', 'DRAFT')}.get(action)
    if expected:
        must(value['states'] == {'home': expected[0], **dict.fromkeys(['navigation', 'footer', 'site-settings', 'group-profile'], expected[1])},
             'CMS fixture states differ')
    must(type(value['database_version_num']) is int and value['database_version_num'] // 10000 == 17,
         'Actual CMS database is not PostgreSQL 17')
    return {'action': action, 'passed': True, 'database_version_num': value['database_version_num']}


def probe(p, envfile, mode):
    value = document(compose(p, envfile, 'run', '--rm', '--no-deps', 'cms-probe', mode,
                             capture=True, timeout=60), 'int03.cms.http-probe.v1')
    must(value['mode'] == mode and value['passed'] is True and value['node'] == 'v24.21.0' and
         value['identities_created'] is False and value['connected_qualification'] is False, 'CMS HTTP observation differs')
    return {'mode': mode, 'passed': True, 'node': value['node']}


def wait_probe(p, envfile):
    deadline = time.monotonic() + 120
    while True:
        try:
            return probe(p, envfile, 'healthy')
        except o.Blocked:
            must(time.monotonic() < deadline, 'CMS readiness recovery timed out')
            time.sleep(2)


def verify_tool_manifest(p, envfile, expected):
    script = ('const fs=require("node:fs"),crypto=require("node:crypto");'
              'const paths=JSON.parse(fs.readFileSync(0,"utf8"));'
              'process.stdout.write(JSON.stringify(Object.fromEntries(paths.map(p=>'
              '[p,crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex")]))));')
    value = handoff.document(compose(p, envfile, 'run', '--rm', '--no-deps', '-T', 'cms-tool',
        'node', '-e', script, stdin=json.dumps(sorted(expected)), capture=True, timeout=60))
    must(value == expected, 'Built CMS tool/migrations differ from verified source')
    npm = compose(p, envfile, 'run', '--rm', '--no-deps', 'cms-tool', 'npm', '--version', capture=True, timeout=30).strip()
    must(re.fullmatch(r'11\.[0-9]+\.[0-9]+', npm), 'CMS package manager is not supported npm 11')
    return {'files_sha256': value, 'npm': npm}


def image_provenance(tag, revision=None):
    value = json.loads(o.execute(['docker', 'image', 'inspect', tag], capture=True))[0]
    must(re.fullmatch('sha256:[0-9a-f]{64}', value['Id']), 'CMS image content ID unavailable')
    if revision:
        must(value['Config']['Labels']['org.opencontainers.image.revision'] == revision, 'CMS runtime source label differs')
    return {'image_id': value['Id'], 'os': value['Os'], 'architecture': value['Architecture']}


def source_provenance(source):
    files = o.execute(['git', '-C', str(source), 'ls-files', '--', 'Dockerfile', 'package.json', 'package-lock.json', 'migrations'], capture=True).splitlines()
    must(all(re.fullmatch(r'(Dockerfile|package(?:-lock)?\.json|migrations/[A-Za-z0-9_.-]+)', f) for f in files), 'CMS source manifest path differs')
    return {path: hashlib.sha256((source / path).read_bytes()).hexdigest() for path in files}


def run():
    lock = load()
    receipt = {'schema': 'infrastructure.int03.cms-component.v1', 'evidence_class': 'ACTUAL_CMS_PG17_COMPONENT_SYNTHETIC_DATA',
        'scenario': 'NAB-03', 'cases': dict.fromkeys(cms_gate.CASES, 'BLOCKED'), 'qualified': False,
        'identities_created': False, 'full_int03_acceptance': False, 'production_authorized': False,
        'component_outcome': 'FAIL', 'teardown': 'NOT_RUN', 'fixtures': [], 'probes': []}
    error = None
    p = None
    try:
        p, directory, envfile, gate = materialise(lock)
        receipt.update({'run_id': p['run_id'], 'registry_gate': gate['gate'], 'shared': gate['shared'],
            'decision': gate['decision'], 'observed_sources': {'baobab-cms': p['source_sha'], 'shared': lock['sources']['shared'],
            'infrastructure': lab.harness_sha()}, 'source_manifest': source_provenance(directory / 'baobab-cms')})
        lab.require_clean_harness()
        receipt['phase'] = 'BUILD'
        compose(p, envfile, 'build', 'cms-tool', 'cms', timeout=1800)
        receipt['tool_manifest'] = verify_tool_manifest(p, envfile, receipt['source_manifest'])
        receipt['build_base_reference'] = lock['runtime_images']['node']
        receipt['images'] = {'cms': image_provenance('int03-cms-runtime:' + p['run_id'], p['source_sha']),
            'cms_tool': image_provenance('int03-cms-tool:' + p['run_id'])}
        receipt['phase'] = 'DATABASE'
        compose(p, envfile, 'up', '-d', '--wait', '--wait-timeout', '120', 'cms-db', timeout=150)
        receipt['images']['postgres'] = {**image_provenance(lock['runtime_images']['postgres']), 'reference': lock['runtime_images']['postgres']}
        compose(p, envfile, 'exec', '-T', 'cms-db', 'psql', '-U', 'payload', '-d', 'cms_int03_' + p['run_id'],
                '-v', 'ON_ERROR_STOP=1', '-c', 'CREATE SCHEMA payload AUTHORIZATION payload;', timeout=30)
        receipt['phase'] = 'MIGRATIONS'
        compose(p, envfile, 'run', '--rm', '--no-deps', 'cms-tool', 'npm', 'run', 'db:migrate', timeout=180)
        applied = compose(p, envfile, 'exec', '-T', 'cms-db', 'psql', '-U', 'payload', '-d', 'cms_int03_' + p['run_id'],
            '-v', 'ON_ERROR_STOP=1', '-t', '-A', '-c', 'SELECT name FROM payload.payload_migrations ORDER BY name;', capture=True, timeout=30).splitlines()
        expected = sorted(path.stem for path in (directory / 'baobab-cms/migrations').glob('*.ts') if path.name != 'index.ts')
        must(applied == expected and bool(expected), 'Committed migration readback differs')
        receipt['migrations_applied'] = applied
        for action in ['seed', 'seed', 'verify', 'publish', 'withdraw', 'draft', 'verify']:
            receipt['phase'] = 'FIXTURE_' + action.upper()
            receipt['fixtures'].append(fixture(p, envfile, action))
        receipt['phase'] = 'HTTP_HEALTHY'
        compose(p, envfile, 'up', '-d', '--wait', '--wait-timeout', '180', 'cms', timeout=210)
        receipt['probes'].append(wait_probe(p, envfile))
        receipt['phase'] = 'DATABASE_OUTAGE'
        compose(p, envfile, 'stop', 'cms-db', timeout=30)
        receipt['probes'].append(probe(p, envfile, 'database-down'))
        receipt['phase'] = 'DATABASE_RECOVERY'
        compose(p, envfile, 'up', '-d', '--wait', '--wait-timeout', '120', 'cms-db', timeout=150)
        receipt['probes'].append(wait_probe(p, envfile))
        must(time.time() < p['deadline'], 'CMS component deadline exceeded')
        receipt['component_outcome'] = 'PASS'
        receipt['phase'] = 'COMPONENT_COMPLETE'
    except BaseException as cause:
        # Never export exception strings, build logs, DB/HTTP contents or secrets.
        error = cause
    finally:
        try:
            cleanup(p)
            receipt['teardown'] = 'PASS'
        except BaseException:
            receipt['teardown'] = 'FAIL'
            receipt['component_outcome'] = 'FAIL'
    if error:
        receipt['component_outcome'] = 'FAIL'
    receipt['generated_at'] = datetime.now(timezone.utc).isoformat()
    target = o.EVIDENCE / ('cms-component-' + receipt.get('run_id', secrets.token_hex(8)))
    target.mkdir(mode=0o700, parents=True)
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + '\n').encode()
    pending = target / '.pending'
    pending.mkdir(mode=0o700)
    try:
        o.private(pending / 'receipt.json', raw.decode())
        o.private(pending / 'receipt.sha256', hashlib.sha256(raw).hexdigest() + '  receipt.json\n')
        for path in pending.iterdir():
            with path.open('rb') as handle:
                os.fsync(handle.fileno())
        descriptor = os.open(pending, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.rename(pending, target / 'completed')
        descriptor = os.open(target, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        shutil.rmtree(pending, ignore_errors=True)
        shutil.rmtree(target / 'completed', ignore_errors=True)
        raise
    print('CMS component ' + receipt['component_outcome'] + '; phase=' + receipt.get('phase', 'MATERIALISE') + '; teardown=' + receipt['teardown'] + '; NAB-03 14 cases BLOCKED; qualified=false')
    return 0 if receipt['component_outcome'] == receipt['teardown'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('command', choices=['run', 'down', 'preflight'])
    args = parser.parse_args()
    if args.command == 'down':
        cleanup()
        return 0
    if args.command == 'preflight':
        load()
        return 0
    def interrupted(_signum, _frame):
        raise InterruptedError('CMS component interrupted')
    for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGALRM]:
        signal.signal(sig, interrupted)
    signal.alarm(80 * 60)
    try:
        return run()
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    sys.exit(main())
