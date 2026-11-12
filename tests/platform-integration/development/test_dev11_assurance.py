"""DEV-11 synthetic source tests; not live cross-engine proof."""
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dev11_assurance import HOPS, VERSION, Refused, route, traceparent, verify_chain, unique_pairs

class Dev11AssuranceTests(unittest.TestCase):
    def sample(self):
        trace = 'a' * 32
        correlation = 'a1234567-89ab-cdef-0123-456789abcdef'
        hops = []
        for i, role in enumerate(HOPS, 1):
            hops.append({'service_role': role,
                'traceparent': f'00-{trace}-{i:016x}-01',
                'parent_span_id': f'{i-1:016x}' if i > 1 else None,
                'correlation_id': correlation, 'result': 'PASS', 'cause': 'NONE'})
        return {'schema': VERSION, 'source_sha': 'b' * 40,
                'profile': 'DEV-07', 'scenario': 'DEV07-TRACE-01',
                'correlation_id': correlation, 'hops': hops,
                'runtime_observed': True, 'teardown_verified': True,
                'evidence_class': 'REAL_COMPONENT_SYNTHETIC_DATA'}

    def test_closed_chain(self):
        out = verify_chain(self.sample())
        self.assertTrue(out['trace_chain_valid'])
        self.assertFalse(out['runtime_qualified'])
        self.assertTrue(out['teardown_verified'])
        self.assertFalse(out['protected_acceptance'])
        self.assertNotIn('hops', out)
        self.assertNotIn('correlation_id', out)

    def test_missing_runtime_or_teardown_never_qualifies(self):
        for edit in (lambda x: x.update(evidence_class='SOURCE'),
                     lambda x: x.update(runtime_observed=False),
                     lambda x: x.update(teardown_verified=False)):
            item = self.sample()
            edit(item)
            self.assertFalse(verify_chain(item)['runtime_qualified'])

    def test_blocked_not_run_and_fail_do_not_fake_green(self):
        for status, cause in [('BLOCKED','NATIVE_NOT_IMPLEMENTED'),
                              ('NOT_RUN','NOT_EXECUTED'),
                              ('FAIL','INCORRECT_RESULT')]:
            item = self.sample()
            item['hops'][4].update(result=status,cause=cause)
            result = verify_chain(item)
            self.assertEqual(result['result'], status)
            self.assertFalse(result['runtime_qualified'])
            self.assertEqual(result['cause_codes'], [cause])

    def test_chain_is_bound_to_one_trace_and_parent(self):
        mutations = (
            lambda x: x['hops'][1].update(correlation_id='b'*36),
            lambda x: x['hops'][2].update(parent_span_id='1'*16),
            lambda x: x['hops'][4].update(traceparent='00-'+'b'*32+'-'+'5'*16+'-01'),
            lambda x: x['hops'][3].update(traceparent=x['hops'][0]['traceparent']),
            lambda x: x['hops'].pop(),
            lambda x: x['hops'][1].update(service_role='unexpected'),
        )
        for mutate in mutations:
            item = self.sample()
            mutate(item)
            with self.assertRaises(Refused):
                verify_chain(item)

    def test_secret_fields_and_free_text_refused_without_echo(self):
        for mutate in (
            lambda x: x.update(authorization='Bearer confidential-token'),
            lambda x: x['hops'][0].update(headers={'authorization':'Bearer confidential-token'}),
            lambda x: x['hops'][0].update(error_message='customer@private.example'),
            lambda x: x['hops'][1].update(cause='raw error with password'),
        ):
            item = self.sample()
            mutate(item)
            with self.assertRaises(Refused) as error:
                verify_chain(item)
            self.assertNotIn('confidential',str(error.exception))
            self.assertNotIn('customer@',str(error.exception))

    def test_traceparent_malformed_zero_or_injected_refused(self):
        for value in ('00-'+'0'*32+'-'+'1'*16+'-01',
                      '00-'+'1'*32+'-'+'0'*16+'-01',
                      'ff-'+'1'*32+'-'+'1'*16+'-01',
                      '00-'+'G'*32+'-'+'1'*16+'-01',
                      '00-'+'1'*32+'-'+'1'*16+'-01\nSecret: token',
                      '00-'+'1'*32+'-'+'1'*16+'-1'):
            with self.assertRaises(Refused):
                traceparent(value)

    def test_buyer_changes_route_to_authority_and_bff(self):
        result = route(['tests/platform-integration/development/buyer_identity.py'])
        self.assertEqual(result['affected_profiles'], ['DEV-01-04','DEV-07'])
        self.assertEqual(result['routing_result'], 'PLANNED_NOT_EXECUTED')
        self.assertFalse(result['runtime_qualified'])

    def test_unknown_path_and_workflows_fail_closed_to_full(self):
        self.assertEqual(len(route(['new-engine/adapter.py'])['affected_profiles']), 10)
        self.assertEqual(len(route(['.github/workflows/platform-development.yml'])['affected_profiles']), 10)

    def test_docs_only_not_runtime_pass(self):
        result = route(['docs/testing/README.md'])
        self.assertEqual(result['affected_profiles'],[])
        self.assertFalse(result['runtime_qualified'])

    def test_full_nightly_includes_browser_owner(self):
        result = route(None,full=True)
        self.assertIn('ESTATE-BROWSER',result['external_owner_checks'])
        self.assertIn('DEV-14-15',result['affected_profiles'])
        self.assertFalse(result['runtime_qualified'])

    def test_duplicate_receipt_keys_are_refused_before_validation(self):
        with self.assertRaises(Refused):
            json.loads('{"source_sha":"a","source_sha":"b"}', object_pairs_hook=unique_pairs)

    def test_untrusted_path_not_echoed(self):
        for name in ('../private/.env','/private/access','secret\nAuthorization: token'):
            with self.assertRaises(Refused):
                route([name])

if __name__ == '__main__':
    unittest.main()
