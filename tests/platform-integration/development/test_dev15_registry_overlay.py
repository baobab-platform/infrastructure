"""Private DEV-15 client registry overlay: no issuance, grants or mutable source."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("dev15_registry_overlay", HERE / "dev15_registry_overlay.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
import adapter
import dev


class RegistryOverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.private = self.root / "run"
        self.private.mkdir(mode=0o700)
        self.shared = self.root / "shared"
        self.shared.mkdir()
        self.source = self.shared / mod.dev15_registry.SHARED_REGISTRY
        self.source.parent.mkdir(parents=True)
        self.source.write_text("workloads:\n  synthetic-development: {status: ACTIVE}\n")
        for name in mod.dev15_registry.PROFILE_NAMES:
            file = self.shared / mod.onboard.PROFILE_DIR / (name + ".json")
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text('{"profile_key":"' + name + '"}')
        self.state = {
            "environment": "development", "phase": "PREPARED",
            "lease_seconds": 3600,
        }

    def install(self):
        with patch.dict("os.environ", {"BAOBAB_ENVIRONMENT": "development"}), \
                patch.object(mod.dev, "current", return_value=(self.private, self.state)), \
                patch.object(mod.onboard, "git_identity", return_value=(mod.onboard.SHARED_SHA, True)), \
                patch.object(mod.dev15_registry, "validate", return_value={
                    "registered_development_clients": [str(i) for i in range(6)]
                }):
            return mod.install("f" * 32, self.shared)

    def test_source_overlay_is_atomic_and_remains_not_issued(self):
        receipt = self.install()
        self.assertEqual(receipt["result"], "SOURCE_MOUNT_PREPARED")
        self.assertEqual(receipt["real_iam_credentials"], "NOT_PROVISIONED")
        self.assertEqual(receipt["connected_acceptance"], "BLOCKED")
        path = self.private / mod.NAME
        self.assertEqual(path.read_bytes(), self.source.read_bytes())
        self.assertEqual(self.state["dev15_registry_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertFalse(receipt["production_authorized"])

    def test_second_install_does_not_override_locked_registry(self):
        self.install()
        with self.assertRaisesRegex(dev.Refused, "DEV15_REGISTRY_PREPARED_ONLY"):
            self.install()

    def test_dev01_source_verification_catches_tampering(self):
        self.install()
        self.state["sources"] = {}
        dev.verify_sources(self.private, self.state)
        (self.private / mod.NAME).write_text("workloads: {}\n")
        with self.assertRaisesRegex(dev.Refused, "DEV15_REGISTRY_SOURCE_DRIFT"):
            dev.verify_sources(self.private, self.state)

    def test_protected_environment_cannot_install_overlay(self):
        with patch.dict("os.environ", {"BAOBAB_ENVIRONMENT": "staging"}):
            with self.assertRaisesRegex(dev.Refused, "EXPLICIT_DEVELOPMENT_REQUIRED"):
                mod.install("f" * 32, self.shared)

    def test_baseline_compose_source_is_unchanged_without_dev15_marker(self):
        from inspect import getsource
        self.assertIn("sources/shared/contracts/identity/v1/workload-registry.yaml", getsource(adapter.composition))
        self.assertIn("dev15-workload-registry.yaml", getsource(adapter.composition))
        self.assertIn("DEV15_REGISTRY_DRIFT", getsource(adapter.composition))


if __name__ == "__main__":
    unittest.main()
