"""DEV-14 source-only planner tests: cannot fabricate runtime acceptance."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).with_name("engine_onboarding.py")
spec = importlib.util.spec_from_file_location("engine_onboarding", MODULE)
onboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(onboard)


def example():
    return {
        "schema": "baobab.engine-integration-profile.v1",
        "profile_key": "pulse-intelligence",
        "mode": "l4",
        "services": {
            "required": [
                {"key": "iam", "kind": "iam"},
                {"key": "control-plane", "kind": "control-plane"},
                {"key": "subject", "kind": "engine"},
            ],
            "optional": [{"key": "cache", "kind": "redis"}],
        },
    }


def receipt():
    return {
        "scope": "SOURCE_PROFILE_VALIDATION_ONLY",
        "protected_acceptance": False,
        "production_authorized": False,
        "service_order": ["iam", "control-plane", "subject"],
        "capabilities": ["intelligence.evidence.search"],
        "owner_support": "NOT_INSPECTED",
    }


class EngineOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.shared = self.root / "shared"
        self.shared.mkdir()
        self.path = self.shared / onboard.PROFILE_DIR / "pulse-intelligence.json"
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps(example()))

    def mocked(self):
        return (
            patch.object(onboard, "git_identity", return_value=(onboard.SHARED_SHA, True)),
            patch.object(onboard, "shared_validate", return_value=receipt()),
        )

    def test_valid_source_plan_never_claims_runtime_acceptance(self):
        with self.mocked()[0], self.mocked()[1]:
            result = onboard.source_plan("pulse-intelligence", self.shared)
        self.assertEqual(result["result"], "BLOCKED")
        self.assertEqual(result["evidence_class"], "SOURCE")
        self.assertEqual(result["eng_onb_runtime_cases"], "NOT_EXECUTED")
        self.assertIn("ENGINE_SOURCE_NOT_INSPECTED", result["blockers"])
        self.assertIn("REQUIRED_IMAGE_DIGEST_MISSING", result["blockers"])
        self.assertIn("RUNTIME_ADAPTER_NOT_QUALIFIED", result["blockers"])
        self.assertEqual(result["required_service_order"], ["iam", "control-plane", "subject"])
        self.assertIsNone(result["required_images"]["iam"])
        self.assertFalse(result["production_authorized"])

    def test_missing_and_wrong_shared_pin_are_rejected(self):
        with patch.object(onboard, "git_identity", return_value=("0" * 40, True)):
            with self.assertRaisesRegex(onboard.Refused, "SHARED_SOURCE_PIN_MISMATCH"):
                onboard.source_plan("pulse-intelligence", self.shared)

    def test_dirty_shared_is_rejected(self):
        with patch.object(onboard, "git_identity", return_value=(onboard.SHARED_SHA, False)):
            with self.assertRaisesRegex(onboard.Refused, "SHARED_SOURCE_PIN_MISMATCH"):
                onboard.source_plan("pulse-intelligence", self.shared)

    def test_unknown_profile_and_path_are_rejected(self):
        with self.assertRaisesRegex(onboard.Refused, "PROFILE_NAME_REFUSED"):
            onboard.source_plan("../pulse-intelligence", self.shared)

    def test_duplicate_profile_key_is_rejected(self):
        self.path.write_text('{"schema":"x","schema":"y"}')
        with self.mocked()[0]:
            with self.assertRaisesRegex(onboard.Refused, "DUPLICATE_JSON_KEY"):
                onboard.source_plan("pulse-intelligence", self.shared)

    def test_symlink_profile_is_rejected(self):
        other = self.root / "elsewhere.json"
        other.write_text(json.dumps(example()))
        self.path.unlink()
        self.path.symlink_to(other)
        with self.mocked()[0]:
            with self.assertRaisesRegex(onboard.Refused, "SOURCE_FILE_REQUIRED"):
                onboard.source_plan("pulse-intelligence", self.shared)

    def test_owner_shall_match_exact_sha_and_be_clean(self):
        owner = self.root / "baobab-pulse"
        owner.mkdir()
        with patch.object(onboard, "git_identity",
                          side_effect=[(onboard.SHARED_SHA, True), ("a"*40, True)]):
            with self.assertRaisesRegex(onboard.Refused, "ENGINE_SOURCE_PIN_MISMATCH"):
                onboard.source_plan("pulse-intelligence", self.shared, owner, "b"*40)

    def test_owner_without_pin_is_rejected(self):
        owner = self.root / "baobab-pulse"
        owner.mkdir()
        with self.mocked()[0]:
            with self.assertRaisesRegex(onboard.Refused, "ENGINE_SOURCE_PIN_REQUIRED"):
                onboard.source_plan("pulse-intelligence", self.shared, owner)

    def test_unpinned_or_foreign_image_cannot_become_ready(self):
        images = self.root / "images.json"
        for values, expected in [
            ({"subject": "baobab-pulse:latest"}, "IMAGE_DIGEST_REQUIRED"),
            ({"unknown": "python@sha256:"+"a"*64}, "IMAGE_LOCK_UNKNOWN_SERVICE"),
        ]:
            images.write_text(json.dumps({
                "schema": "infrastructure.dev14.images.v1",
                "profile_key": "pulse-intelligence", "images": values,
            }))
            with self.mocked()[0], self.mocked()[1]:
                with self.assertRaisesRegex(onboard.Refused, expected):
                    onboard.source_plan("pulse-intelligence", self.shared, image_lock=images)

    def test_even_all_digest_pins_do_not_pretend_execution(self):
        images = self.root / "images.json"
        images.write_text(json.dumps({
            "schema": "infrastructure.dev14.images.v1",
            "profile_key": "pulse-intelligence",
            "images": {key: "sample@sha256:"+"f"*64 for key in ("iam", "control-plane", "subject")},
        }))
        with self.mocked()[0], self.mocked()[1]:
            result = onboard.source_plan("pulse-intelligence", self.shared, image_lock=images)
        self.assertEqual(result["missing_image_pins"], [])
        self.assertEqual(result["result"], "BLOCKED")
        self.assertFalse(result["protected_acceptance"])

    def test_shared_validation_failure_denies_admission(self):
        with patch.object(onboard, "git_identity", return_value=(onboard.SHARED_SHA, True)):
            with patch.object(onboard, "shared_validate", side_effect=onboard.Refused("SHARED_PROFILE_REFUSED")):
                with self.assertRaisesRegex(onboard.Refused, "SHARED_PROFILE_REFUSED"):
                    onboard.source_plan("pulse-intelligence", self.shared)


if __name__ == "__main__":
    unittest.main()
