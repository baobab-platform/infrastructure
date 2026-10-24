"""Source regressions only; never credited as live authority evidence."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import adapter
import dev

class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('native_probe',Path(__file__).with_name('probe.py'))
        cls.probe=importlib.util.module_from_spec(spec)
        with patch('ssl.create_default_context',return_value=SimpleNamespace()):spec.loader.exec_module(cls.probe)

    def test_callback_is_bound_before_code_redemption(self):
        state='bound-state';valid='https://rp.baobab-dev.test/callback?code=real-observation&state='+state
        self.probe.validate_callback(valid,state)
        for url in (valid.replace(state,'foreign'),valid+'&state='+state,valid+'&code=other',valid+'&error=access_denied',valid+'#fragment',valid.replace('rp.baobab-dev.test','foreign.invalid'),valid.replace('/callback','/foreign')):
            with self.assertRaises(ValueError):self.probe.validate_callback(url,state)

    def test_native_planes_and_exact_receipt_obligations(self):
        self.assertEqual(adapter.ISSUER,'https://hydra.int03.test')
        self.assertIn('hydra',dev.load_lock()['images'])
        self.assertIn('kratos',dev.load_lock()['images'])
        self.assertEqual(len(dev.AUTHORITY_CASES),16)
        self.assertIn('issuer_revocation_while_unexpired',dev.AUTHORITY_CASES)
        self.assertIn('cp_denial_independent_of_issuer_status',dev.AUTHORITY_CASES)
        self.assertIn('wrong_pkce_denied_by_issuer',dev.AUTHORITY_CASES)

if __name__=='__main__':unittest.main()
