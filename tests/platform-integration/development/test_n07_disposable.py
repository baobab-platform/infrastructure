"""N07 source-locked real Redis observation/teardown validation negatives.

These are source contract tests, not a mocked positive real runtime receipt.
The actual Docker services are owned by n07_disposable.py in separate CI.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
import dev
import n07_disposable
import adapter
import n07_redis_probe


def runtime_state():
    return {
        "run_id":"a"*32,
        "sources":{
            "shared":"1"*40, "baobab-cp":"2"*40,
            "baobab-iam":"3"*40,"thamani":"4"*40,
            "baobab-tms":"5"*40,
        },
        "runtime_images":{
            "redis":"redis@sha256:"+"f"*64,
        },
    }


def original(state):
    return {
        "schema":"infrastructure.n07.redis-original.v1",
        "classification":"REAL_REDIS_TLS_ACL_GETDEL_OBSERVED_UNATTESTED",
        "run_id":state["run_id"],
        "source_pins":state["sources"],
        "redis_image":state["runtime_images"]["redis"],
        "tls_verified":True,"run_lease_isolated":True,
        "acl_cross_tenant_denied":True,"anonymous_denied":True,
        "invalid_password_denied":True,"untrusted_certificate_denied":True,
        "cross_worker_getdel_live":False,"one_use_getdel_observed":True,
        "issuer_cp_connected_accepted":False,
        "tms_native_booking_accepted":False,"protected_accepted":False,
    }


class N07SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.state = runtime_state()

    def save(self, data):
        dev.write(self.path / "n07-redis-observation.json", data)

    def test_real_candidate_source_lock_does_not_alter_dev04(self):
        candidate = dev.load_lock("n07-base-lock.json")
        accepted = dev.load_lock("lock.json")
        self.assertEqual(set(candidate["sources"]), {
            "shared", "baobab-cp", "baobab-iam", "nabhold",
            "zuribeans", "thamani", "baobab-tms",
        })
        self.assertEqual(set(candidate["images"]) - set(accepted["images"]),
                         {"redis"})
        self.assertNotEqual(candidate["sources"]["baobab-iam"],
                            accepted["sources"]["baobab-iam"])
        self.assertTrue(candidate["synthetic_only"])
        self.assertFalse(candidate["protected_acceptance"])

    def test_native_redis_uses_pinned_image_and_private_network(self):
        self.assertIn("redis", adapter.SERVICES)
        state = {
            **self.state, "uid":1000,"gid":1000,"deadline":2000000000,
            "run_id":"a"*32,
            "n07_profile":True,
            "images":{"cp":"reviewed-project-cp"},
            "secrets":{"cp_db":"a", "iam_db":"b", "introspection":"c","verifier":"d",
                       "hook":"e","redis":"f"},
        }
        images = {**dev.load_lock("n07-base-lock.json")["images"]}
        # This is static Compose structure inspection, not Docker acceptance.
        root = self.path
        composition = adapter.composition(state,root,images,"reviewed-private-n07")
        redis = composition["services"]["redis"]
        self.assertEqual(redis["image"],images["redis"])
        self.assertEqual(redis["user"],"999:999")
        self.assertTrue(redis["read_only"])
        self.assertIn("ALL",redis["cap_drop"])
        self.assertNotIn("ports",redis)
        self.assertTrue(composition["networks"]["lab"]["internal"])
        self.assertEqual(redis["networks"]["lab"]["aliases"],["redis.baobab-dev.test"])

    def test_exact_original_only_records_component_readback(self):
        self.save(original(self.state))
        x = n07_disposable.inspect_redis(self.path,self.state)
        self.assertEqual(x["classification"],"REAL_TLS_REDIS_COMPONENT_UNATTESTED")
        self.assertFalse(x["tms_native_booking_accepted"])
        self.assertFalse(x["protected_accepted"])
        self.assertEqual(len(x["original_sha256"]),64)

    def test_unknown_source_or_overclaimed_proof_is_denied(self):
        for field,value in [
            ("run_id","b"*32),
            ("source_pins",{"baobab-iam":"foreign"}),
            ("tls_verified",False),
            ("one_use_getdel_observed",False),
            ("acl_cross_tenant_denied",False),
            ("cross_worker_getdel_live",True),
            ("issuer_cp_connected_accepted",True),
            ("tms_native_booking_accepted",True),
            ("protected_accepted",True),
        ]:
            with self.subTest(field=field):
                self.save({**original(self.state),field:value})
                with self.assertRaises(dev.Refused):
                    n07_disposable.inspect_redis(self.path,self.state)

    def test_redis_probe_requires_exact_run_private_identity(self):
        with patch.dict("os.environ",{"DEV01_RUN_ID":"untrusted"}):
            with self.assertRaises(n07_redis_probe.Blocked):
                n07_redis_probe.read_state()

    def test_redis_wire_is_protocol_data_not_shell(self):
        self.assertEqual(
            n07_redis_probe.wire(b"PING"),
            b"*1\r\n$4\r\nPING\r\n",
        )


if __name__ == "__main__":
    unittest.main()
