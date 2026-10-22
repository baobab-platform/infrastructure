"""Source tests: these cannot certify live IAM/CP integration."""
import copy
import unittest

from connected_identity_evidence import CASES, EvidenceRefused, validate

SOURCES = {"infrastructure": "a" * 40, "baobab-iam": "b" * 40,
           "baobab-cp": "c" * 40, "shared": "d" * 40}


def sample():
    cases = {}
    for name in CASES:
        status = (403 if name in ("wrong_audience_denied", "cross_tenant_denied",
                                 "revoked_credential_denied", "deactivated_principal_denied")
                  else None if name == "independent_teardown" else 200)
        cases[name] = {"result": "PASS", "http_status": status, "live": True}
    return {"schema": "infrastructure.int03c.connected-identity.v1",
            "sources": dict(SOURCES), "synthetic": True, "provider": "REAL_IAM_CP",
            "observations": cases, "teardown": "INDEPENDENTLY_VERIFIED",
            "qualified": True, "nab03_qualified": False}


class EvidenceTests(unittest.TestCase):
    def test_complete_shape(self):
        # Structural acceptance only: fixture is NOT actual live proof.
        self.assertTrue(validate(sample(), expected_sources=SOURCES))

    def test_missing_case(self):
        r = sample()
        del r["observations"]["cross_tenant_denied"]
        with self.assertRaises(EvidenceRefused):
            validate(r, expected_sources=SOURCES)

    def test_revocation_must_deny(self):
        r = sample()
        r["observations"]["revoked_credential_denied"]["http_status"] = 200
        with self.assertRaises(EvidenceRefused):
            validate(r, expected_sources=SOURCES)

    def test_no_mock_pass(self):
        r = sample()
        r["observations"]["cp_current_principal"]["live"] = False
        with self.assertRaises(EvidenceRefused):
            validate(r, expected_sources=SOURCES)

    def test_teardown_required(self):
        r = sample()
        r["teardown"] = "NOT_RUN"
        with self.assertRaises(EvidenceRefused):
            validate(r, expected_sources=SOURCES)

    def test_no_nab03_promotion(self):
        r = sample()
        r["nab03_qualified"] = True
        with self.assertRaises(EvidenceRefused):
            validate(r, expected_sources=SOURCES)

    def test_wrong_pin(self):
        r = sample()
        r["sources"]["baobab-cp"] = "e" * 40
        with self.assertRaises(EvidenceRefused):
            validate(r, expected_sources=SOURCES)

    def test_unqualified_failure_allowed(self):
        r = sample()
        r["observations"]["cross_tenant_denied"]["result"] = "FAIL"
        r["qualified"] = False
        self.assertFalse(validate(r, expected_sources=SOURCES))


if __name__ == "__main__":
    unittest.main()
