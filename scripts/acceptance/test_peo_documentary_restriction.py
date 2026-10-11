"""Synthetic-only, offline tests for PEO-02T proof verifier."""
import unittest
from datetime import datetime, timedelta, timezone

from peo_documentary_restriction import (
    POLICY, ProofDenied, reviewed_endpoint, verify_decision,
)

NOW = datetime(2026, 10, 11, 6, 0, 0, tzinfo=timezone.utc)
CONTEXT = "0190a1b2-c3d4-7e8f-9a0b-1c2d3e4f5a6b"
ORG = "0190a1b2-c3d4-7e8f-9a0b-1c2d3e4f5a6c"
CAP = "trade.checkout"
OP = "synthetic/documentary/held"


def payload(blocked: bool = True) -> dict:
    return {
        "context_id": CONTEXT,
        "organisation_id": ORG,
        "capability": CAP,
        "market": "ZA",
        "operation_reference": OP,
        "blocked": blocked,
        "authority_granted": False,
        "policy_reference": POLICY,
        "evaluated_at": (NOW - timedelta(milliseconds=300)).isoformat(),
        "expires_at": (NOW + timedelta(milliseconds=1500)).isoformat(),
    }


def check(obj: object, blocked: bool = True):
    return verify_decision(
        obj, context=CONTEXT, organisation=ORG, capability=CAP,
        market="ZA", operation=OP, expected_blocked=blocked, now=NOW,
    )


class DocumentaryStagingEvidenceTests(unittest.TestCase):
    def test_blocked_and_clear_are_both_negative_only(self):
        self.assertTrue(check(payload())["blocked"])
        self.assertFalse(check(payload(False), blocked=False)["blocked"])
        self.assertFalse(check(payload(False), blocked=False)["authority_granted"])

    def test_mismatch_and_expired_or_overlong_lease_deny(self):
        cases = [
            {"context_id": "other-context"},
            {"organisation_id": "other-org"},
            {"capability": "payments.capture"},
            {"market": "UG"},
            {"operation_reference": "another-operation"},
            {"policy_reference": "applicant-claim"},
            {"authority_granted": True},
            {"blocked": False},
            {"blocked": "true"},
            {"expires_at": (NOW - timedelta(seconds=1)).isoformat()},
            {"expires_at": (NOW + timedelta(seconds=9)).isoformat()},
            {"evaluated_at": (NOW - timedelta(seconds=10)).isoformat()},
            {"evaluated_at": (NOW + timedelta(seconds=5)).isoformat()},
        ]
        for mutation in cases:
            with self.subTest(mutation=mutation):
                with self.assertRaises(ProofDenied):
                    check({**payload(), **mutation})
        for invalid in (None, "", [], {}):
            with self.assertRaises(ProofDenied):
                check(invalid)

    def test_only_explicit_https_hosts_are_allowed(self):
        allow = {"iam.example.test", "cp.example.test"}
        self.assertEqual(
            reviewed_endpoint("https://cp.example.test/", allow),
            "https://cp.example.test",
        )
        for candidate in (
            "http://cp.example.test",
            "https://other.example.test",
            "https://user:pass@cp.example.test",
            "https://cp.example.test?evil=1",
            "https://cp.example.test/#fragment",
        ):
            with self.subTest(endpoint=candidate):
                with self.assertRaises(ProofDenied):
                    reviewed_endpoint(candidate, allow)


if __name__ == "__main__":
    unittest.main()
