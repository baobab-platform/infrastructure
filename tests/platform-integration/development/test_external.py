"""Failure/custody contracts only; never substitute for actual INT-07 proof."""
import copy
import importlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import dev
import external_contract as contract
import external_vertical as external

class ExternalContracts(unittest.TestCase):
    def test_closed_original_obligations_cannot_be_omitted_or_promoted(self):
        run='a'*32;value=contract.fresh(run)
        for mutation in (lambda r:r['cases'].pop('zero-estates'),lambda r:r.update(int07_qualified=True),
            lambda r:r.update(protected_acceptance=True),lambda r:r['component_checks'].update(access_token=True),
            lambda r:r['cases']['teardown'].update(result='PASS')):
            changed=copy.deepcopy(value);mutation(changed)
            with self.assertRaises(ValueError):contract.validate(changed,run)

    def test_native_sources_are_immutable_and_no_estate_dependency_is_added(self):
        value=external.lock()
        self.assertEqual(set(value['source']),{'baobab-pulse'})
        self.assertRegex(value['source']['baobab-pulse'],r'^[0-9a-f]{40}$')
        self.assertIn('@sha256:',value['qdrant'])

    def test_readback_rejects_an_estate_even_when_other_facts_pass(self):
        state={'run_id':'a'*32,'bootstrap_lease':300}
        facts={'schema':'baobab.development-external-api.v1','run_id':state['run_id'],
            'zero_estates':True,'independent_tenant':True,'own_assignment':True,
            'validator_unassigned':True,'synthetic_only':True,'protected_acceptance':False}
        for changed in ({}, {'zero_estates':False}, {'own_assignment':False}, {'protected_acceptance':True}, {'arbitrary':True}):
            with self.subTest(changed=changed),patch.object(dev,'read',return_value={'maker':'actual-maker','checker':'actual-checker'}), \
                 patch.object(dev,'compose',return_value=json.dumps({**facts,**changed})) as compose:
                if changed:
                    with self.assertRaises(dev.Refused):external.check_facts(Path('/private'),state)
                else:
                    self.assertEqual(external.check_facts(Path('/private'),state),facts)
                    self.assertIn('--check-external-api',compose.call_args.args)

    def test_teardown_cannot_promote_missing_canonical_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);state=root/'state';run='a'*32;directory=state/run;directory.mkdir(parents=True,mode=0o700);state.chmod(0o700)
            report=contract.fresh(run)
            report['component_checks'].update(native_clients_deleted=True,native_tokens_inactive=True)
            report['cases']['teardown']={'result':'BLOCKED','reason':'TEARDOWN_PENDING'}
            dev.write(directory/'state.json',{'run_id':run,'harness_sha':'b'*40,'sources':{},'image_ids':{},'tests':True,
                'lock_sha256':'c'*64,'external':report})
            with patch.object(dev,'STATE',state),patch.object(dev,'EVIDENCE',root/'evidence'),patch.object(dev,'resources',return_value=[]):
                dev.down(run)
            receipt=dev.read(root/'evidence'/('dev01-'+run)/'completed/receipt.json')
            self.assertEqual(receipt['external']['cases']['teardown']['result'],'PASS')
            self.assertFalse(receipt['external']['int07_qualified'])
            self.assertEqual(receipt['external']['cases']['bound-resource-and-audited-effect']['result'],'BLOCKED')
            self.assertFalse(directory.exists())

    def test_failure_keeps_case_attribution_and_never_echoes_token(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('external_probe')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);report=contract.fresh('a'*32)
            report['cases']['zero-estates']={'result':'PASS','reason':'OBSERVED'}
            (root/'external-report.json').write_text(json.dumps(report))
            with patch.dict('os.environ',{'DEV01_RUN_ID':'a'*32}),patch.object(probe.p,'ROOT',root), \
                 patch.object(probe,'config',return_value=({}, {}, {})),patch.object(probe,'search',side_effect=RuntimeError('private-bearer')):
                with self.assertRaises(SystemExit) as error:probe.main('outage')
                self.assertNotIn('private-bearer',str(error.exception))
            saved=json.loads((root/'external-report.json').read_text())
            self.assertEqual(saved['cases']['zero-estates']['result'],'PASS')
            self.assertEqual(saved['cases']['dependency-outage-and-recovery']['result'],'FAIL')

    def test_recovery_and_teardown_failure_preserve_prior_identity_observation(self):
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):
            probe=importlib.import_module('external_probe')
        for action,case in (('restored','dependency-outage-and-recovery'),('finish','teardown')):
            with self.subTest(action=action),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);report=contract.fresh('a'*32)
                report['cases']['independent-registered-workload']={'result':'PASS','reason':'OBSERVED'}
                (root/'external-report.json').write_text(json.dumps(report))
                with patch.dict('os.environ',{'DEV01_RUN_ID':'a'*32}),patch.object(probe.p,'ROOT',root), \
                     patch.object(probe,'config',return_value=({}, {}, {})), \
                     patch.object(probe,'context',side_effect=ValueError('private-context')), \
                     patch.object(probe.p,'api',side_effect=ValueError('private-provider')):
                    with self.assertRaises(SystemExit):probe.main(action)
                saved=json.loads((root/'external-report.json').read_text())
                self.assertEqual(saved['cases']['independent-registered-workload']['result'],'PASS')
                self.assertEqual(saved['cases'][case]['result'],'FAIL')

if __name__=='__main__':unittest.main()
