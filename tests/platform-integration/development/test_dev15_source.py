"""DEV-15 source-only matrix cannot downgrade canonical case requirements."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).with_name("dev15_source.py")
SPEC = importlib.util.spec_from_file_location("dev15_source", PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class Dev15SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.shared = self.root / "shared"
        self.shared.mkdir()
        self.owners = {key: self.root / key for key in MOD.ALLOWED}
        for name, path in self.owners.items():
            path.mkdir()
            document = {
                "subject_engine": MOD.ALLOWED[name].split("/")[-1],
                "reporting": {"case_ids": sorted(MOD.CASE_IDS) + [name + "-NATIVE"]},
            }
            source = self.shared / MOD.onboarding.PROFILE_DIR / (name + ".json")
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(json.dumps(document))
        self.lock = {
            "schema": "infrastructure.dev15.first-adopters.source-lock.v1",
            "shared": MOD.onboarding.SHARED_SHA,
            "adopters": {key: {"repo": repo, "sha": "a" * 40}
                         for key, repo in MOD.ALLOWED.items()},
            "environment": "development",
            "synthetic_only": True,
            "protected_acceptance": False,
        }

    def fake_plan(self, name, *_args):
        return {
            "source": {"engine_sha": "a" * 40, "profile_sha256": "f" * 64},
            "owner_support": "DECLARED_IMPLEMENTATION_ONLY",
            "result": "BLOCKED",
            "eng_onb_runtime_cases": "NOT_EXECUTED",
            "protected_acceptance": False,
            "production_authorized": False,
            "required_service_order": ["iam", "control-plane", "subject"],
            "blockers": ["RUNTIME_ADAPTER_NOT_QUALIFIED"],
        }

    def test_inventory_is_blocked_even_for_validated_owner_sources(self):
        with patch.object(MOD.onboarding, "source_plan", side_effect=self.fake_plan):
            data = MOD.reconcile(self.shared, self.owners, self.lock)
        self.assertFalse(data["eng_onb_runtime_qualified"])
        self.assertEqual(data["evidence_class"], "SOURCE_ONLY")
        for item in data["adopters"].values():
            self.assertEqual(item["runtime_status"], "BLOCKED")
            self.assertFalse(item["independently_verified_teardown"])
            self.assertTrue(all(x["result"] == "BLOCKED" and not x["evidence"]
                                for x in item["cases"].values()))

    def test_missing_canonical_case_is_rejected(self):
        p = self.shared / MOD.onboarding.PROFILE_DIR / "pulse-intelligence.json"
        data = json.loads(p.read_text())
        data["reporting"]["case_ids"].remove("ENG-ONB-09")
        p.write_text(json.dumps(data))
        with patch.object(MOD.onboarding, "source_plan", side_effect=self.fake_plan):
            with self.assertRaisesRegex(MOD.onboarding.Refused, "DEV15_REQUIRED_CASE_DRIFT"):
                MOD.reconcile(self.shared, self.owners, self.lock)

    def test_source_success_cannot_be_promoted_to_runtime(self):
        def fake_promote(name, *_args):
            item = self.fake_plan(name)
            item["result"] = "PASS"
            return item
        with patch.object(MOD.onboarding, "source_plan", side_effect=fake_promote):
            with self.assertRaisesRegex(MOD.onboarding.Refused, "DEV15_SOURCE_VALIDATION_INCOMPLETE"):
                MOD.reconcile(self.shared, self.owners, self.lock)

    def test_unexpected_owner_refused(self):
        with self.assertRaisesRegex(MOD.onboarding.Refused, "DEV15_OWNER_ROSTER_REQUIRED"):
            MOD.reconcile(self.shared, {"pulse-intelligence": self.owners["pulse-intelligence"]}, self.lock)


if __name__ == "__main__":
    unittest.main()
