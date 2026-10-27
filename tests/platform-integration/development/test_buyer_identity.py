"""DEV-07 source refusal boundaries; never actual issuer/runtime evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import adapter
import dev
import buyer_identity_contract as c

class BuyerIdentityTests(unittest.TestCase):
    def test_candidate_lock_is_closed_and_uses_current_companion_sources(self):
        lock=dev.load_lock('buyer-identity-base-lock.json')
        self.assertFalse(lock['protected_acceptance'])
        self.assertEqual(lock['sources']['shared'],'2fde03e2f5f3a8a6cbc1e2081b4859fdccc1bb53')
        self.assertEqual(lock['sources']['baobab-iam'],'03d4d7c026d524a265403af9606d0b9e46f71783')
        self.assertEqual(len(lock['sources']),3)
        self.assertTrue(all('@sha256:' in image for image in lock['images'].values()))
    def test_feature_flags_and_owner_module_are_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            state={'run_id':'a'*32,'project':'dev01-'+'a'*32,'uid':1000,'gid':1000,'deadline':int(time.time())+600,
                'secrets':{'cp_db':'private','iam_db':'private','hook':'h'*64,'introspection':'i'*64,'verifier':'v'*64},'images':{'cp':'sha256:'+'a'*64}}
            images=dev.load_lock()['images']
            baseline=adapter.composition(state,directory,images,'namespace')
            self.assertNotIn('BUYER_PRINCIPAL_RESOLUTION_ENABLED',baseline['services']['cp']['environment'])
            candidate=adapter.composition({**state,'buyer_identity_profile':True},directory,images,'namespace')
            env=candidate['services']['cp']['environment']
            self.assertEqual(env['BUYER_SUBJECT_AUTHORISED_PARTIES'],'baobab-dev-zuribeans-bff')
            self.assertEqual(env['ESTATE_CLIENT_BINDING_ENABLED'],'true')
            self.assertNotIn('BUYER_REGISTRATION_ENABLED',env)
            self.assertTrue(any('/dev07_buyer_fixture.py:' in p for p in candidate['services']['probe']['volumes']))
            self.assertEqual(set(candidate['services']),set(baseline['services']))
    def test_untrusted_component_receipt_cannot_promote_qualification(self):
        sha='b'*40
        value={'schema':'baobab-trade.dev07-iam-cp-components.v1','source_sha':sha,'evidence_class':'REAL_COMPONENT_SYNTHETIC_DATA',
            'scope':'LIVE_IAM_CP_NATIVE_TRADE_HANDLER','iam_cp_component_qualified':True,'host_teardown':'NOT_OBSERVED',
            'bff_http_qualified':False,'int05_qualified':False,'provider_qualified':False,'protected_acceptance':False,'production_authorized':False,
            'cases':{case:{'result':'PASS','reason':'OBSERVED'} for case in c.CASES}}
        self.assertIs(c.validate(value,sha),value)
        for change in ({'source_sha':'c'*40},{'bff_http_qualified':True},{'host_teardown':'PASS'}, {'private_token':'sensitive'}):
            with self.assertRaises(ValueError):c.validate({**value,**change},sha)
        broken=deepcopy(value);broken['cases'].pop('wrong-audience-denial')
        with self.assertRaises(ValueError):c.validate(broken,sha)
        broken=deepcopy(value);broken['cases']['wrong-audience-denial']={'result':'BLOCKED','reason':'NOT_EXECUTED'}
        with self.assertRaises(ValueError):c.validate(broken,sha)
