"""N07 source-locked real Redis observation/teardown validation negatives.

These are source contract tests, not a mocked positive real runtime receipt.
The actual Docker services are owned by n07_disposable.py in separate CI.
"""
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

    def test_native_n07_configuration_preserves_original_hydra_and_acl_hashing(self):
        # Real configure path regression: the N07 digest code must not create
        # a function-local hashlib binding before introspection is prepared.
        source = self.path / "sources" / "baobab-iam" / "config" / "ory"
        (source / "hydra").mkdir(parents=True)
        (source / "kratos").mkdir(parents=True)
        (source / "hydra" / "hydra.yml").write_text("urls: http://127.0.0.1:4444\\n")
        (source / "kratos" / "kratos.yml").write_text("url: http://127.0.0.1:4433/\\n")
        (source / "kratos" / "identity.schema.json").write_text("{}\\n")
        state = {
            "run_id": "a" * 32,
            "n07_profile": True,
            "secrets": {
                "introspection": "native-introspection-key",
                "verifier": "native-verifier-key",
                "admin": "native-admin-key",
                "hook": "h" * 64,
                "redis": "r" * 64,
            },
        }
        adapter.configure(self.path, state)
        htpasswd = (self.path / "introspection.htpasswd").read_text()
        acl = (self.path / "n07-redis.acl").read_text()
        self.assertIn("baobab-dev-introspection:{SHA}", htpasswd)
        self.assertIn("user n07 on #", acl)
        self.assertNotIn(state["secrets"]["redis"], acl)
        self.assertIn("tls-port 6380", (self.path / "n07-redis.conf").read_text())

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
        self.assertEqual(candidate["sources"]["shared"],
                         "7f547ccdd759208355ef9224d2177929f4bf224e")
        self.assertEqual(candidate["sources"]["baobab-cp"],
                         "a5e5458ea6651657a66698b60b765eca5774daf4")
        self.assertEqual(candidate["sources"]["zuribeans"],
                         "d08643d5275dff8a25b60e0181dadec6c26ee840")
        self.assertEqual(candidate["sources"]["nabhold"],
                         "7f25aaea378d420e04c4f4f735b03613c518c419")

    def test_native_redis_uses_pinned_image_and_private_network(self):
        # Optional N07 Redis must not mutate the existing DEV-04 service inventory.
        self.assertNotIn("redis", adapter.SERVICES)
        state = {
            **self.state, "uid":1000,"gid":1000,"deadline":2000000000,
            "run_id":"a"*32,
            "project":"dev01-"+"a"*32,
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

    def test_original_custody_refuses_symlink_and_ambiguous_json(self):
        import json
        observation = self.path / "n07-redis-observation.json"
        external = self.path / "foreign-observation.json"
        dev.write(external, original(self.state))
        observation.symlink_to(external)
        with self.assertRaises((OSError, dev.Refused)):
            n07_disposable.inspect_redis(self.path, self.state)
        observation.unlink()
        # Duplicate keys in a putative producer receipt must not let the
        # parser choose a convenient final acceptance or source value.
        raw = json.dumps(original(self.state), separators=(",", ":"))
        raw = raw[:-1] + ',"run_id":"' + "b"*32 + '"}'
        observation.write_text(raw)
        observation.chmod(0o600)
        with self.assertRaises(dev.Refused):
            n07_disposable.inspect_redis(self.path, self.state)

    def test_original_custody_refuses_group_read_and_hardlinks(self):
        original_path = self.path / "n07-redis-observation.json"
        self.save(original(self.state))
        original_path.chmod(0o640)
        with self.assertRaises(dev.Refused):
            n07_disposable.inspect_redis(self.path, self.state)
        original_path.chmod(0o600)
        linked = self.path / "n07-original-hardlink.json"
        linked.hardlink_to(original_path)
        with self.assertRaises(dev.Refused):
            n07_disposable.inspect_redis(self.path, self.state)

    def test_redis_probe_requires_exact_run_private_identity(self):
        with patch.dict("os.environ",{"DEV01_RUN_ID":"untrusted"}):
            with self.assertRaises(n07_redis_probe.Blocked):
                n07_redis_probe.read_state()

    def test_probe_state_source_refuses_symlinks_duplicate_keys_and_oversize(self):
        import json
        state = {
            "run_id": "a" * 32, "environment": "development",
            "n07_profile": True, "lock_file": "n07-base-lock.json",
            "phase": "RUNNING", "secrets": {"redis": "0" * 64},
        }
        file = self.path / "state.json"
        dev.write(file, state)
        with (patch.object(n07_redis_probe, "RUN", str(self.path)),
              patch.dict("os.environ", {"DEV01_RUN_ID": "a" * 32})):
            self.assertEqual(n07_redis_probe.read_state(), state)
            file.unlink()
            target = self.path / "state-other.json"
            dev.write(target, state)
            file.symlink_to(target)
            with self.assertRaises(OSError):
                n07_redis_probe.read_state()
            file.unlink()
            doc = json.dumps(state)[:-1] + ',"run_id":"' + "b" * 32 + '"}'
            file.write_text(doc)
            file.chmod(0o600)
            with self.assertRaises(n07_redis_probe.Blocked):
                n07_redis_probe.read_state()
            file.write_bytes(b"x" * (1_048_577))
            with self.assertRaises(n07_redis_probe.Blocked):
                n07_redis_probe.read_state()

    def test_redis_wire_is_protocol_data_not_shell(self):
        self.assertEqual(
            n07_redis_probe.wire(b"PING"),
            b"*1\r\n$4\r\nPING\r\n",
        )


if __name__ == "__main__":
    unittest.main()
