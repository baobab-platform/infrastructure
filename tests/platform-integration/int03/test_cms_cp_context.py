"""Protocol guards for CP-owned topology; no mock can satisfy live acceptance."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
import uuid

import cms_gate
from cms_cp_context import HTTPSControlPlane, Refused, assert_resolved, assert_validated
from cms_lifecycle import Lifecycle


def ident():
    return str(uuid.uuid4())


class Tests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.tenant, self.org, self.context_id = ident(), ident(), ident()
        self.market = ident()
        self.expiry = self.now + timedelta(seconds=75)
        self.resolved = {
            "context_id": self.context_id, "tenant_id": self.tenant,
            "organisation_id": self.org, "organisation_type": "ORGANISATION",
            "country_code": "ZA", "market_id": self.market, "currency_code": "ZAR",
            "resolved_at": (self.now - timedelta(seconds=1)).isoformat(),
            "expires_at": self.expiry.isoformat(),
        }
        self.validated = {
            "context_id": self.context_id, "tenant_id": self.tenant,
            "organisation_id": self.org, "market_id": self.market,
            "authority_purpose": "RUNTIME",
            "resolved_at": self.resolved["resolved_at"],
            "expires_at": self.resolved["expires_at"],
        }

    def test_cp_issues_exact_bounded_topology(self):
        cid, exp = assert_resolved(self.resolved, tenant=self.tenant,
            organisation=self.org, country="ZA", kind="ORGANISATION", now=self.now)
        self.assertEqual(cid, self.context_id)
        assert_validated(self.validated, cid=cid, tenant=self.tenant,
                         organisation=self.org, market=self.market, expires=exp, now=self.now)

    def test_foreign_organisation_wrong_market_and_invalid_purpose_denied(self):
        for field, value in (("tenant_id", ident()), ("organisation_id", ident()),
                             ("country_code", "UG"), ("market_id", ""),
                             ("organisation_type", "SUPPLIER_ORGANISATION"),
                             ("expires_at", (self.now - timedelta(seconds=1)).isoformat())):
            bad = dict(self.resolved, **{field: value})
            with self.assertRaises(Refused, msg=field):
                assert_resolved(bad, tenant=self.tenant, organisation=self.org,
                                country="ZA", kind="ORGANISATION", now=self.now)
        for field, value in (("context_id", ident()), ("tenant_id", ident()),
                             ("organisation_id", ident()), ("market_id", ident()),
                             ("authority_purpose", "TENANT_PROVISIONING")):
            bad = dict(self.validated, **{field: value})
            with self.assertRaises(Refused, msg=field):
                assert_validated(bad, cid=self.context_id, tenant=self.tenant,
                                 organisation=self.org, market=self.market,
                                 expires=self.expiry, now=self.now)

    def test_cannot_use_unbounded_or_provisioning_context(self):
        for value in (None, "", "not-a-date"):
            bad = dict(self.resolved, expires_at=value)
            with self.assertRaises(Refused):
                assert_resolved(bad, tenant=self.tenant, organisation=self.org,
                    country="ZA", kind="ORGANISATION", now=self.now)
        bad = dict(self.validated, provisioning_authority={"plan_id": "fake"})
        with self.assertRaises(Refused):
            assert_validated(bad, cid=self.context_id, tenant=self.tenant,
                             organisation=self.org, market=self.market,
                             expires=self.expiry, now=self.now)

    def test_https_transport_guards_and_private_token_handling(self):
        with tempfile.TemporaryDirectory() as td:
            ca = Path(td) / "ca.pem"
            # A failed CA load is an error, never TLS insecure fallback.
            ca.write_text("invalid CA")
            with self.assertRaises(Refused):
                HTTPSControlPlane("http://cp.int02.test", ca)
            with self.assertRaises(Exception):
                HTTPSControlPlane("https://cp.int02.test", ca)
        # Test-only transport (not provenance) exercises exact methods.
        seen = []
        def transport(path, bearer, payload, seconds):
            seen.append((path, bearer, payload, seconds))
            return json.dumps(self.resolved if path.endswith("/resolve") else self.validated).encode()
        cp = HTTPSControlPlane.__new__(HTTPSControlPlane)
        cp.transport = transport
        gp = cms_gate.receipt("OPEN", ["CONNECTED_LANE_REQUIRED"], "a"*40, "b"*64, "c"*64)
        owner = Lifecycle(gp, datetime.now(timezone.utc) + timedelta(minutes=4))
        owner.register_closure(acceptors=lambda: True, issuer=lambda: True,
                               cp=lambda: True, private=lambda: True)
        with owner:
            result = cp.resolve_and_validate(owner, consumer_token="c"*32,
                validator_token="v"*32, tenant_id=self.tenant, organisation_id=self.org,
                country_code="ZA", organisation_kind="ORGANISATION")
        self.assertEqual([s[0] for s in seen], [
            "/v1/platform-context/resolve", "/v1/platform-context/validate"])
        self.assertEqual(seen[1][2], {"context_id": self.context_id, "subject_token": "c"*32})
        self.assertFalse(result["qualified"])
        self.assertIn("UNCERTIFIED", result["source"])

    def test_incorrect_cp_token_denied_without_transport(self):
        cp = HTTPSControlPlane.__new__(HTTPSControlPlane)
        cp.transport = lambda *_: self.fail("network should not be used")
        with self.assertRaises(Refused):
            cp._post("/v1/platform-context/resolve", "short", {}, 1)
        with self.assertRaises(Refused):
            cp._post("/v1/private/admin", "c"*32, {}, 1)


if __name__ == "__main__":
    unittest.main()
