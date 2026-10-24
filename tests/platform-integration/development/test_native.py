"""Source regressions only; never credited as live authority evidence."""
import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import adapter
import dev

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('native_probe',Path(__file__).with_name('native_probe.py'))
        cls.probe=importlib.util.module_from_spec(spec)
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):spec.loader.exec_module(cls.probe)

    def test_callback_is_bound_before_code_redemption(self):
        state='bound-state';valid='https://rp.baobab-dev.test/callback?code=real-observation&state='+state
        self.probe.validate_callback(valid,state)
        for url in (valid.replace(state,'foreign'),valid+'&state='+state,valid+'&code=other',valid+'&error=access_denied',valid+'#fragment',valid.replace('rp.baobab-dev.test','foreign.invalid'),valid.replace('/callback','/foreign')):
            with self.assertRaises(ValueError):self.probe.validate_callback(url,state)

    def test_failure_diagnostics_keep_only_closed_probe_codes(self):
        import subprocess
        output=io.StringIO()
        with redirect_stdout(output), patch('subprocess.run',return_value=subprocess.CompletedProcess([],2,
                'DEV05_PROBE_STAGE=BFF_CALLBACK\nDEV05_PROBE_STAGE=private-secret\nprivate-body','')):
            with self.assertRaises(dev.Refused):dev.call(['docker','exec','owned'])
        self.assertEqual(output.getvalue(),'DEV05_PROBE_STAGE=BFF_CALLBACK\n')
        with patch('subprocess.run',return_value=subprocess.CompletedProcess([],2,'private-body','DEV03_PROVIDER_PROBE_FAILED CP_PROVENANCE_PROPOSE private-secret')):
            with self.assertRaisesRegex(dev.Refused,'^PROBE_CP_PROVENANCE_PROPOSE$'):
                dev.call(['docker','exec','owned'])
        with patch('subprocess.run',return_value=subprocess.CompletedProcess([],2,'','DEV03_PROVIDER_PROBE_FAILED SECRET_VALUE')):
            with self.assertRaisesRegex(dev.Refused,'^COMMAND_FAILED$'):
                dev.call(['docker','exec','owned'])

    def test_qualification_retains_success_but_clears_it_before_failure(self):
        report={'schema':'infrastructure.dev03.authority-observed.v1','checks':{name:True for name in dev.AUTHORITY_CASES},
                'synthetic_only':True,'canonical_provider_qualified':False,'int03c_qualified':False,'nab03_qualified':False,'protected_acceptance':False}
        state={'phase':'TESTED','authority':{'old':'receipt'}}
        with patch.object(dev,'current',return_value=(Path('/private'),state)), patch.object(dev,'verify_sources'), \
             patch.object(dev,'compose'),patch.object(dev,'read',return_value=report),patch.object(dev,'persist'):
            self.assertEqual(dev.qualify('a'*32),report)
            self.assertEqual(state['authority'],report)
        with patch.object(dev,'current',return_value=(Path('/private'),state)), patch.object(dev,'verify_sources'), \
             patch.object(dev,'compose',side_effect=dev.Refused('OBSERVED_FAILURE')),patch.object(dev,'persist'):
            with self.assertRaises(dev.Refused): dev.qualify('a'*32)
            self.assertIsNone(state['authority'])

    def test_collapsed_ui_origins_remain_unique(self):
        raw='allowed_origins:\n  - https://rp.baobab-dev.test\n  - https://rp.baobab-dev.test\n'
        self.assertEqual(adapter.unique_transport_lists(raw).count('  - https://rp.baobab-dev.test'),1)

    def test_native_planes_and_exact_receipt_obligations(self):
        self.assertEqual(adapter.ISSUER,'https://hydra.int03.test')
        self.assertIn('hydra',dev.load_lock()['images'])
        self.assertIn('location = /oauth2/introspect',adapter.EDGE)
        self.assertIn('auth_basic_user_file',adapter.EDGE)
        self.assertIn('$introspector/admin/oauth2/introspect',adapter.EDGE)
        self.assertIn('kratos',dev.load_lock()['images'])
        self.assertEqual(len(dev.AUTHORITY_CASES),16)
        self.assertIn('issuer_revocation_while_unexpired',dev.AUTHORITY_CASES)
        self.assertIn('cp_denial_independent_of_issuer_status',dev.AUTHORITY_CASES)
        self.assertIn('wrong_pkce_denied_by_issuer',dev.AUTHORITY_CASES)

if __name__=='__main__':unittest.main()
