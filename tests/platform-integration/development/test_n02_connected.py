"""N02/DEV-04 same-run checkpoint regressions (source-only, NOT acceptance)."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import dev
import n02_connected as join

RUN = "a" * 32
IAM = "b" * 40
SHARED = "c" * 40
CP = "d" * 40
INFRA = "e" * 40


class N02CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.state = {
            "run_id": RUN, "phase": "TESTED", "tests": True,
            "sources": {"baobab-iam": IAM, "shared": SHARED, "baobab-cp": CP},
            "harness_sha": INFRA, "deadline": time.time() + 300,
        }
        self.browser = {
            "schema": "baobab.iam.n02.browser-observation.v1",
            "classification": "REAL_BROWSER_SYNTHETIC_DATA",
            "run_id": RUN, "source_sha": IAM,
            "shared_source_sha": SHARED, "cp_source_sha": CP,
            "infrastructure_harness_sha": INFRA,
            "cases": {name: "OBSERVED" for name in join.EXPECTED},
            "provider_and_cp_independently_attested": False,
            "protected_accepted": False,
        }

    def original(self):
        payload = self.root / "browser-observation.json"
        dev.write(payload, self.browser)
        digest = self.root / "browser-observation.sha256"
        digest.write_text(hashlib.sha256(payload.read_bytes()).hexdigest() + "\n")
        digest.chmod(0o600)

    def test_private_original_current_run_binding_and_pre_deactivation(self):
        self.original()
        checkpoint = join.inspect_original(self.root, self.state, self.root)
        self.assertEqual(checkpoint["phase"], "BEFORE_INT03C_DEACTIVATION")
        self.assertEqual(checkpoint["run_id"], RUN)
        self.assertEqual(checkpoint["classification"], "ORIGINAL_BROWSER_RECONCILED_UNATTESTED")
        self.assertFalse(checkpoint["provider_independently_attested"])
        self.assertFalse(checkpoint["protected_accepted"])
        with (patch.object(dev, "current", return_value=(self.root, self.state)),
              patch.object(dev, "verify_sources"),
              patch.object(dev, "compose") as actual_live_health,
              patch.object(dev, "persist") as persisted):
            self.assertEqual(join.checkpoint(RUN, self.root, max_wait_seconds=0), checkpoint)
            actual_live_health.assert_called_once()
            persisted.assert_called_once()
        self.assertEqual(self.state["n02_browser_checkpoint"], checkpoint)

    def test_negative_absent_skipped_wrong_source_and_digest(self):
        for key, mutate in (
            ("run", lambda b: b.update(run_id="f" * 32)),
            ("cp", lambda b: b.update(cp_source_sha="f" * 40)),
            ("shared", lambda b: b.update(shared_source_sha="f" * 40)),
            ("iam", lambda b: b.update(source_sha="f" * 40)),
            ("harness", lambda b: b.update(infrastructure_harness_sha="f" * 40)),
            ("skip", lambda b: b["cases"].update({next(iter(join.EXPECTED)): "BLOCKED"})),
            ("protected", lambda b: b.update(protected_accepted=True)),
        ):
            with self.subTest(key=key):
                self.browser = dict(self.browser, cases=dict(self.browser["cases"]))
                mutate(self.browser)
                self.original()
                with self.assertRaises(dev.Refused):
                    join.inspect_original(self.root, self.state, self.root)
                self.browser = {**self.browser, "run_id": RUN, "source_sha": IAM,
                                "shared_source_sha": SHARED, "cp_source_sha": CP,
                                "infrastructure_harness_sha": INFRA,
                                "protected_accepted": False,
                                "cases": {name: "OBSERVED" for name in join.EXPECTED}}
        self.original()
        (self.root / "browser-observation.sha256").write_text("f" * 64 + "\n")
        (self.root / "browser-observation.sha256").chmod(0o600)
        with self.assertRaises(dev.Refused):
            join.inspect_original(self.root, self.state, self.root)

    def test_absent_real_browser_fails_without_false_positive(self):
        with (patch.object(dev, "current", return_value=(self.root, self.state)),
              patch.object(dev, "verify_sources"),
              patch.object(dev, "compose") as observed,
              patch.object(dev, "persist") as persisted):
            with self.assertRaises(dev.Refused):
                join.checkpoint(RUN, self.root, max_wait_seconds=0)
            observed.assert_not_called()
            persisted.assert_not_called()


if __name__ == "__main__":
    unittest.main()
