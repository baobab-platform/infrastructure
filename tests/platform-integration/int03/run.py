#!/usr/bin/env python3
"""Execute the actual connected identity smoke; full INT-03 remains separate."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import uuid

sys.dont_write_bytecode = True

import handoff
import runtime as lab

o = lab.engine
IDS = ['NAB-ID-01', 'NAB-ID-02', 'NAB-ID-03', 'NAB-ID-04']


def provision(p, directory, envfile):
    """No real humans/admin role/business grants; explicit lab-only CP records."""
    password = secrets.token_hex(32)
    principal = str(uuid.uuid4())
    inputs = {'synthetic': True, 'sources': {k: p['sources'][k] for k in handoff.SOURCES},
              'principal_id': principal, 'username': handoff.USERNAME, 'password': password,
              'ca_file': str(directory / 'tls/ca.pem')}
    prepared = handoff.prepare(inputs,
        handoff.document(handoff.read_file(directory / 'baobab-iam/config/clients/nabhold-executive.json', private=False)),
        handoff.read_file(inputs['ca_file'], private=False), directory / 'int03-bundle')
    user = {'username': handoff.USERNAME, 'enabled': True, 'emailVerified': True,
            'firstName': 'Synthetic', 'lastName': 'INT03', 'email': 'int03@example.invalid',
            'credentials': [{'type': 'password', 'value': password, 'temporary': False}]}
    lines = ['set -euo pipefail', 'set +x', 'umask 077', 'INT03_FIXTURE_DIR=$(mktemp -d)',
             'trap \'rm -rf "$INT03_FIXTURE_DIR"\' EXIT']
    for name, content in [('client.json', (prepared / 'client.json').read_text()), ('user.json', json.dumps(user))]:
        marker = 'INT03_' + secrets.token_hex(20)
        o.must(marker not in content, 'Fixture delimiter collision')
        lines.extend([f'cat > "$INT03_FIXTURE_DIR/{name}" <<\'{marker}\'', content, marker])
    lines.append((lab.BASE / 'fixture.sh').read_text())
    subject = lab.compose(p, envfile, 'exec', '-T', 'keycloak', '/bin/bash', '-se',
                          stdin='\n'.join(lines), capture=True, timeout=180).strip()
    o.must(re.fullmatch(r'[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', subject), 'Issuer subject unavailable')
    # Synthetic fixture creation, confined to this private disposable CP DB.
    # It is not a registration API, onboarding acceptance or production recipe.
    statement = f"""BEGIN;
    INSERT INTO identity.principal(principal_id,actor_type,status)
    VALUES ('{principal}','human','ACTIVE');
    INSERT INTO identity.external_identity(principal_id,issuer,subject,status)
    VALUES ('{principal}','{o.ISSUER}','{subject}','ACTIVE');
    COMMIT;
    SELECT count(*) FROM identity.external_identity e JOIN identity.principal p USING(principal_id)
    WHERE e.principal_id='{principal}' AND e.issuer='{o.ISSUER}' AND e.subject='{subject}'
      AND e.status='ACTIVE' AND p.status='ACTIVE' AND p.actor_type='human';"""
    result = o.cp_sql(p, envfile, 'identity_human', statement)
    o.must(result.strip().splitlines()[-1] == '1', 'Current synthetic CP mapping not established')


def smoke_projection(raw, sources):
    """Only closed booleans and fixed IDs cross the component boundary."""
    o.must(type(raw) is str and 0 < len(raw.encode()) <= 16384, 'Consumer receipt unavailable')
    r = json.loads(raw, object_pairs_hook=handoff.unique)
    o.must(type(r) is dict and set(r) == {'schema', 'runId', 'startedAt', 'profile',
        'syntheticIdentities', 'nabhold', 'declaredDependencies', 'dependencyRuntimeAttested',
        'acceptanceClaimed', 'endedAt', 'outcome', 'observations', 'processSucceeded'}, 'Unexpected consumer receipt')
    o.must(r['schema'] == 'nabhold.identity-smoke.observation.v1' and
           r['profile'] == 'keycloak-identity-smoke' and r['syntheticIdentities'] is True and
           r['dependencyRuntimeAttested'] is False and r['acceptanceClaimed'] is False and
           r['nabhold'] == {'sha': sources['nabhold'], 'worktree': 'clean'}, 'Consumer source/profile mismatch')
    expected = {k: sources[v] for k, v in [('infrastructure', 'infrastructure'), ('iam', 'baobab-iam'),
                                          ('cp', 'baobab-cp'), ('shared', 'shared')]}
    o.must(r['declaredDependencies'] == expected, 'Declared pins differ from observed sources')
    observation = r['observations']
    o.must(type(observation) is dict and set(observation) == {'complete', 'invalid', 'results'} and
           type(observation['results']) is dict and set(observation['results']) == set(IDS), 'Incomplete consumer coverage')
    o.must(r['processSucceeded'] is True and r['outcome'] == 'PASS' and
           observation['complete'] is True and observation['invalid'] is False and
           all(observation['results'][key] == 'passed' for key in IDS), 'Consumer smoke did not pass')
    return {'consumer_receipt_sha256': hashlib.sha256(raw.encode()).hexdigest(),
            'scenarios': {key: 'PASS' for key in IDS}}


def cleanup():
    """Keep recovery state on failure; no acceptance before ALL cleanup."""
    if not o.SESSION.exists():
        return
    p, directory, envfile = o.current()
    env = dict(line.split('=', 1) for line in envfile.read_text().splitlines())
    destroy = lab.compose if 'INT03_NABHOLD_IMAGE' in env else lab.base_compose
    destroy(p, envfile, 'down', '--volumes', '--remove-orphans', timeout=240)
    for resource, command in [('container', ['docker', 'ps', '-aq']),
                              ('network', ['docker', 'network', 'ls', '-q']),
                              ('volume', ['docker', 'volume', 'ls', '-q'])]:
        seen = o.execute([*command, '--filter', 'label=com.docker.compose.project=' + p['project']], capture=True)
        o.must(not seen.strip(), 'Disposable ' + resource + ' cleanup incomplete')
    for key in ('L4_IAM_IMAGE', 'L4_CP_IMAGE', 'L4_HUMAN_IMAGE', 'L4_PULSE_IMAGE', 'INT03_NABHOLD_IMAGE'):
        image = env.get(key)
        if image:
            o.must(re.fullmatch(r'l4-(iam|cp|human|pulse|nabhold)-l4-[0-9a-f]{16}', image), 'Untrusted cleanup image')
            if o.execute(['docker', 'image', 'ls', '-q', '--filter', 'reference=' + image], capture=True).strip():
                o.execute(['docker', 'image', 'rm', image], timeout=120)
    # Existing prerequisite receipt gains its own teardown checkpoint; no
    # statement here promotes its result into full Nabhold/CMS acceptance.
    o.compose = destroy
    try:
        o.down()
    finally:
        o.compose = lab.compose


def write_receipt(project, receipt):
    # Publish the receipt and digest together. A write/sync failure must never
    # expose a standalone PASS file without its completed evidence pair.
    o.EVIDENCE.mkdir(exist_ok=True)
    final = o.EVIDENCE / (project + '-int03-identity')
    final.mkdir(mode=0o700)
    try:
        pending = final / '.pending'
        pending.mkdir(mode=0o700)
        body = json.dumps(receipt, sort_keys=True, indent=2) + '\n'
        handoff.write_private(pending / 'receipt.json', body)
        handoff.write_private(pending / 'receipt.sha256', hashlib.sha256(body.encode()).hexdigest() + '\n')
        handoff.sync_directory(pending)
        os.rename(pending, final / 'completed')
        handoff.sync_directory(final)
        handoff.sync_directory(o.EVIDENCE)
    except BaseException:
        shutil.rmtree(final)
        raise


def run(value, prerequisite, token):
    receipt = {'schema': 'infrastructure.int03.identity.observed.v1', 'profile': value['profile'],
               'evidence_class': 'REAL_COMPONENT_SYNTHETIC_DATA', 'synthetic_only': True,
               'full_int03_accepted': False, 'protected_staging_accepted': False,
               'production_authorized': False, 'teardown_verified': False,
               'passed': False, 'scenarios': {key: 'BLOCKED' for key in IDS}}
    project = None
    stage = 'materialise'

    def checkpoint(name):
        nonlocal stage
        stage = name
        print('INT-03 stage: ' + name, flush=True)
    try:
        lab.materialise(value, prerequisite, token)
        p, directory, envfile = o.current()
        project = p['project']
        checkpoint('consumer-build')
        docker_config = directory / 'build-docker-config'
        docker_config.mkdir(mode=0o700)
        build_env = {**os.environ, 'DOCKER_CONFIG': str(docker_config)}
        try:
            username = os.environ.get('INT03_REGISTRY_USERNAME', '')
            o.must(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', username), 'Registry username unavailable')
            o.execute(['docker', 'login', 'ghcr.io', '--username', username, '--password-stdin'],
                      input_text=(directory / 'npm-token').read_text(), env=build_env, timeout=60)
            lab.compose(p, envfile, 'build', 'nabhold', timeout=1800, command_env=build_env)
        finally:
            # Blank rather than unlink: Compose still validates this secret
            # path during later commands. No package credential reaches up().
            (directory / 'npm-token').write_text('')
            shutil.rmtree(docker_config)
        checkpoint('prerequisite-up')
        o.up(prerequisite)
        checkpoint('prerequisite-requalification')
        o.test(prerequisite)
        receipt['prerequisite_checks_passed'] = True
        checkpoint('identity-fixture')
        provision(p, directory, envfile)
        checkpoint('consumer-up')
        lab.compose(p, envfile, 'up', '-d', 'redis-int03', 'nabhold', timeout=180)
        lab.compose(p, envfile, 'exec', '-T', 'probe', 'python', '-',
                    stdin=(lab.BASE / 'wait.py').read_text(), timeout=260)
        checkpoint('runtime-provenance')
        receipt['runtime'] = lab.source_manifest(p, directory, value)
        actual = lab.compose(p, envfile, 'exec', '-T', 'nabhold', 'git', 'rev-parse', 'HEAD', capture=True).strip()
        o.must(actual == value['sources']['nabhold'], 'Running estate source mismatch')
        dirty = lab.compose(p, envfile, 'exec', '-T', 'nabhold', 'git', 'status', '--porcelain', '--untracked-files=normal', capture=True)
        o.must(not dirty.strip(), 'Running estate source is dirty')
        checkpoint('browser-smoke')
        raw = lab.compose(p, envfile, 'run', '--rm', '--no-deps', 'nabhold', 'test', capture=True, timeout=400)
        receipt.update(smoke_projection(raw, p['sources']))
        receipt['smoke_checks_passed'] = True
    except Exception as error:
        match = re.search(r"Build failure class: ([A-Z_]{1,32})", str(error)) if isinstance(error, o.Blocked) else None
        if match:
            receipt['failure_class'] = match.group(1)
        # No exception message, URL, command argv, Principal or credential is
        # exported. The fixed stage is enough to request private diagnostics.
        receipt['failed_stage'] = stage
        receipt['failure_type'] = type(error).__name__ if type(error).__name__ in {'Blocked', 'OSError', 'PermissionError', 'FileNotFoundError', 'KeyError', 'ValueError', 'TypeError'} else 'OTHER'
        if isinstance(error, o.Blocked):
            reasons = {'Integration source must be clean': 'DIRTY_HARNESS',
                       'Harness revision unavailable': 'HARNESS_REVISION_UNAVAILABLE',
                       'Runtime source checkout is dirty': 'DIRTY_SOURCE',
                       'Runtime source checkout mismatch': 'SOURCE_HEAD_MISMATCH'}
            if str(error) in reasons:
                receipt['failure_class'] = reasons[str(error)]
        raise
    finally:
        # If materialisation failed after writing its session, still clean it.
        if o.SESSION.exists() and project is None:
            project = o.current()[0]['project']
        try:
            cleanup()
            receipt['teardown_verified'] = True
            receipt['passed'] = receipt.get('smoke_checks_passed') is True
        except Exception:
            receipt['failed_stage'] = 'teardown'
            receipt['passed'] = False
            raise
        finally:
            if project:
                receipt['ended_at'] = datetime.now(timezone.utc).isoformat()
                write_receipt(project, receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'run', 'down'])
    parser.add_argument('--package-token-stdin', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'down':
            cleanup()
        else:
            value, prerequisite = lab.load()
            if args.action == 'run':
                o.must(args.package_token_stdin, 'Use private stdin for package-read authentication')
                # No environment export or command-line credential; never shell
                # source this input. A Codespace may pipe its existing read token.
                token = sys.stdin.read(4098).removesuffix('\n')
                run(value, prerequisite, token)
                print('INT-03 connected identity smoke PASS; full INT-03/staging/production NOT ACCEPTED')
            else:
                print('INT-03 source preflight PASS; connected execution NOT VERIFIED')
        return 0
    except (Exception, KeyboardInterrupt):
        print('INT-03 identity run failed; inspect sanitized stage receipt; no acceptance claimed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
