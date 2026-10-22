"""Issuer transport contract tests: no fake response is live acceptance."""
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch

from connected_identity_evidence import EvidenceRefused
from connected_identity_issuer import IssuerPort


class Reply:
    def __init__(self, data, code=200):
        import json
        self.data=json.dumps(data).encode()
        self.status=code
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self, limit): return self.data[:limit]


class IssuerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ca=Path(self.temp.name)/"ca.pem"
        self.ca.write_text("invalid synthetic CA replaced in tests")
        self.out=[]
        self.inputs=[]
        def open_request(req,timeout):
            self.inputs.append(req)
            if not self.out:
                raise EvidenceRefused("fake response missing")
            return self.out.pop(0)
        with patch("connected_identity_issuer.ssl.create_default_context",
                   return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)):
            self.port=IssuerPort("https://hydra.int03.test",self.ca,
                                 transport=open_request)

    def test_discovery_must_bind_exact_real_issuer(self):
        self.out=[Reply({"issuer":"https://hydra.int03.test",
             "token_endpoint":"https://hydra.int03.test/oauth2/token",
             "introspection_endpoint":"https://hydra.int03.test/admin/oauth2/introspect",
             "revocation_endpoint":"https://hydra.int03.test/oauth2/revoke"})]
        self.assertTrue(self.port.discover())
        self.assertEqual(len(self.inputs),1)
        self.assertEqual(self.inputs[0].get_method(),"GET")

    def test_malicious_discovery_host_rejected(self):
        for url in ("https://hydra.int03.test.evil/oauth2/token",
                    "https://evil.test/oauth2/token",
                    "http://hydra.int03.test/oauth2/token"):
            self.out=[Reply({"issuer":"https://hydra.int03.test",
                "token_endpoint":url,
                "introspection_endpoint":"https://hydra.int03.test/oauth2/introspect",
                "revocation_endpoint":"https://hydra.int03.test/oauth2/revoke"})]
            with self.assertRaises(EvidenceRefused):
                self.port.discover()

    def test_introspection_bounds_authority_and_expiry(self):
        now=10000
        active={"active":True,"client_id":"reviewed-workload",
                "aud":["baobab-control-plane"],"scope":"context:resolve",
                "exp":now+150}
        result=self.port.assert_introspection(active,client_id="reviewed-workload",
                          audience="baobab-control-plane",scope="context:resolve",now=now)
        self.assertFalse(result["qualified"])
        for change in ({"active":False},{"aud":["foreign"]},
                       {"client_id":"other"},{"exp":now-1},
                       {"scope":"context:validate"}):
            with self.assertRaises(EvidenceRefused):
                self.port.assert_introspection(dict(active,**change),
                    client_id="reviewed-workload",audience="baobab-control-plane",
                    scope="context:resolve",now=now)

    def test_revocation_requires_independently_current_unexpired_token(self):
        self.assertFalse(self.port.assert_revoked({"active":False},
                                 expiry=11000,now=10000)["qualified"])
        for x,expiry,now in (({"active":True},11000,10000),
                             ({"active":False},10000,10000)):
            with self.assertRaises(EvidenceRefused):
                self.port.assert_revoked(x,expiry=expiry,now=now)

    def test_private_only_operation_gate(self):
        with self.assertRaises(EvidenceRefused):
            IssuerPort("https://unknown.example",self.ca)
        with self.assertRaises(EvidenceRefused):
            self.port.execute("token_endpoint",{"grant_type":"client_credentials"},"Basic fake")
        self.out=[Reply({"issuer":"https://hydra.int03.test",
             "token_endpoint":"https://hydra.int03.test/oauth2/token",
             "introspection_endpoint":"https://hydra.int03.test/oauth2/introspect",
                "revocation_endpoint":"https://hydra.int03.test/oauth2/revoke"})]
        self.port.discover()
        self.out=[Reply({"active":False})]
        result=self.port.execute("introspection_endpoint",{"token":"opaque"},
                                 "Basic independently-reviewed-fixture")
        self.assertIs(result["active"],False)
        with self.assertRaises(EvidenceRefused):
            self.port.execute("revocation_endpoint",{},"Basic independently-reviewed-fixture")


if __name__=="__main__":
    unittest.main()
