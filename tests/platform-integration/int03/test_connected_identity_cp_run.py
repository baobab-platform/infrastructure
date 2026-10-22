"""INT-03C synthetic adapters: contract coverage only, NEVER runtime PASS."""
import os
from pathlib import Path
import tempfile
import unittest
import uuid

import connected_identity_cp_run as runner
from connected_identity_evidence import EvidenceRefused, validate


class FakePort:
    def __init__(self,values):
        self.responses=list(values)
        self.calls=[]
    def request(self,method,path,token,body=None):
        self.calls.append((method,path,token,body))
        return self.responses.pop(0)


class LiveCPObserver(unittest.TestCase):
    def setUp(self):
        self.tenant=str(uuid.uuid4())
        self.neighbour=str(uuid.uuid4())
        self.organisation=str(uuid.uuid4())
        self.human=str(uuid.uuid4())
        self.plan={
            "tenant_id":self.tenant,"neighbour_tenant_id":self.neighbour,
            "organisation_id":self.organisation,"human_principal_id":self.human,
            "country_code":"ZA","organisation_kind":"ORGANISATION",
            "run_id":"a"*32,
            "sources":dict.fromkeys(["shared","infrastructure","baobab-cms",
                 "baobab-iam","baobab-cp","nabhold"],"b"*40)}
        self.tokens=dict.fromkeys(["human","workload","wrong_audience",
                                   "revoked","deactivated"],"private-token")
        self.responses=[
            {"status":200,"code":"","document":{"principal_id":self.human}},
            {"status":200,"code":"","document":{"context_id":str(uuid.uuid4()),
             "tenant_id":self.tenant,"organisation_id":self.organisation,
             "expires_at":"2026-10-23T00:00:00Z"}},
            {"status":401,"code":"AUTH_TOKEN_REQUIRED","document":None},
            {"status":403,"code":"TENANT_CONTEXT_MISMATCH","document":None},
            {"status":401,"code":"AUTH_TOKEN_REQUIRED","document":None},
            {"status":403,"code":"PRINCIPAL_INACTIVE","document":None},
        ]

    def test_connected_cp_port_observes_exact_separate_negative_credentials(self):
        port=FakePort(self.responses)
        checks=runner.execute(port,self.plan,self.tokens)
        self.assertEqual(len(checks),5)
        self.assertEqual(len(port.calls),6)
        self.assertEqual(port.calls[3][3]["tenant_id"],self.neighbour)
        self.assertEqual(port.calls[1][3]["tenant_id"],self.tenant)

    def test_successful_cp_source_cannot_report_iAM_or_teardown_pass(self):
        port=FakePort(self.responses)
        checks=runner.execute(port,self.plan,self.tokens)
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/"sealed"
            receipt=runner.capture(self.plan,checks,target)
            self.assertFalse(receipt["qualified"])
            self.assertFalse(receipt["nab03_qualified"])
            self.assertEqual(receipt["observations"]["iam_issued_token"]["result"],"BLOCKED")
            self.assertEqual(receipt["observations"]["independent_teardown"]["result"],"BLOCKED")
            self.assertFalse(validate(receipt,expected_sources={
                k:receipt["sources"][k] for k in receipt["sources"]}))
            self.assertTrue((target/"manifest.json").exists())
            with self.assertRaises(FileExistsError):
                runner.capture(self.plan,checks,target)

    def test_wrong_audience_or_cross_tenant_success_is_refused(self):
        for index in (2,3):
            altered=[dict(x) for x in self.responses]
            altered[index]={"status":200,"code":"","document":{}}
            with self.assertRaises(EvidenceRefused):
                runner.execute(FakePort(altered),self.plan,self.tokens)

    def test_missing_verified_current_cp_principal_refused(self):
        altered=[dict(x) for x in self.responses]
        altered[0]={"status":200,"code":"","document":{"principal_id":str(uuid.uuid4())}}
        with self.assertRaises(EvidenceRefused):
            runner.execute(FakePort(altered),self.plan,self.tokens)


if __name__=="__main__":
    unittest.main()
