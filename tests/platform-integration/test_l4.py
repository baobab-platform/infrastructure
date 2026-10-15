"""INT-01 source and denial contracts, no Docker required."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("l4", BASE / "l4.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class L4ContractTest(unittest.TestCase):
    def test_static_preflight(self):
        m = mod.load()
        self.assertEqual(m["adr"], "ADR-SHARED-036")
        self.assertEqual(m["profiles"]["foundation"]["mandatory"], list(mod.REQUIRED))
        mod.preflight(m, static=True)

    def test_unresolved_image_cannot_run(self):
        m = mod.load()
        edited = dict(m["foundation_images"]["postgres"])
        edited["digest"] = "PENDING_VERIFIED_DIGEST"
        m["foundation_images"]["postgres"] = edited
        with self.assertRaises(mod.Blocked):
            mod.images(m)

    def test_unsafe_manifest_denial(self):
        m = mod.load()
        for key,val in [("contains_production_credentials", True), ("simulators", ["fake_cp"]),
                        ("classification", "PROTECTED_STAGING"), ("adr", "OTHER")]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as d:
                path = Path(d)/"m.json"
                path.write_text(json.dumps({**m,key:val}))
                with mock.patch.object(mod, "LOCK", path):
                    with self.assertRaises(mod.Blocked):
                        mod.load()

    def test_missing_scenario_denied(self):
        m = mod.load()
        p = {**m["profiles"]["foundation"], "mandatory":["L4-MAN-01"]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"m.json"
            path.write_text(json.dumps({**m,"profiles":{"foundation":p}}))
            with mock.patch.object(mod, "LOCK", path):
                with self.assertRaises(mod.Blocked):
                    mod.load()

    def test_public_host_port_denied(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/"compose.yaml"
            p.write_text("services:\n  redis:\n    ports:\n      - '0.0.0.0:6379:6379'\n")
            with mock.patch.object(mod,"COMPOSE",p):
                with self.assertRaises(mod.Blocked):
                    mod.load()

if __name__ == "__main__":
    unittest.main()
