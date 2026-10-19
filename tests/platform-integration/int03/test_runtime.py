"""Boundary/fault tests. Mocks here never count as a connected qualification."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
spec = importlib.util.spec_from_file_location('int03_connected', BASE / 'run.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
o = m.o
lab = m.lab


def consumer(sources):
    return {'schema': 'nabhold.identity-smoke.observation.v1', 'runId': 'test', 'startedAt': 'test',
        'endedAt': 'test', 'profile': 'keycloak-identity-smoke', 'syntheticIdentities': True,
        'nabhold': {'sha': sources['nabhold'], 'worktree': 'clean'},
        'declaredDependencies': {k: sources[v] for k, v in [('infrastructure', 'infrastructure'),
            ('iam', 'baobab-iam'), ('cp', 'baobab-cp'), ('shared', 'shared')]},
        'dependencyRuntimeAttested': False, 'acceptanceClaimed': False, 'outcome': 'PASS',
        'processSucceeded': True, 'observations': {'complete': True, 'invalid': False,
            'results': {key: 'passed' for key in m.IDS}}}


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.sources = {name: str(n) * 40 for n, name in enumerate(
            ['infrastructure', 'baobab-iam', 'baobab-cp', 'shared', 'nabhold'], 1)}
        self.good = consumer(self.sources)

    def test_fixed_success_projection_never_copies_supplied_ids_or_text(self):
        result = m.smoke_projection(json.dumps(self.good), self.sources)
        self.assertEqual(result['scenarios'], {key: 'PASS' for key in m.IDS})
        self.assertEqual(set(result), {'scenarios', 'consumer_receipt_sha256'})
        self.assertNotIn('test', json.dumps(result))

    def test_each_missing_failed_and_nonboolean_observation_denies(self):
        for key in m.IDS:
            for status in ['failed', 'skipped', 'timedOut', 'notRun', 'PASS', True, None]:
                bad = copy.deepcopy(self.good)
                bad['observations']['results'][key] = status
                with self.assertRaises(o.Blocked):
                    m.smoke_projection(json.dumps(bad), self.sources)
            bad = copy.deepcopy(self.good)
            del bad['observations']['results'][key]
            with self.assertRaises(o.Blocked):
                m.smoke_projection(json.dumps(bad), self.sources)
        for key in ['processSucceeded', 'syntheticIdentities']:
            for value in [1, 'true', False]:
                bad = copy.deepcopy(self.good); bad[key] = value
                with self.assertRaises(o.Blocked):
                    m.smoke_projection(json.dumps(bad), self.sources)

    def test_extra_fields_duplicate_json_pin_drift_and_acceptance_claims_deny(self):
        for transform in [lambda r: r.update(secret='must-not-copy'),
            lambda r: r['declaredDependencies'].update(cp='f' * 40),
            lambda r: r.update(nabhold={'sha': 'f' * 40, 'worktree': 'clean'}),
            lambda r: r.update(dependencyRuntimeAttested=True),
            lambda r: r.update(acceptanceClaimed=True),
            lambda r: r['observations'].update(complete=False),
            lambda r: r['observations'].update(invalid=True),
            lambda r: r['observations']['results'].update(unknown='passed')]:
            bad = copy.deepcopy(self.good); transform(bad)
            with self.assertRaises(o.Blocked):
                m.smoke_projection(json.dumps(bad), self.sources)
        with self.assertRaises(m.handoff.Refused):
            m.smoke_projection('{"schema":1,"schema":2}', self.sources)
        with self.assertRaises(o.Blocked):
            m.smoke_projection(' ' * 16385, self.sources)


class RuntimeTests(unittest.TestCase):
    def test_overlay_does_not_change_frozen_baseline_and_has_separate_session(self):
        before = (lab.PREVIOUS / 'lock.json').read_bytes()
        value, prerequisite = lab.load()
        self.assertEqual((lab.PREVIOUS / 'lock.json').read_bytes(), before)
        self.assertEqual(prerequisite['sources']['baobab-iam'], value['sources']['baobab-iam'])
        self.assertEqual(o.SESSION.name, 'int03-session.json')
        self.assertFalse(value['full_int03_acceptance'])
        with patch.dict(os.environ, {'INT02_CANDIDATE_SHA': 'f' * 40}):
            with self.assertRaises(o.Blocked):
                lab.load()

    def test_compose_includes_both_files_and_uses_private_stdin(self):
        with patch.object(o, 'execute', return_value='safe') as execute:
            result = lab.compose({'project': 'l4-' + 'a' * 16}, Path('/private/env'),
                                 'exec', '-T', 'keycloak', 'bash', stdin='private fixture', capture=True)
        args = execute.call_args
        self.assertIn(str(lab.PREVIOUS / 'compose.yaml'), args.args[0])
        self.assertIn(str(BASE / 'compose.yaml'), args.args[0])
        self.assertNotIn('private fixture', args.args[0])
        self.assertEqual(args.kwargs['input_text'], 'private fixture')
        self.assertEqual(result, 'safe')

    def test_tls_has_distinct_valid_hostname_leaves_and_no_retained_signer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); lab.tls(root / 'tls')
            self.assertFalse((root / 'int03-ca.key').exists())
            self.assertFalse(list(root.glob('*.csr')))
            self.assertFalse(list(root.glob('*.ext')))
            self.assertFalse((root / 'tls/redis.key').exists())
            for name, folder, hostname in [('edge', 'tls', 'nabhold.int03.test'),
                                            ('redis', 'redis-tls', 'redis.int03.test')]:
                leaf = root / folder
                self.assertEqual((leaf / (name + '.key')).stat().st_mode & 0o777, 0o600)
                subprocess.run(['openssl', 'verify', '-CAfile', str(root / 'tls/ca.pem'),
                    '-verify_hostname', hostname, str(leaf / (name + '.pem'))], check=True, capture_output=True)
            self.assertNotEqual((root / 'tls/edge.key').read_bytes(), (root / 'redis-tls/redis.key').read_bytes())

    def test_signer_is_destroyed_on_issuance_failure(self):
        actual = o.execute
        def fail(args, **kwargs):
            if 'x509' in args and '-req' in args:
                raise o.Blocked('injected')
            return actual(args, **kwargs)
        with tempfile.TemporaryDirectory() as tmp, patch.object(o, 'execute', side_effect=fail):
            with self.assertRaises(o.Blocked):
                lab.tls(Path(tmp) / 'tls')
            self.assertFalse((Path(tmp) / 'int03-ca.key').exists())

    def test_services_cannot_read_package_token_or_admin_runtime_file(self):
        text = (BASE / 'compose.yaml').read_text()
        self.assertNotIn('${INT03_RUNTIME_HOST}:${INT03_RUNTIME_PATH}', text)
        self.assertNotIn('runtime.env:', text)
        self.assertNotIn('npm_token:', text.split('secrets:')[0])
        self.assertIn('int03-bundle/prepared/users.acl:/run/int03/users.acl:ro', text)
        self.assertIn('--tls-port', text)
        self.assertIn('--port\n      - "0"', text)

    def test_cleanup_keeps_state_when_any_resource_remains(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); session = directory / 'session.json'; session.write_text('{}')
            env = directory / 'runtime.env'; env.write_text('L4_IAM_IMAGE=l4-iam-l4-' + 'a'*16 + '\n')
            with patch.object(o, 'SESSION', session), patch.object(o, 'current', return_value=(
                {'project': 'l4-' + 'a'*16}, directory, env)), patch.object(lab, 'compose'), \
                patch.object(o, 'execute', return_value='leftover'), patch.object(o, 'down') as down:
                with self.assertRaises(o.Blocked):
                    m.cleanup()
                down.assert_not_called()
                self.assertTrue(session.exists())

    def test_run_cannot_claim_pass_after_cleanup_failure(self):
        value, prerequisite = lab.load()
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); (directory / 'npm-token').write_text('test-read-token')
            session = directory / 'session.json'; session.write_text('{}')
            p = {'project': 'l4-'+'a'*16, 'sources': {**prerequisite['sources'], 'nabhold': value['sources']['nabhold']}}
            good = json.dumps(consumer(p['sources']))
            with patch.object(lab, 'materialise'), patch.object(o, 'current', return_value=(p, directory, directory/'runtime.env')), \
                patch.object(o, 'SESSION', session), patch.object(lab, 'compose', side_effect=lambda *a, **k:
                    value['sources']['nabhold'] if 'rev-parse' in a else good if 'run' in a else ''), \
                patch.dict(os.environ, {'INT03_REGISTRY_USERNAME': 'fixture-owner'}), patch.object(o, 'execute', return_value=''), \
                patch.object(o, 'up'), patch.object(o, 'test'), patch.object(m, 'provision'), \
                patch.object(lab, 'source_manifest', return_value={}), patch.object(m, 'cleanup', side_effect=o.Blocked('failed')), \
                patch.object(m, 'write_receipt') as write:
                with self.assertRaises(o.Blocked):
                    m.run(value, prerequisite, 'synthetic-read-token')
                receipt = write.call_args.args[1]
                self.assertTrue(receipt['smoke_checks_passed'])
                self.assertFalse(receipt['passed'])
                self.assertFalse(receipt['teardown_verified'])
                self.assertFalse(receipt['full_int03_accepted'])
                self.assertEqual((directory/'npm-token').read_text(), '')

    def test_atomic_recovery_handle_preserves_previous_content_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'runtime.env'; path.write_text('previous')
            with patch.object(lab.os, 'replace', side_effect=OSError('injected')):
                with self.assertRaises(OSError):
                    lab.replace_private(path, 'new secret')
            self.assertEqual(path.read_text(), 'previous')
            self.assertEqual(list(Path(tmp).iterdir()), [path])
            lab.replace_private(path, 'new secret')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.read_text(), 'new secret')

    def test_build_failure_classes_never_echo_supplied_output(self):
        self.assertEqual(lab.build_class('ERR_PNPM_FETCH_403 private-token'), 'PACKAGE_READ_FORBIDDEN')
        self.assertEqual(lab.build_class('unrecognized private-token'), 'OTHER')


if __name__ == '__main__':
    unittest.main()
