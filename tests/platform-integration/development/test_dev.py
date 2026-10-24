"""DEV-01 source/recovery contracts. Mocks here are never runtime evidence."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import adapter
import dev


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.evidence = self.root / 'evidence'
        self.run_id = 'a' * 32
        self.directory = self.state / self.run_id
        self.directory.mkdir(parents=True, mode=0o700)
        self.state.chmod(0o700)
        self.data = {'run_id': self.run_id, 'project': 'dev01-' + self.run_id,
                     'namespace': dev.NAMESPACE, 'uid': os.getuid(), 'gid': os.getgid(),
                     'environment': 'development', 'deadline': int(time.time()) + 600,
                     'harness_sha': 'b' * 40, 'sources': dev.load_lock()['sources'],
                     'lock_sha256': 'c' * 64, 'image_ids': {}, 'images': {}, 'tests': False,
                     'secrets': {'cp_db': 'private-cp', 'iam_db': 'private-iam', 'admin': 'private-admin', 'hook': 'a'*64, 'introspection':'b'*64, 'verifier':'c'*64}}
        self.addCleanup(patch.stopall)
        patch.object(dev, 'STATE', self.state).start()
        patch.object(dev, 'EVIDENCE', self.evidence).start()
        dev.write(self.directory / 'state.json', self.data)

    def test_static_profile_has_no_cms_or_49_dependency(self):
        result = dev.doctor(static=True)
        self.assertEqual(set(result['services']), adapter.SERVICES)
        self.assertFalse(result['cms_required'])
        self.assertFalse(result['protected_acceptance'])

    def test_missing_or_mutable_source_and_digest_are_refused(self):
        for mutate in (lambda d: d['sources'].update(shared='main'),
                       lambda d: d['images'].update(postgres='postgres:17'),
                       lambda d: d.update(protected_acceptance=True),
                       lambda d: d.update(max_lease_seconds=86401)):
            data = dev.load_lock()
            mutate(data)
            with patch.object(Path, 'read_text', return_value=json.dumps(data)):
                with self.assertRaises(dev.Refused):
                    dev.load_lock()

    def test_unknown_environment_never_starts_docker(self):
        for environment in ('', 'ci', 'staging', 'production'):
            with patch.dict(os.environ, {'BAOBAB_ENVIRONMENT': environment}), patch.object(dev, 'call') as call:
                with self.assertRaises(dev.Refused):
                    dev.prepare()
                call.assert_not_called()

    def test_private_atomic_state_and_duplicate_key_refusal(self):
        self.assertEqual(dev.read(self.directory / 'state.json'), self.data)
        self.assertEqual((self.directory / 'state.json').stat().st_mode & 0o777, 0o600)
        (self.directory / 'state.json').write_text('{"phase":"FAILED","phase":"TESTED"}')
        with self.assertRaises(dev.Refused):
            dev.read(self.directory / 'state.json')

    def test_symlink_shared_and_hardlinked_state_refused(self):
        original = self.directory / 'state.json'
        link = self.directory / 'link.json'
        link.symlink_to(original)
        with self.assertRaises(OSError):
            dev.read(link)
        original.chmod(0o644)
        with self.assertRaises(dev.Refused):
            dev.read(original)
        original.chmod(0o600)
        link.unlink()
        os.link(original, link)
        with self.assertRaises(dev.Refused):
            dev.read(original)

    def test_path_traversal_and_shared_run_root_refused(self):
        for run in ('../other', None, 'A' * 32):
            with self.assertRaises(dev.Refused):
                dev.run_dir(run)
        self.state.chmod(0o755)
        with self.assertRaises(dev.Refused):
            dev.run_dir(self.run_id)

    def test_failed_teardown_retains_only_cleanup_handle_for_retry(self):
        with patch.object(dev, 'resources', return_value=[('container', 'abc', {})]), \
             patch.object(dev, 'call', side_effect=dev.Refused('DOCKER_UNAVAILABLE')):
            with self.assertRaises(dev.Refused):
                dev.down(self.run_id)
        self.assertTrue((self.directory / 'state.json').exists())
        with patch.object(dev, 'resources', return_value=[]):
            dev.down(self.run_id)
        self.assertFalse(self.directory.exists())
        receipt = dev.read(self.evidence / ('dev01-' + self.run_id) / 'completed/receipt.json')
        self.assertFalse(receipt['lifecycle_passed'])
        self.assertFalse(receipt['int03c_qualified'])
        self.assertTrue(receipt['teardown_verified'])
        self.assertNotIn('private-admin', json.dumps(receipt))

    def test_surviving_resources_cannot_emit_cleanup_success(self):
        with patch.object(dev, 'resources', return_value=[('volume', 'owned', {})]), patch.object(dev, 'call'):
            with self.assertRaises(dev.Refused):
                dev.down(self.run_id)
        self.assertTrue(self.directory.exists())
        self.assertFalse(self.evidence.exists())

    def test_recovery_finds_orphans_without_env_or_state(self):
        import shutil
        shutil.rmtree(self.directory)
        labels = {'io.baobab.dev.run': self.run_id, 'io.baobab.dev.deadline': str(int(time.time()) - 10)}
        with patch.object(dev, 'resources', return_value=[('volume', 'orphan', labels)]), patch.object(dev, 'down') as down:
            dev.recover()
        down.assert_called_once_with(self.run_id)

    def test_unexpired_other_run_is_not_swept_by_default(self):
        with patch.object(dev, 'resources', return_value=[]), patch.object(dev, 'down') as down:
            dev.recover()
        down.assert_not_called()

    def test_composition_is_private_and_marked_with_one_owner(self):
        images = dev.load_lock()['images']
        self.data['images'] = {'iam': 'owned-iam', 'cp': 'owned-cp'}
        c = adapter.composition(self.data, self.directory, images, dev.NAMESPACE)
        self.assertEqual(set(c['services']), adapter.SERVICES)
        self.assertTrue(c['networks']['lab']['internal'])
        for service in c['services'].values():
            self.assertNotIn('ports', service)
            self.assertNotIn('privileged', service)
            self.assertEqual(service['labels']['io.baobab.dev.run'], self.run_id)
        self.assertNotIn('BAOBAB_DEV_BOOTSTRAP_ENABLED', c['services']['cp']['environment'])

    def test_fixture_report_rejects_incomplete_outcomes_and_authority(self):
        import copy
        outcomes = {'valid_scoped': 'ACTOR_NOT_VERIFIED', 'missing': 'NO_APPLICABLE_MANDATE',
                    'stale': 'REVOKED_OR_EXPIRED', 'revoked': 'REVOKED_OR_EXPIRED',
                    'wrong_market': 'NO_APPLICABLE_MANDATE', 'pending': 'NO_APPLICABLE_MANDATE'}
        outcomes.update({'boundary_wrong_' + key: 'NO_APPLICABLE_MANDATE'
                         for key in ('role', 'activity', 'capability', 'tenant', 'organisation', 'market')})
        report = {'schema': 'baobab.development-fixture-checks.v1', 'run_id': self.run_id,
                  'synthetic_only': True, 'official_actor_verified': False,
                  'provider_permissions_granted': False, 'protected_acceptance': False,
                  'scope': 'DEV02_NON_AUTHORISING_SCOPE_AND_LIFECYCLE',
                  'observations': [{'enterprise': e, 'case': case, 'policy_outcome': outcome, 'passed': True}
                                   for e in ('zuribeans', 'equator-estate') for case, outcome in outcomes.items()]}
        dev.validate_fixture_report(report, self.run_id)
        for mutation in (lambda r: r['observations'].pop(),
                         lambda r: r['observations'].__setitem__(0, r['observations'][1]),
                         lambda r: r['observations'][0].update(policy_outcome='AUTHORIZED'),
                         lambda r: r.update(official_actor_verified=True),
                         lambda r: r.update(run_id='b' * 32)):
            altered = copy.deepcopy(report)
            mutation(altered)
            with self.assertRaises(dev.Refused):
                dev.validate_fixture_report(altered, self.run_id)

    def test_codespaces_mount_mapping_is_explicit(self):
        with patch.dict(os.environ, {'LOCAL_WORKSPACE_FOLDER': '/host/project',
                                   'CONTAINER_WORKSPACE_FOLDER': '/workspaces/project'}):
            self.assertEqual(adapter.host(Path('/workspaces/project/a')), '/host/project/a')
            with self.assertRaises(ValueError):
                adapter.host(Path('/other/a'))

    def test_composition_tampering_fails_before_any_docker_command(self):
        dev.write(self.directory / 'compose.json', {'ports': ['8080:8080']})
        self.data['compose_sha256'] = '0' * 64
        with patch.object(dev, 'call') as call:
            with self.assertRaises(dev.Refused):
                dev.compose(self.directory, self.data, 'up')
            call.assert_not_called()

    def test_expired_and_dead_watchdog_runs_fail_closed(self):
        self.data['deadline'] = int(time.time()) - 1
        dev.write(self.directory / 'state.json', self.data)
        with patch.dict(os.environ, {'BAOBAB_ENVIRONMENT': 'development'}):
            with self.assertRaises(dev.Refused):
                dev.current(self.run_id)

    def test_dependency_source_drift_is_checked_before_build_or_test(self):
        def actual(args, **_):
            repo = Path(args[2]).name
            return self.data['sources'][repo] if args[-1] == 'HEAD' else ' M altered-source'
        with patch.object(dev, 'call', side_effect=actual):
            with self.assertRaisesRegex(dev.Refused, 'DEPENDENCY_SOURCE_DRIFT'):
                dev.verify_sources(self.directory, self.data)

    def test_static_option_cannot_start_a_runtime(self):
        with patch.object(dev, 'prepare') as prepare:
            self.assertEqual(dev.main(['run', '--static']), 2)
        prepare.assert_not_called()

    def test_missing_watchdog_does_not_admit_an_active_lease(self):
        import hashlib
        self.data['lock_sha256'] = hashlib.sha256((dev.BASE / 'lock.json').read_bytes()).hexdigest()
        dev.write(self.directory / 'state.json', self.data)
        with patch.dict(os.environ, {'BAOBAB_ENVIRONMENT': 'development'}), \
             patch.object(dev, 'source_identity', return_value=self.data['harness_sha']):
            with self.assertRaisesRegex(dev.Refused, 'WATCHDOG_REQUIRED'):
                dev.current(self.run_id)


if __name__ == '__main__':
    unittest.main()
