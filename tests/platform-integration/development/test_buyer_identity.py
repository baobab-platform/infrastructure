"""DEV-07 source refusal boundaries; never actual issuer/runtime evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import importlib.util
import types
from unittest.mock import Mock, patch
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

    def test_closed_dev07_diagnostics_distinguish_cp_and_revoke_without_leaking(self):
        allowed=(
            'DEV07_CP_PRINCIPAL_STAGE=CP_RESPONDED',
            'DEV07_CP_PRINCIPAL_STAGE=CALLER_REVOKED',
            'DEV07_CP_PRINCIPAL_RESULT=RESOLVED',
            'DEV07_CP_PRINCIPAL_RESULT=INVALID_RESPONSE',
            'DEV07_PRIVATE_FAILURE_CLASS=DEV07_CP_PRINCIPAL_PREFLIGHT_REFUSED',
            'DEV07_PRIVATE_FAILURE_CLASS=DEV07_CP_CALLER_REVOKE_REFUSED',
            'DEV07_PRIVATE_FAILURE_CLASS=DEV07_CP_CALLER_REVOKE_READBACK_REFUSED',
            'DEV07_CP_PRINCIPAL_REFUSAL=HTTP_403_CODE_CALLER_NOT_PERMITTED',
        )
        self.assertTrue(all(dev.is_dev07_preflight_diagnostic(x) for x in allowed))
        refused=(
            'DEV07_PRIVATE_FAILURE_CLASS=ANY_OTHER_REASON',
            'DEV07_CP_PRINCIPAL_RESULT=RESOLVED token=private',
            'DEV07_CP_PRINCIPAL_STAGE=CP_RESPONDED\\nsecret',
            'DEV07_CP_PRINCIPAL_REFUSAL=HTTP_200_CODE_OTHER',
            'DEV07_CP_CALLER_ISSUANCE=HTTP_401_CODE_private',
            'Authorization: Bearer private',
            '',
        )
        self.assertTrue(all(not dev.is_dev07_preflight_diagnostic(x) for x in refused))

    def _private_buyer_probe(self, request):
        # Fake transport only: this unit test is not native IAM/CP evidence.
        fake=types.ModuleType('native_probe')
        fake.ISSUER='https://hydra.int03.test'
        fake.request=request
        def require(ok,code='PROVIDER_OBSERVATION_FAILED'):
            if not ok:
                raise ValueError(code)
        fake.require=require
        iam=types.ModuleType('dev07_buyer_fixture')
        iam.BFF='baobab-dev-zuribeans-bff'
        iam.VALIDATOR='baobab-dev-trade-buyer-validator'
        iam.CALLBACK='https://rp.baobab-dev.test/dev07/callback'
        file=Path(__file__).with_name('buyer_identity_probe.py')
        spec=importlib.util.spec_from_file_location('_dev07_probe_under_test',file)
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{'native_probe':fake,'dev07_buyer_fixture':iam}):
            spec.loader.exec_module(module)
        return module

    def test_revoke_uses_registered_method_and_independent_readback(self):
        native={'clients':{
            'baobab-dev-trade-buyer-validator':{
                'secret':'private-validator','config':{'token_endpoint_auth_method':'client_secret_post'}},
            'baobab-dev-zuribeans-bff':{
                'secret':'private-bff','config':{'token_endpoint_auth_method':'client_secret_basic'}},
        }}
        for name,body_auth,basic in (
            ('baobab-dev-trade-buyer-validator',True,None),
            ('baobab-dev-zuribeans-bff',False,('baobab-dev-zuribeans-bff','private-bff')),
        ):
            with self.subTest(client=name):
                transport=Mock(side_effect=[(200,{},None),(200,{'active':False},None)])
                probe=self._private_buyer_probe(transport)
                verifier=('verifier','private')
                probe.revoke_and_readback(native,name,'single-use-token',verifier)
                self.assertEqual(transport.call_count,2)
                revoke=transport.call_args_list[0]
                self.assertEqual(revoke.args[1],'https://hydra.int03.test/oauth2/revoke')
                self.assertEqual(revoke.args[2]['token'],'single-use-token')
                self.assertEqual(revoke.kwargs['basic'],basic)
                self.assertEqual('client_id' in revoke.args[2],body_auth)
                self.assertEqual('client_secret' in revoke.args[2],body_auth)
                readback=transport.call_args_list[1]
                self.assertEqual(readback.args[1],'https://hydra.int03.test/oauth2/introspect')
                self.assertEqual(readback.kwargs['basic'],verifier)

    def test_revoke_denies_current_token_or_unsupported_client_auth(self):
        name='baobab-dev-trade-buyer-validator'
        native={'clients':{name:{
            'secret':'private-validator','config':{'token_endpoint_auth_method':'client_secret_post'}}}}
        transport=Mock(side_effect=[(200,{},None),(200,{'active':True},None)])
        probe=self._private_buyer_probe(transport)
        with self.assertRaisesRegex(ValueError,'DEV07_CP_CALLER_REVOKE_READBACK_REFUSED'):
            probe.revoke_and_readback(native,name,'still-current',('verifier','secret'))
        native['clients'][name]['config']['token_endpoint_auth_method']='none'
        transport.reset_mock()
        with self.assertRaisesRegex(ValueError,'DEV07_UNSUPPORTED_CLIENT_AUTH'):
            probe.revoke_and_readback(native,name,'token',('verifier','secret'))
        transport.assert_not_called()

    def test_native_context_diagnostics_are_closed_and_cannot_release_response_text(self):
        self.assertTrue(dev.is_dev07_native_diagnostic(
            'DEV07_NATIVE_CONTEXT=HTTP_503_REASON_SOURCE_UNAVAILABLE'))
        self.assertTrue(dev.is_dev07_native_diagnostic(
            'DEV07_NATIVE_CONTEXT=HTTP_200_REASON_CONTEXT_MISMATCH'))
        for line in ('DEV07_NATIVE_CONTEXT=HTTP_503_REASON_private-token',
                     'DEV07_NATIVE_CONTEXT=HTTP_503_REASON_SOURCE_UNAVAILABLE token=private',
                     'DEV07_NATIVE_CONTEXT=HTTP_503_REASON_SOURCE_UNAVAILABLE\nsecret',
                     'DEV07_NATIVE_CONTEXT=HTTP_999_REASON_OTHER'):
            self.assertFalse(dev.is_dev07_native_diagnostic(line))
