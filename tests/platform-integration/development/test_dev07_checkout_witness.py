"""Source-only regressions. These examples are not native checkout evidence."""
from __future__ import annotations

import copy
import unittest

from dev07_checkout_witness import CheckoutWitnessRefused, verify_checkout


class CheckoutWitnessTests(unittest.TestCase):
    def setUp(self):
        self.bff = {
            "order_id": "order_" + "a" * 48,
            "idempotency_key": "dev07.test.qualified.1234",
            "traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01",
            "csrf_refused": True,
            "same_order_replayed": True,
            "native_sql_readback_observed": False,
        }
        self.origin = {
            "schema": "baobab.trade.dev11.native-origin.v1",
            "classification": "SOURCE_SQL_READBACK_ONLY",
            "native_origin_qualified": True,
            "reason": "NATIVE_ORIGIN_SQL_CONFIRMED",
            "native_order_readback": True,
            "enforced_b2b_commit": True,
            "exact_commit_transaction": True,
            "spend_commit_same_transaction": True,
            "current_iam_cp_authority_qualified": False,
            "native_erp_business_effect_qualified": False,
            "l4_ops_01": "BLOCKED",
            "production_authorized": False,
            "business_origin": {
                "order_id": self.bff["order_id"],
                "event_id": "11111111-1111-4111-8111-111111111111",
                "transaction_id": "405",
                "persisted_envelope_digest": "c" * 64,
                "traceparent": "00-" + "1" * 32 + "-" + "3" * 16 + "-01",
            },
        }
        self.meta = {"trade_sha": "a" * 40, "image_id": "sha256:" + "b" * 64,
                     "run_id": "c" * 32}

    def observe(self, bff=None, origin=None):
        return verify_checkout(bff if bff is not None else self.bff,
                               origin if origin is not None else self.origin, **self.meta)

    def test_source_only_witness_is_never_full_acceptance(self):
        report = self.observe()
        self.assertTrue(report["native_order_seller_buyer_spend_outbox_same_xid"])
        self.assertFalse(report["dev07_accepted"])
        self.assertEqual(report["l4_ops_01"], "BLOCKED")

    def test_different_trace_rejected(self):
        bad = copy.deepcopy(self.origin)
        bad["business_origin"]["traceparent"] = "00-" + "4" * 32 + "-" + "3" * 16 + "-01"
        with self.assertRaisesRegex(CheckoutWitnessRefused, "CAUSALLY_BOUND"):
            self.observe(origin=bad)

    def test_wrong_order_rejected(self):
        bad = copy.deepcopy(self.origin)
        bad["business_origin"]["order_id"] = "order_" + "b" * 48
        with self.assertRaisesRegex(CheckoutWitnessRefused, "CAUSALLY_BOUND"):
            self.observe(origin=bad)

    def test_unenforced_spend_rejected(self):
        bad = copy.deepcopy(self.origin)
        bad["spend_commit_same_transaction"] = False
        with self.assertRaisesRegex(CheckoutWitnessRefused, "SQL_NOT_QUALIFIED"):
            self.observe(origin=bad)

    def test_response_is_not_authoritative(self):
        bad = copy.deepcopy(self.bff)
        bad["native_sql_readback_observed"] = True
        with self.assertRaisesRegex(CheckoutWitnessRefused, "COMMIT_AND_REPLAY"):
            self.observe(bff=bad)

    def test_no_original_event_rejected(self):
        bad = copy.deepcopy(self.origin)
        del bad["business_origin"]
        with self.assertRaisesRegex(CheckoutWitnessRefused, "PROVENANCE"):
            self.observe(origin=bad)

    def test_source_classification_cannot_be_promoted(self):
        bad = copy.deepcopy(self.origin)
        bad["current_iam_cp_authority_qualified"] = True
        with self.assertRaisesRegex(CheckoutWitnessRefused, "SQL_NOT_QUALIFIED"):
            self.observe(origin=bad)


if __name__ == "__main__":
    unittest.main()
