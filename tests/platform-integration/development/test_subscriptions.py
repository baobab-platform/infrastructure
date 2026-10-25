"""Evidence/refusal regressions; these mocks never certify native runtime."""
import copy
import hashlib
import os
from pathlib import Path
from unittest.mock import patch
import unittest
import dev
import subscriptions_contract as contract

class SubscriptionContracts(unittest.TestCase):
    def test_inventory_and_independent_internal_gates_cannot_be_promoted(self):
        value=contract.fresh();self.assertEqual(len(value),19)
        for mutate in (lambda v:v.pop('revision-before-replay'),
                       lambda v:v['current-internal-positive'].update(result='PASS',reason='OBSERVED'),
                       lambda v:v['teardown'].update(reason='SKIPPED'),
                       lambda v:v.update(invented={'result':'PASS','reason':'OBSERVED'})):
            changed=copy.deepcopy(value);mutate(changed)
            with self.assertRaises(ValueError):contract.validate(changed)
    def test_new_source_selection_does_not_rewrite_historical_pins(self):
        original=dev.load_lock();current=dev.load_lock('subscriptions-base-lock.json')
        self.assertNotEqual(original['sources']['shared'],current['sources']['shared'])
        self.assertNotEqual(original['sources']['baobab-cp'],current['sources']['baobab-cp'])
        self.assertEqual(original['images'],current['images'])
        with self.assertRaises(dev.Refused):dev.load_lock('../lock.json')

    def test_current_checks_selected_lock_without_comparing_historical_lock(self):
        run='a'*32;sha='b'*40
        state={'run_id':run,'project':'dev01-'+run,'namespace':dev.NAMESPACE,'uid':os.getuid(),
            'environment':'development','deadline':9999999999,'harness_sha':sha,'watcher_pid':123,
            'lock_file':'subscriptions-base-lock.json',
            'lock_sha256':hashlib.sha256((dev.BASE/'subscriptions-base-lock.json').read_bytes()).hexdigest()}
        original=Path.read_bytes
        def raw(path):
            if str(path)=='/proc/123/cmdline':return b'python\0watch\0'+run.encode()+b'\0'
            return original(path)
        with patch.object(dev,'run_dir',return_value=Path('/private-run')),patch.object(dev,'read',return_value=state), \
             patch.object(dev,'source_identity',return_value=sha),patch.object(Path,'read_bytes',raw), \
             patch.dict(os.environ,BAOBAB_ENVIRONMENT='development'):
            self.assertEqual(dev.current(run)[1],state)
            state['lock_sha256']='c'*64
            with self.assertRaises(dev.Refused):dev.current(run)
