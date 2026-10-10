"""Pure validation tests. No stage credentials or bearer tokens used in CI."""
import copy
import datetime as dt
import sys
from pathlib import Path
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from peo_cross_engine_relay import canonical_digest, verify_delivery

class RelayEvidenceValidationTest(unittest.TestCase):
    def setUp(self):
        now = dt.datetime.now(dt.timezone.utc)
        grant = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        correlation = str(uuid.uuid4())
        payload = {
            "specversion": "1.0",
            "id": event_id,
            "type": "com.baobab-platform.control-plane.founding-sponsorship.suspended.v1",
            "source": "urn:baobab-platform:service:baobab-cp",
            "subject": "founding-governance/" + grant,
            "dataschema": "https://contracts.baobab-platform.com/admission/v2/"
                          "founding-lifecycle-events.schema.json#/$defs/SponsorshipSuspended",
            "correlationid": correlation,
            "data": {"sponsorship_id": grant, "operating_organisation_id": str(uuid.uuid4()),
                     "status": "SUSPENDED"},
        }
        def stamp(seconds):
            return (now + dt.timedelta(seconds=seconds)).isoformat()
        self.grant = grant
        self.correlation = correlation
        self.cp = {
            "outbox_id": str(uuid.uuid4()),
            "aggregate_id": grant, "correlation_id": correlation,
            "event_type": payload["type"], "payload": payload, "publish_attempts": 2,
            "occurred_at": stamp(0), "published_at": stamp(4),
        }
        self.sub = {
            "event_id": event_id, "aggregate_id": grant, "event_type": payload["type"],
            "event_source": payload["source"], "envelope": copy.deepcopy(payload),
            "payload_sha256": "0" * 64, "received_by_client_id": "baobab-cp",
            "received_at": stamp(3), "processed_at": stamp(3.2),
        }

    def check(self):
        return verify_delivery(self.cp, self.sub, grant=self.grant,
                               correlation=self.correlation, expected_client="baobab-cp")

    def test_exact_dual_database_correlation(self):
        proof = self.check()
        self.assertEqual(proof["result"], "PROVED")
        self.assertEqual(proof["producer_attempts"], 2)
        self.assertEqual(proof["cross_engine_canonical_sha256"], canonical_digest(self.cp["payload"]))

    def test_reject_wrong_iam_workload(self):
        self.sub["received_by_client_id"] = "unexpected-client"
        with self.assertRaisesRegex(ValueError, "do not converge"):
            self.check()

    def test_reject_different_recipient_envelope(self):
        self.sub["envelope"]["data"]["status"] = "REVOKED"
        with self.assertRaisesRegex(ValueError, "different"):
            self.check()

    def test_reject_before_ack_publish(self):
        self.cp["published_at"] = None
        with self.assertRaisesRegex(ValueError, "do not converge"):
            self.check()

    def test_reject_fabricated_correlation(self):
        self.cp["correlation_id"] = str(uuid.uuid4())
        with self.assertRaisesRegex(ValueError, "do not converge"):
            self.check()

    def test_reject_temporally_impossible_ack(self):
        self.cp["published_at"] = self.cp["occurred_at"]
        with self.assertRaisesRegex(ValueError, "durable receiver"):
            self.check()

    def test_reject_missing_inbox_digest(self):
        self.sub["payload_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.check()

if __name__ == "__main__":
    unittest.main()
