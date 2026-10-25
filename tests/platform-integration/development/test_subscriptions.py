"""Evidence/refusal regressions; these mocks never certify native runtime."""
import copy
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
