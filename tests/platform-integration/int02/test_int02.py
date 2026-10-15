"""Fail-closed source contracts, independent of Docker and network."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import unittest.mock as mock

BASE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("int02",BASE/"orchestrate.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ContractTest(unittest.TestCase):
    def test_pinned_profile(self):
        data=m.load()
        self.assertEqual(data["profile"],"iam-cp")
        self.assertEqual(data["evidence_class"],"REAL_COMPONENT_SYNTHETIC_DATA")
        self.assertEqual(set(data["mandatory"]),m.REQUIRED)
        m.check_prerequisites(data,static=True)

    def test_negative_mutations(self):
        data=m.load()
        cases=[("no_protected_credentials",False),
               ("evidence_class","PROTECTED_STAGING"),
               ("mandatory",["L4-IAM-01"]),
               ("sources",{**data["sources"],"baobab-cp":"main"})]
        for key,val in cases:
            with self.subTest(key=key),tempfile.TemporaryDirectory() as d:
                path=Path(d)/"lock.json"
                path.write_text(json.dumps({**data,key:val}))
                with mock.patch.object(m,"LOCK",path):
                    with self.assertRaises(m.Blocked):
                        m.load()

    def test_image_must_have_immutable_digest(self):
        data=m.load()
        data["runtime_images"]["python_probe"]="python:3.12.12-slim"
        with self.assertRaises(m.Blocked):
            m.check_prerequisites(data,static=False)

    def test_no_public_listening_ports(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"compose.yaml"
            p.write_text("services:\n  cp:\n    ports:\n      - 8080:8080\n")
            with mock.patch.object(m,"COMPOSE",p):
                with self.assertRaises(m.Blocked):
                    m.load()

    def test_provider_resolution_fixture_cannot_claim_certified_health(self):
        source=(BASE/"probe.py").read_text()
        self.assertIn('state["L4-CP-02"]="BLOCKED" if provider_record else "FAIL"',source)
        self.assertIn("wait-iam",source)

    def test_iam_bootstrap_workload_secret_contract(self):
        source=(BASE/"probe.py").read_text()
        self.assertIn('return token("baobab-cms-workload",prefix,"client_credentials")',source)
        self.assertNotIn('prefix+"-baobab-cms-workload"',source)

    def test_iam_readiness_requires_real_issuer(self):
        # Management health is optional; the fallback must still contact the
        # genuine issuer's OIDC metadata and verify its canonical issuer.
        source=(BASE/"probe.py").read_text()
        self.assertIn('"/.well-known/openid-configuration"',source)
        self.assertIn('document.get("issuer") == ISSUER',source)
        self.assertIn('status == 200',source)
        self.assertIn('verified-oidc-discovery',source)

    def test_admin_master_probe_checks_real_token_endpoint(self):
        source=(BASE/"probe.py").read_text()
        self.assertIn("def verify_master_administrator():",source)
        self.assertIn("/realms/master/protocol/openid-connect/token",source)
        self.assertIn("master-admin",source)

    def test_blocked_cannot_be_certification(self):
        data=m.load()
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(m,"EVIDENCE",Path(d)):
                m.write_evidence({"project":"l4-1111111111111111"},data,
                   {"scenarios":{k:"BLOCKED" for k in m.REQUIRED}},accepted=False)
            evidence=json.loads(next(Path(d).glob("*.json")).read_text())
            self.assertFalse(evidence["passed"])
            self.assertFalse(evidence["protected_staging_accepted"])

if __name__=="__main__":
    unittest.main()
