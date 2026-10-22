"""Source contracts for guarded IAM token handoff; not a live OAuth proof."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import connected_identity_issuer_run as run
import cms_evidence as custody
from connected_identity_evidence import EvidenceRefused


class FakeIssuer:
    def __init__(self, *, wrong=False):
        self.calls=[]
        self.wrong=wrong
    def discover(self):
        self.calls.append(("discover",))
        return True
    def execute(self,operation,fields,actor):
        self.calls.append((operation,fields,actor))
        if operation=="token_endpoint":
            return {"access_token":"t"*128,"token_type":"Bearer","expires_in":120}
        if self.wrong:
            return {"active":False,"client_id":"synthetic-owner"}
        return {"active":True,"client_id":"synthetic-owner"}
    def assert_introspection(self,data,*,client_id,audience,scope,now):
        if data["active"] is not True:
            raise EvidenceRefused("issuer refused")
        return {"client_id":client_id,"audience":audience,"scope":scope,
                "expiry":now+100,"qualified":False}


class IssuerRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        os.chmod(self.root,0o700)
        self.owner=self.root/"owner"
        self.checker=self.root/"checker"
        self.owner.write_text("owner-"+"x"*40)
        self.checker.write_text("checker-"+"y"*40)
        os.chmod(self.owner,0o600)
        os.chmod(self.checker,0o600)
        self.plan={
            "schema":run.SCHEMA,"run_id":"a"*32,"environment":"development",
            "sources":dict.fromkeys(["infrastructure","shared","baobab-cms",
                                     "baobab-iam","baobab-cp","nabhold"],"b"*40),
            "issuer":"https://hydra.int03.test","ca_file":str(self.root/"ca.pem"),
            "shared_checkout":str(self.root/"shared"),
            "owner_client":"synthetic-owner","verifier_client":"synthetic-checker",
            "owner_secret_file":str(self.owner),
            "verifier_secret_file":str(self.checker),
            "audience":"baobab-control-plane","scope":"context:resolve",
            "approval_digest":"sha256:"+"c"*64,
        }
        self.spec=self.root/"operator.json"
        self.write()

    def write(self):
        self.spec.write_text(json.dumps(self.plan))
        os.chmod(self.spec,0o600)

    def test_real_issuer_separately_introspects_and_retains_no_secret(self):
        p=run.reviewed(self.spec)
        with patch.object(run,"source_pins",return_value=p["sources"]), patch.object(run,"verify_governed_workloads",return_value=True):
            issuer=FakeIssuer()
            token,observation=run.issue(p,issuer=issuer,now=1000)
        self.assertEqual(token,"t"*128)
        self.assertEqual([x[0] for x in issuer.calls],
                         ["discover","token_endpoint","introspection_endpoint"])
        self.assertNotIn(token,json.dumps(observation))
        self.assertFalse(observation["qualified"])
        target=self.root/"saved.token"
        directory=self.root/"custody"
        run.persist(p,token,observation,token_output=target,
                    evidence_output=directory)
        self.assertEqual(target.stat().st_mode & 0o777,0o600)
        self.assertTrue(custody.verify(directory)["files"])
        self.assertNotIn(token,(directory/"issuer-create.json").read_text())

    def test_unregistered_clients_cannot_issue_any_credential(self):
        p=run.reviewed(self.spec)
        with patch.object(run,"source_pins",return_value=True):
            with self.assertRaises(EvidenceRefused):
                run.issue(p,issuer=FakeIssuer(),now=1000)

    def test_introspection_cannot_be_skipped(self):
        p=run.reviewed(self.spec)
        with patch.object(run,"source_pins",return_value=True), patch.object(run,"verify_governed_workloads",return_value=True):
            with self.assertRaises(EvidenceRefused):
                run.issue(p,issuer=FakeIssuer(wrong=True),now=1000)

    def test_no_held_cms_client_or_shared_identity(self):
        for name in run.FORBIDDEN:
            previous=self.plan["owner_client"]
            self.plan["owner_client"]=name
            self.write()
            with self.assertRaises(EvidenceRefused):
                run.reviewed(self.spec)
            self.plan["owner_client"]=previous
        self.write()
        self.plan["environment"]="production"
        self.write()
        with self.assertRaises(EvidenceRefused):
            run.reviewed(self.spec)

    def test_different_live_issuer_and_verifier_credentials_required(self):
        p=run.reviewed(self.spec)
        self.checker.write_text(self.owner.read_text())
        with patch.object(run,"source_pins",return_value=True), patch.object(run,"verify_governed_workloads",return_value=True):
            with self.assertRaises(EvidenceRefused):
                run.issue(p,issuer=FakeIssuer(),now=1000)

    def test_custody_does_not_overwrite_or_store_token_in_manifest(self):
        p=run.reviewed(self.spec)
        with patch.object(run,"source_pins",return_value=True), patch.object(run,"verify_governed_workloads",return_value=True):
            token,obs=run.issue(p,issuer=FakeIssuer(),now=1000)
        dest=self.root/"saved.token"
        directory=self.root/"custody"
        run.persist(p,token,obs,token_output=dest,evidence_output=directory)
        with self.assertRaises(EvidenceRefused):
            run.persist(p,token,obs,token_output=dest,evidence_output=directory)


if __name__=="__main__":
    unittest.main()
