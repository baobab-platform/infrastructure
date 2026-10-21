"""Orchestrator/source tests only; actual CMS/PG probes run in their own CI job."""
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml
import cms_provider as provider


class CMSProvider(unittest.TestCase):
    def observation(self, action='seed'):
        return {'schema': 'cms.int03.fixture.v1', 'run_id': '0123456789abcdef', 'action': action, 'converged': True,
                'database_version_num': 170011, 'states': {'home': 'draft', **dict.fromkeys(['navigation', 'footer', 'site-settings', 'group-profile'], 'DRAFT')},
                'canonical_references': dict.fromkeys(['tenant', 'organisation', 'legalEntity', 'market', 'digitalEstate'], 'UNRESOLVED'),
                'evidence_class': 'CMS_COMPONENT_SYNTHETIC_DATA', 'human_editorial_approval': False, 'identities_created': False,
                'cp_issuance_proven': False, 'connected_qualification': False, 'full_int03_acceptance': False, 'production_authorized': False}

    def test_component_composition_is_real_source_private_storage_and_no_identity(self):
        doc = yaml.safe_load((provider.BASE / 'cms-compose.yaml').read_text())
        self.assertTrue(doc['networks']['lab']['internal'])
        self.assertEqual(set(doc['services']), {'cms-db', 'cms-tool', 'cms', 'cms-probe'})
        for service in doc['services'].values():
            self.assertNotIn('ports', service)
        self.assertEqual(doc['services']['cms']['build']['target'], 'runtime')
        self.assertEqual(doc['services']['cms-tool']['build']['target'], 'build')
        self.assertTrue(doc['services']['cms']['read_only'])
        self.assertEqual(doc['services']['cms']['tmpfs'], ['/tmp:mode=1777', '/app/.next/cache:uid=1001,gid=1001'])
        self.assertNotIn('CMS_CONTEXT_VALIDATOR_TOKEN', doc['services']['cms']['environment'])
        self.assertNotIn('CMS_CONTEXT_VALIDATOR_MODE', doc['services']['cms']['environment'])
        self.assertEqual(doc['services']['cms-db']['volumes'], ['cmsdata:/var/lib/postgresql/data'])

    def test_duplicate_observations_and_unresolved_boundary_crossings_refuse(self):
        with self.assertRaises(Exception):
            provider.document('{"schema":"x","schema":"y"}', 'y')
        value = self.observation()
        p = {'run_id': value['run_id']}
        for changed in [{}, {'identities_created': True}, {'cp_issuance_proven': True}, {'connected_qualification': True},
                        {'human_editorial_approval': True}, {'full_int03_acceptance': True}, {'production_authorized': True},
                        {'database_version_num': 160015}, {'database_version_num': True},
                        {'canonical_references': {**value['canonical_references'], 'tenant': 'tn_invented'}}]:
            candidate = {**deepcopy(value), **changed}
            with patch.object(provider, 'compose', return_value=json.dumps(candidate)):
                if changed:
                    with self.assertRaises(Exception):
                        provider.fixture(p, Path('/unused'), 'seed')
                else:
                    self.assertTrue(provider.fixture(p, Path('/unused'), 'seed')['passed'])
        wrong = deepcopy(value)
        wrong['states']['home'] = 'published'
        with patch.object(provider, 'compose', return_value=json.dumps(wrong)), self.assertRaises(Exception):
            provider.fixture(p, Path('/unused'), 'seed')

    def test_cleanup_is_project_scoped_and_retains_recovery_on_incomplete_destruction(self):
        for leftover in [False, True]:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                directory = root / 'cms-int03-0123456789abcdef'
                directory.mkdir()
                envfile = directory / 'compose.env'
                envfile.write_text('private synthetic fixture environment')
                session = root / 'session.json'
                session.write_text('{}')
                p = {'project': directory.name, 'run_id': '0123456789abcdef'}
                def execute(args, **_kwargs):
                    if 'com.docker.compose.project=' + p['project'] in args[-1]:
                        return 'resource-still-present' if leftover else ''
                    if args[:3] == ['docker', 'image', 'ls']:
                        return 'run-owned-image'
                    return ''
                with patch.object(provider, 'SESSION', session), patch.object(provider, 'current', return_value=(p, directory, envfile)), \
                        patch.object(provider, 'compose') as compose, patch.object(provider.o, 'execute', side_effect=execute) as calls:
                    if leftover:
                        with self.assertRaises(Exception):
                            provider.cleanup()
                        self.assertTrue(session.exists())
                        self.assertTrue(directory.exists())
                    else:
                        provider.cleanup()
                        self.assertFalse(session.exists())
                        self.assertFalse(directory.exists())
                        image_removals = [c.args[0][-1] for c in calls.call_args_list if c.args[0][:3] == ['docker', 'image', 'rm']]
                        self.assertEqual(image_removals, ['int03-cms-runtime:0123456789abcdef', 'int03-cms-tool:0123456789abcdef'])
                    compose.assert_not_called()

    def test_failure_and_interruption_always_cleanup_and_never_qualify(self):
        for cause in [RuntimeError('private dependency failure'), InterruptedError('interrupted')]:
            with tempfile.TemporaryDirectory() as temporary, patch.object(provider, 'load', return_value={}), \
                    patch.object(provider, 'materialise', side_effect=cause), patch.object(provider, 'cleanup') as cleanup, \
                    patch.object(provider.o, 'EVIDENCE', Path(temporary)):
                self.assertEqual(provider.run(), 1)
                cleanup.assert_called_once()
                completed = list(Path(temporary).glob('*/completed'))
                self.assertEqual(len(completed), 1)
                receipt = json.loads((completed[0] / 'receipt.json').read_text())
                self.assertEqual(receipt['component_outcome'], 'FAIL')
                self.assertEqual(receipt['teardown'], 'PASS')
                digest = hashlib.sha256((completed[0] / 'receipt.json').read_bytes()).hexdigest()
                self.assertEqual((completed[0] / 'receipt.sha256').read_text(), digest + '  receipt.json\n')
                self.assertFalse(receipt['qualified'])
                self.assertEqual(set(receipt['cases'].values()), {'BLOCKED'})
                self.assertEqual(len(receipt['cases']), 14)
                self.assertNotIn('private dependency failure', (completed[0] / 'receipt.json').read_text())

    def test_lost_recovery_handle_still_destroys_only_in_memory_owned_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            p = {'project': 'cms-int03-0123456789abcdef', 'run_id': '0123456789abcdef'}
            directory = root / p['project']
            directory.mkdir(mode=0o700)
            removed = []
            def execute(args, **_kwargs):
                if args[:3] == ['docker', 'rm', '-f']:
                    removed.append(args[-1])
                if args[:3] == ['docker', 'ps', '-aq'] and not removed:
                    return 'abcdef012345'
                return ''
            with patch.object(provider, 'SESSION', root / 'missing.json'), patch.object(provider.o, 'STATE', root), \
                    patch.object(provider.o, 'execute', side_effect=execute) as calls:
                provider.cleanup(p)
                self.assertEqual(removed, ['abcdef012345'])
                self.assertFalse(directory.exists())
                queries = [c.args[0] for c in calls.call_args_list if '--filter' in c.args[0]]
                self.assertTrue(all('label=com.docker.compose.project=' + p['project'] in q for q in queries
                                    if q[:3] != ['docker', 'image', 'ls']))
                directory.mkdir(mode=0o755)
                with self.assertRaises(Exception):
                    provider.cleanup(p)

    def test_receipt_publication_failure_cannot_leave_a_completed_pair(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(provider, 'load', return_value={}), \
                patch.object(provider, 'materialise', side_effect=InterruptedError()), patch.object(provider, 'cleanup'), \
                patch.object(provider.o, 'EVIDENCE', Path(temporary)), \
                patch.object(provider.os, 'fsync', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                provider.run()
            self.assertEqual(list(Path(temporary).glob('*/completed/*')), [])
            self.assertEqual(list(Path(temporary).glob('*/.pending/*')), [])

    def test_open_or_refused_registry_cannot_start_held_component(self):
        for verdict in ['OPEN', 'REFUSED']:
            with tempfile.TemporaryDirectory() as temporary, patch.object(provider.o, 'STATE', Path(temporary)), \
                    patch.object(provider, 'SESSION', Path(temporary) / 'session.json'), \
                    patch.object(provider, 'pinned_checkout'), \
                    patch.object(provider.cms_gate, 'evaluate', return_value={'gate': {'verdict': verdict}}), \
                    patch.object(provider.o, 'execute') as execute:
                with self.assertRaises(Exception):
                    provider.materialise(provider.load())
                execute.assert_not_called()
                self.assertTrue(provider.SESSION.exists(), 'failed preparation retains its private recovery handle')

    def test_stuck_owned_container_does_not_prevent_other_resource_removals(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'cms-int03-0123456789abcdef'
            directory.mkdir(mode=0o700)
            p = {'project': directory.name, 'run_id': '0123456789abcdef', 'deadline': 1, 'source_sha': 'a' * 40}
            resources = {'container': ['a' * 12, 'b' * 12], 'network': ['c' * 12], 'volume': [directory.name + '_cmsdata']}
            def execute(args, **_kwargs):
                if args[:3] == ['docker', 'ps', '-aq']:
                    return '\n'.join(resources['container'])
                for kind in ['network', 'volume']:
                    if args[:4] == ['docker', kind, 'ls', '-q']:
                        return '\n'.join(resources[kind])
                    if args[:3] == ['docker', kind, 'rm']:
                        resources[kind].remove(args[-1])
                if args[:3] == ['docker', 'rm', '-f']:
                    if args[-1] == 'a' * 12:
                        raise RuntimeError('synthetic stuck resource')
                    resources['container'].remove(args[-1])
                if args[:3] == ['docker', 'image', 'ls']:
                    return 'owned-image'
                return ''
            with patch.object(provider, 'SESSION', root / 'lost.json'), patch.object(provider.o, 'STATE', root), \
                    patch.object(provider.o, 'execute', side_effect=execute) as calls:
                with self.assertRaises(Exception):
                    provider.cleanup(p)
                self.assertEqual(resources, {'container': ['a' * 12], 'network': [], 'volume': []})
                self.assertEqual(len([c for c in calls.call_args_list if c.args[0][:3] == ['docker', 'image', 'rm']]), 2)
                self.assertEqual(json.loads(provider.SESSION.read_text()), p)
                self.assertTrue(directory.exists())


if __name__ == '__main__':
    unittest.main()
