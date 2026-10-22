"""Scenario semantics and held-state tests. These are NOT live qualification."""
import unittest

import cms_gate
from cms_nab03 import CONTENT, HTTP, ObservationRegister, Refused, blocked_receipt, case_verdict


TENANT = "9e493b9a-1665-4655-9dd9-c00bbd26c5bb"


def active_gate(state="OPEN"):
    return cms_gate.receipt(state, ["CONNECTED_LANE_REQUIRED"], "a" * 40, "b" * 64, "c" * 64)


def positive(key="home"):
    return HTTP(200, tenant_id=TENANT, content_key=key,
                publication_state="PUBLISHED", record_present=True)


def bad(status, code, endpoint="cms"):
    return HTTP(status, code=code, endpoint=endpoint)


def absent(key="home"):
    return HTTP(200, content_key=key)


class Cases(unittest.TestCase):
    def test_all_fourteen_have_exact_success_shape(self):
        observations = {
            "published-home-nav-footer": tuple(positive(k) for k in CONTENT),
            "wrong-audience-token": (bad(401, "AUTHENTICATION_REQUIRED"),),
            "wrong-credential": (bad(401, "AUTHENTICATION_REQUIRED"),),
            "disabled-caller": (bad(401, "AUTHENTICATION_REQUIRED"),),
            "expired-caller-token": (bad(401, "AUTHENTICATION_REQUIRED"),),
            "revoked-caller-token": (bad(401, "AUTHENTICATION_REQUIRED"),),
            "missing-grant": (bad(403, "CONTEXT_DENIED", "cp"),),
            "wrong-owner-or-context": (bad(403, "CONTENT_CONTEXT_REJECTED"),),
            "neighbour-tenant": (bad(403, "CONTENT_CONTEXT_REJECTED"),),
            "draft-or-preview": (bad(403, "CONTENT_PREVIEW_NOT_PERMITTED"), absent()),
            "withdrawn-content": (absent(),),
            "dependency-outage-and-restoration": (bad(503, "CONTENT_CONTEXT_UNAVAILABLE"), positive()),
            "validator-negatives": (bad(401, "SUBJECT_TOKEN_INVALID", "cp"),
                                    bad(403, "CONTENT_CONTEXT_REJECTED")),
            "teardown": ("VERIFIED_ACCEPTORS", "VERIFIED_ISSUER",
                         "VERIFIED_CP", "VERIFIED_PRIVATE"),
        }
        self.assertEqual(set(observations), set(cms_gate.CASES))
        for case, items in observations.items():
            with self.subTest(case=case):
                self.assertTrue(case_verdict(case, items, TENANT))
        result = ObservationRegister(active_gate(), TENANT, live=True)
        for case, items in observations.items():
            result.record(case, items)
        receipt = result.receipt()
        self.assertFalse(receipt["qualified"])
        self.assertFalse(receipt["full_int03_acceptance"])
        self.assertFalse(receipt["independent_acceptance"])
        self.assertEqual(len(receipt["cases"]), 14)
        self.assertEqual(set(receipt["cases"].values()), {"OBSERVED_UNATTESTED"})
        # Even a synthetic set of passing assertions can NEVER create an
        # acceptance receipt or authorize a CMS client.
        self.assertNotIn("ACCEPTED", receipt.values())

    def test_negatives_fail_if_wrong_http_or_missing(self):
        expected = {
            "published-home-nav-footer": (positive(),),
            "wrong-audience-token": (bad(200, ""),),
            "wrong-credential": (),
            "disabled-caller": (bad(503, "CONTENT_CONTEXT_UNAVAILABLE"),),
            "expired-caller-token": (bad(401, "SOMETHING_ELSE"),),
            "revoked-caller-token": (bad(403, "CONTENT_CONTEXT_REJECTED"),),
            "missing-grant": (bad(403, "CONTEXT_DENIED"),),
            "wrong-owner-or-context": (bad(404, "CONTENT_CONTEXT_REJECTED"),),
            "neighbour-tenant": (positive(),),
            "draft-or-preview": (absent(),),
            "withdrawn-content": (positive(),),
            "dependency-outage-and-restoration": (bad(503, "CONTENT_CONTEXT_UNAVAILABLE"),),
            "validator-negatives": (bad(401, "SUBJECT_TOKEN_INVALID", "cp"),),
            "teardown": ("VERIFIED_ACCEPTORS", "FAILED_ISSUER", "VERIFIED_CP", "VERIFIED_PRIVATE"),
        }
        for case, items in expected.items():
            with self.subTest(case=case):
                self.assertFalse(case_verdict(case, items, TENANT))

    def test_hold_blocks_registry_and_fake_evidence(self):
        for verdict in ("HELD", "REFUSED"):
            with self.assertRaises(Refused):
                ObservationRegister(active_gate(verdict), TENANT, live=True)
        with self.assertRaises(Refused):
            ObservationRegister(active_gate(), TENANT, live=False)
        b = blocked_receipt()
        self.assertEqual(len(b["cases"]), 14)
        self.assertEqual(set(b["cases"].values()), {"BLOCKED"})
        self.assertFalse(b["qualified"])
        self.assertFalse(b["identities_created"])

    def test_duplicate_or_unknown_case_never_advances(self):
        result = ObservationRegister(active_gate(), TENANT, live=True)
        item = (bad(401, "AUTHENTICATION_REQUIRED"),)
        result.record("wrong-credential", item)
        with self.assertRaises(Refused):
            result.record("wrong-credential", item)
        with self.assertRaises(Refused):
            result.record("different", item)
        with self.assertRaises(Refused):
            result.record("expired-caller-token", (bad(200, ""),))
        self.assertEqual(result.receipt()["cases"]["expired-caller-token"], "BLOCKED")

    def test_observation_shape_bounded(self):
        for kwargs in ({"status": 200, "endpoint": "fake"},
                       {"status": 200, "code": "x" * 121},
                       {"status": True}):
            with self.assertRaises(Refused):
                HTTP(**kwargs)
        self.assertFalse(case_verdict("wrong-credential", [{"status": 401}], TENANT))


if __name__ == "__main__":
    unittest.main()
