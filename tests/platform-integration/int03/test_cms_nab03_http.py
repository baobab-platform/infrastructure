"""Verified CMS transport contracts without claiming live integration."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from cms_nab03 import Refused
from cms_nab03_http import HTTPSCMS


class Response:
    def __init__(self, status, payload):
        self.status = status
        self.buffer = BytesIO(json.dumps(payload).encode())
    def read(self, size):
        return self.buffer.read(size)
    def __enter__(self):
        return self
    def __exit__(self, *_):
        self.buffer.close()


class Opener:
    def __init__(self, status, data):
        self.status = status
        self.data = data
        self.requests = []
    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return Response(self.status, self.data)


class TestHTTPSCMS(unittest.TestCase):
    def setUp(self):
        self.context = "26888312-4921-419a-a804-16fc92ba11e3"
        self.tenant = "da1b3aec-2c87-4cc9-a925-1c77178b8fcf"
        self.probe = HTTPSCMS.__new__(HTTPSCMS)
        self.probe.origin = "https://cms.int03.test"
    def invoke(self, opener, **kwargs):
        self.probe.opener = opener
        return self.probe.resolve(context_id=self.context, tenant_id=self.tenant,
                                  content_key="home", bearer="a"*32, timeout=9, **kwargs)

    def test_real_response_minimum_data_and_bearer_not_in_receipt(self):
        o = Opener(200, {"record": {"tenant_id": self.tenant, "content_key": "home",
                                    "publication_state": "PUBLISHED",
                                    "secret": "must never leave transport"}})
        result = self.invoke(o)
        self.assertTrue(result.record_present)
        self.assertEqual(result.publication_state, "PUBLISHED")
        self.assertNotIn("secret", repr(result))
        request, timeout = o.requests[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + "a"*32)
        self.assertEqual(request.full_url,
                         "https://cms.int03.test/v1/content/resolve?context_id=" + self.context)
        self.assertEqual(timeout, 9)

    def test_missing_content_retains_key(self):
        result = self.invoke(Opener(200, {"record": None}))
        self.assertFalse(result.record_present)
        self.assertEqual(result.content_key, "home")

    def test_denial_exposes_only_safe_fixed_code(self):
        result = self.invoke(Opener(403, {"code": "CONTENT_CONTEXT_REJECTED",
                                         "detail": "token hidden"}))
        self.assertEqual((result.status, result.code), (403, "CONTENT_CONTEXT_REJECTED"))
        self.assertNotIn("token hidden", repr(result))

    def test_refuses_html_unknown_response_and_bounded_request(self):
        for payload in ({}, {"record": 15}):
            with self.assertRaises(Refused):
                self.invoke(Opener(200, payload))
        with self.assertRaises(Refused):
            self.invoke(Opener(401, {"code": "not-safe-user-text"}))
        for changes in ({"preview": True, "digital_estate_id": "a"*8200},
                        {"market_id": "m"*8200}):
            with self.assertRaises(Refused):
                self.invoke(Opener(200, {"record": None}), **changes)

    def test_no_transport_on_invalid_request(self):
        o = Opener(200, {"record": None})
        for invalid in ("not-uuid", self.context.upper()):
            with self.assertRaises(Refused):
                self.probe.resolve(context_id=invalid, tenant_id=self.tenant,
                                   content_key="home", bearer="a"*32, timeout=9)
        with self.assertRaises(Refused):
            self.probe.resolve(context_id=self.context, tenant_id=self.tenant,
                               content_key="../home", bearer="a"*32, timeout=9)
        with self.assertRaises(Refused):
            self.probe.resolve(context_id=self.context, tenant_id=self.tenant,
                               content_key="home", bearer="Bearer a b", timeout=9)
        with self.assertRaises(Refused):
            self.probe.resolve(context_id=self.context, tenant_id=self.tenant,
                               content_key="home", bearer="a"*32, timeout=60)
        self.assertEqual(o.requests, [])

    def test_https_ca_cannot_fall_back_to_insecure(self):
        with tempfile.TemporaryDirectory() as td:
            ca = Path(td) / "ca.pem"
            ca.write_text("not a CA")
            for origin in ("http://cms.int03.test", "https://cms.int03.test/user",
                           "https://user:pass@cms.int03.test"):
                with self.assertRaises(Refused):
                    HTTPSCMS(origin, ca)
            with self.assertRaises(Refused):
                HTTPSCMS("https://cms.int03.test", ca)


if __name__ == "__main__":
    unittest.main()
