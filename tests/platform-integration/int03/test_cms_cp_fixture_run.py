"""Source-only operator control tests: no CP or IAM is provisioned here."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import cms_cp_fixture_run as operator
from cms_cp_governance import Refused


class TestOperator(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        os.chmod(self.root,0o700)
        self.plan=self.root/"plan.json"
        self.doc={"schema":operator.PLAN_SCHEMA,"run_id":"int03-cp-governed-test-run-2026",
                  "environment":"development","step":"tenant",
                  "idempotency_key":"int03-tenant-2026-accepted",
                  "document":{"tenant_onboarding_request_id":"tor_accepted",
                              "legal_entity_id":"test-legal-entity",
                              "display_name":"INT03 Synthetic Tenant",
                              "residency_region":"af-south-1",
                              "isolation_strategy":"row_level_security"}}
        self.write()
    def write(self):
        self.plan.write_text(json.dumps(self.doc))

    def test_safe_source_only_inspect_does_not_call_cp(self):
        self.assertEqual(operator.main(["inspect","--plan",str(self.plan)]),0)
        self.assertEqual(operator.read_plan(self.plan)["step"],"tenant")

    def test_non_development_and_forged_authority_rejected(self):
        for changes in (
            {"environment":"production"},
            {"step":"unknown"},
            {"document":{"status":"ACTIVE"}},
            {"document":{"client_secret":"leak"}},
            {"document":{"provider":{"certified_by":"self"}}},
            {"run_id":"not-a-run"},
        ):
            saved=dict(self.doc)
            self.doc.update(changes)
            self.write()
            with self.assertRaises(Refused):
                operator.read_plan(self.plan)
            self.doc=saved
        self.write()

    def test_cp_apply_needs_explicit_two_real_operator_credentials(self):
        result=operator.main(["apply","--plan",str(self.plan)])
        self.assertEqual(result,2)
        self.assertFalse((self.root/"receipt.json").exists())

    def test_cp_only_step_never_claims_connected_acceptance(self):
        class Fake:
            def __init__(self): self.calls=[]
            def register_tenant(self,doc,*,key):
                self.calls.append(("tenant",doc,key))
                return {"operation_id":"op_1234","tenant_registered":False,"qualified":False}
            def certify_provider(self,**doc):
                self.calls.append(("certify",doc))
                return {"certification_id":"cert_"+"a"*32,"status":"CERTIFIED"}
        fake=Fake()
        observed=operator.execute_step(fake,self.doc)
        self.assertFalse(observed["qualified"])
        self.assertEqual(len(fake.calls),1)
        self.doc["step"]="provider-certify"
        self.doc["document"]={"provider_id":"provider_123","capability_key":"content.entry.resolve",
                "contract_version":1,"release_id":"erl_123",
                "qualification_profile":"int03.cms.reviewed",
                "evidence":[{"uri":"https://example.invalid/actual","digest":"sha256:"+"a"*64}]}
        observed=operator.execute_step(fake,self.doc)
        self.assertFalse(observed["qualified"])
        self.assertEqual(len(fake.calls),2)
        self.doc["document"]["approved"]=True
        with self.assertRaises(Refused):
            operator.execute_step(fake,self.doc)

    def test_durable_attempt_precedes_mutation_and_never_claims_success(self):
        receipt=self.root/"receipt.json"
        attempt={"schema":"infrastructure.int03.cp-fixture-observation.v1",
                 "state":"ATTEMPTING_CP_POST","qualified":False}
        operator.save_custody(receipt,attempt,exclusive=True)
        self.assertEqual(receipt.stat().st_mode & 0o777,0o600)
        self.assertEqual(json.loads(receipt.read_text())["state"],"ATTEMPTING_CP_POST")
        with self.assertRaises(FileExistsError):
            operator.save_custody(receipt,attempt,exclusive=True)
        operator.save_custody(receipt,dict(attempt,state="CP_RESPONSE_OBSERVED_UNATTESTED"),
                             exclusive=False)
        state=json.loads(receipt.read_text())
        self.assertEqual(state["state"],"CP_RESPONSE_OBSERVED_UNATTESTED")
        self.assertFalse(state["qualified"])

    def test_nonprivate_operator_token_file_denied(self):
        file=self.root/"token"
        file.write_text("not-a-real-token")
        os.chmod(file,0o644)
        with self.assertRaises(Refused):
            operator.private_file(file)


if __name__=="__main__":
    unittest.main()
