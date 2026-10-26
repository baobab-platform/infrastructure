"""Health-contract regressions, using the pinned native owners' wire shapes.

Component tests only: mocked transport never counts as native evidence.
"""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import dev15_health

class Response(io.BytesIO):
    status=200

class NativeHealthTests(unittest.TestCase):
    def observed(self,profile,body):
        with patch.object(dev15_health.urllib.request,'urlopen',return_value=Response(json.dumps(body).encode())):
            return dev15_health.observed(profile)

    def payments(self):
        # src/http.rs + SandboxProvider.kind() at merged Payments #43.
        return {'status':'READY','environment':'development','payment_provider':{'kind':'SANDBOX','simulated':True},
            'real_payments':'NOT_CONFIGURED','store':'in-memory','checks':{'store':'UP','payment_provider':'UP'}}

    def test_accepts_exact_native_uppercase_provider_kind(self):
        self.assertTrue(self.observed('payments-sandbox',self.payments()))

    def test_rejects_wrong_provider_truth_environment_and_store(self):
        for mutate in (
            lambda d:d['payment_provider'].update(kind='sandbox'),
            lambda d:d['payment_provider'].update(simulated=False),
            lambda d:d.update(environment='production'),
            lambda d:d.update(real_payments='CONFIGURED'),
            lambda d:d.update(store='external'),
            lambda d:d['checks'].update(store='DOWN'),
        ):
            doc=self.payments();mutate(doc)
            self.assertFalse(self.observed('payments-sandbox',doc))

    def test_pulse_requires_both_real_dependencies_ready(self):
        for database,semantic in ((False,True),(True,False),(False,False)):
            self.assertFalse(self.observed('pulse-intelligence',{'status':'ready','dependencies':{'database':database,'semantic_retrieval':semantic}}))
        self.assertTrue(self.observed('pulse-intelligence',{'status':'ready','dependencies':{'database':True,'semantic_retrieval':True}}))

if __name__=='__main__':unittest.main()
