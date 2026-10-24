"""Fail-closed evidence/custody regressions; never native qualification evidence."""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import dev
import int03c_contract as contract

RUN = 'a' * 32


def pending_report():
    report = contract.fresh(RUN)
    for name, row in report['cases'].items():
        if name != 'complete-teardown':
            row['assertions'] = dict.fromkeys(row['assertions'], True)
            row.update(result='PASS', reason='OBSERVED')
    row = report['cases']['complete-teardown']
    for key in row['assertions'].keys() - {'accepting_runtime_absent', 'owned_resources_absent', 'private_state_absent'}:
        row['assertions'][key] = True
    row['reason'] = 'TEARDOWN_PENDING'
    return report


class Int03CTests(unittest.TestCase):
    def test_exact_original_cases_and_closed_partial_results(self):
        self.assertEqual(set(contract.ASSERTIONS), {'issuer-issuance-and-readback', 'current-cp-principal-and-link',
            'wrong-audience-denial', 'wrong-tenant-denial', 'issuer-revocation-before-expiry',
            'cp-principal-deactivation', 'complete-teardown'})
        contract.validate(pending_report(), RUN)
        with self.assertRaises(ValueError): contract.validate(pending_report(), RUN, complete=True)
        for change in (lambda r: r['cases'].pop('wrong-tenant-denial'),
                       lambda r: r['cases']['complete-teardown'].update(result='PASS'),
                       lambda r: r.update(protected_acceptance=True),
                       lambda r: r.update(run_id='b'*32),
                       lambda r: r.update(raw_provider_body='private'),
                       lambda r: r['cases']['issuer-revocation-before-expiry']['assertions'].update(unexpired_after_denial=1)):
            report = pending_report(); change(report)
            with self.assertRaises(ValueError): contract.validate(report, RUN)

    def test_failed_retry_cannot_reuse_a_stale_report(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); path = directory / 'int03c-report.json'
            dev.write(path, pending_report())
            state = {'phase': 'TESTED', 'int03c': pending_report()}
            with patch.object(dev, 'current', return_value=(directory, state)), \
                 patch.object(dev, 'verify_sources'), patch.object(dev, 'persist'), \
                 patch.object(dev, 'compose', side_effect=dev.Refused('COMMAND_FAILED')):
                with self.assertRaises(dev.Refused): dev.qualify_int03c(RUN)
            self.assertFalse(path.exists())
            self.assertTrue(all(row['result'] == 'BLOCKED' for row in state['int03c']['cases'].values()))

    def test_probe_failure_retains_closed_partial_failure_for_custody(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp); state = {'phase': 'TESTED'}
            partial = contract.fresh(RUN)
            partial['cases']['issuer-issuance-and-readback'].update(result='FAIL', reason='SERVICE_UNAVAILABLE')
            def fail(*args, **kwargs):
                dev.write(directory / 'int03c-report.json', partial)
                raise dev.Refused('COMMAND_FAILED')
            with patch.object(dev, 'current', return_value=(directory, state)), \
                 patch.object(dev, 'verify_sources'), patch.object(dev, 'persist'), patch.object(dev, 'compose', side_effect=fail):
                with self.assertRaises(dev.Refused): dev.qualify_int03c(RUN)
            self.assertEqual(state['int03c'], partial)

    def test_teardown_qualifies_only_after_all_readbacks_and_state_removal(self):
        for complete_provider, survivors in ((True, False), (False, False), (True, True)):
            with self.subTest(complete_provider=complete_provider, survivors=survivors), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); state_dir = root / 'state'; state_dir.mkdir(mode=0o700)
                directory = state_dir / RUN; directory.mkdir(mode=0o700)
                report = pending_report()
                if not complete_provider:
                    report['cases']['complete-teardown']['assertions']['both_issuer_clients_absent'] = False
                data = {'run_id': RUN, 'harness_sha': 'b'*40, 'sources': {}, 'image_ids': {},
                        'lock_sha256': 'c'*64, 'tests': True, 'int03c': report}
                dev.write(directory / 'state.json', data)
                resources = [('volume', 'owned', {})] if survivors else []
                with patch.object(dev, 'STATE', state_dir), patch.object(dev, 'EVIDENCE', root / 'evidence'), \
                     patch.object(dev, 'resources', return_value=resources), patch.object(dev, 'call'):
                    if survivors:
                        with self.assertRaises(dev.Refused): dev.down(RUN)
                        self.assertTrue(directory.exists())
                        self.assertFalse((root / 'evidence').exists())
                    else:
                        dev.down(RUN)
                        self.assertFalse(directory.exists())
                        receipt = dev.read(root / 'evidence' / ('dev01-' + RUN) / 'completed/receipt.json')
                        self.assertIs(receipt['int03c_qualified'], complete_provider)
                        self.assertIs(receipt['protected_acceptance'], False)
                        self.assertIs(receipt['production_authorized'], False)
                        if complete_provider: contract.validate(receipt['int03c'], RUN, complete=True)


if __name__ == '__main__': unittest.main()
