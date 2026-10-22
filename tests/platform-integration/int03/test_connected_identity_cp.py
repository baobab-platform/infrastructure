"""CP observer source tests, not real IAM/CP integration acceptance."""
import json
import os
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch

from connected_identity_cp import CPTransport, assert_current_human, assert_negative, read_private_token
from connected_identity_evidence import EvidenceRefused


class Reply:
    def __init__(self, status, body):
        self.status=status
        self.data=json.dumps(body).encode()
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def read(self,n):
        return self.data[:n]


class LivePort(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ca=Path(self.tmp.name)/"ca.pem"
        self.ca.write_text("synthetic-invalid-ca")
        self.calls=[]
        self.responses=[]
        def open_issuer(req,timeout):
            self.calls.append((req.full_url,req.get_method(),req.data,req.headers))
            if not self.responses:
                raise EvidenceRefused("synthetic response missing")
            return self.responses.pop(0)
        with patch("connected_identity_cp.ssl.create_default_context",return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)):
            self.port=CPTransport("https://cp.int03.test",self.ca,open_request=open_issuer)

    def test_actual_request_shape_without_token_export(self):
        self.responses=[Reply(200,{"principal_id":"a"*36})]
        r=self.port.request("GET","/v1/admin/effective-authority","x"*36)
        self.assertEqual(r["status"],200)
        self.assertEqual(self.calls[0][0],"https://cp.int03.test/v1/admin/effective-authority")
        self.assertEqual(self.calls[0][1],"GET")
        self.assertNotIn("x"*36,json.dumps(r))
        self.assertTrue(assert_current_human(r,"a"*36))

    def test_denied_cp_response_carries_only_fixed_status_and_code(self):
        self.responses=[Reply(403,{"status":403,"code":"TENANT_CONTEXT_MISMATCH",
                                  "detail":"private irrelevant detail"})]
        r=self.port.request("POST","/v1/platform-context/resolve","x"*36,
                            {"tenant_id":"t","organisation_id":"o"})
        self.assertEqual(r,{"status":403,"code":"TENANT_CONTEXT_MISMATCH","document":None})
        self.assertTrue(assert_negative(r,"cross_tenant_denied"))

    def test_wrong_denial_cannot_count_as_revocation(self):
        with self.assertRaises(EvidenceRefused):
            assert_negative({"status":403,"code":"TENANT_CONTEXT_MISMATCH"},
                            "revoked_credential_denied")
        with self.assertRaises(EvidenceRefused):
            assert_negative({"status":503,"code":"CONTEXT_STORE_UNAVAILABLE"},
                            "wrong_audience_denied")

    def test_unrecognised_problem_or_html_refused(self):
        self.responses=[Reply(403,{"status":403,"code":"UNKNOWN_AUTHORITY"})]
        with self.assertRaises(EvidenceRefused):
            self.port.request("GET","/v1/admin/effective-authority","x"*36)
        self.responses=[Reply(200,{"principal_id":"wrong"})]
        with self.assertRaises(EvidenceRefused):
            assert_current_human(self.port.request("GET","/v1/admin/effective-authority","x"*36),"a"*36)

    def test_no_redirect_or_http_or_forbidden_endpoint(self):
        with self.assertRaises(EvidenceRefused):
            self.port.request("GET","/v1/tenants","x"*36)
        with self.assertRaises(EvidenceRefused):
            self.port.request("POST","/v1/platform-context/resolve","x"*36,{"data":"x"*8300})
        for origin in ("https://example.com","http://cp.int03.test",
                       "https://cp.int03.test.evil","https://cp.int03.test@evil.test"):
            with patch("connected_identity_cp.ssl.create_default_context",return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)):
                with self.assertRaises(EvidenceRefused):
                    CPTransport(origin,self.ca,open_request=lambda *a:None)

    def test_only_private_token_files(self):
        token=Path(self.tmp.name)/"issuer.token"
        token.write_text("t"*80)
        os.chmod(token,0o600)
        self.assertEqual(read_private_token(token),"t"*80)
        os.chmod(token,0o644)
        with self.assertRaises(EvidenceRefused):
            read_private_token(token)


if __name__=="__main__":
    unittest.main()
