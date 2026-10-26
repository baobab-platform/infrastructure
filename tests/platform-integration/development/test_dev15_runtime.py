"""DEV-15 runner keeps the real DEV-01 teardown and no authority shortcuts."""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("dev15_runtime", BASE / "dev15_runtime.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


class NativeRunnerTests(unittest.TestCase):
    def test_native_phases_reuse_existing_dev01_lease_and_teardown(self):
        events = []
        with patch.dict("os.environ", {"BAOBAB_ENVIRONMENT": "development"}), \
                patch.object(RUNNER.dev, "prepare", side_effect=lambda **kw: events.append(("prepare", kw)) or "f"*32), \
                patch.object(RUNNER.dev, "guarded", side_effect=lambda _run: nullcontext()), \
                patch.object(RUNNER, "plan_native", side_effect=lambda *_: events.append("plan")), \
                patch.object(RUNNER.dev, "up", side_effect=lambda *_: events.append("up")), \
                patch.object(RUNNER, "build_and_run", side_effect=lambda *_: events.append("native")), \
                patch.object(RUNNER.dev, "test", side_effect=lambda *_: events.append("baseline")), \
                patch.object(RUNNER.dev, "down", side_effect=lambda *_: events.append("teardown")), \
                patch.object(RUNNER.dev, "recover", side_effect=lambda **_: events.append("recover")):
            result = RUNNER.run_native("pulse-intelligence", Path("."), 600)
        self.assertEqual(result, 0)
        self.assertEqual(events[0], ("prepare", {"lease": 600, "lock_name": "external-base-lock.json"}))
        self.assertEqual(events[1:], ["plan", "up", "native", "baseline", "teardown", "recover"])

    def test_failure_still_destroys_disposable_run(self):
        events = []
        with patch.dict("os.environ", {"BAOBAB_ENVIRONMENT": "development"}), \
                patch.object(RUNNER.dev, "prepare", return_value="f"*32), \
                patch.object(RUNNER.dev, "guarded", side_effect=lambda _run: nullcontext()), \
                patch.object(RUNNER, "plan_native", return_value=None), \
                patch.object(RUNNER.dev, "up", side_effect=RUNNER.dev.Refused("IAM_UNAVAILABLE")), \
                patch.object(RUNNER.dev, "down", side_effect=lambda *_: events.append("teardown")), \
                patch.object(RUNNER.dev, "recover", side_effect=lambda **_: events.append("recover")):
            with self.assertRaisesRegex(RUNNER.dev.Refused, "IAM_UNAVAILABLE"):
                RUNNER.run_native("payments-sandbox", Path("."), 600)
        self.assertEqual(events, ["teardown", "recover"])

    def test_non_development_refuses_before_any_preparation(self):
        with patch.dict("os.environ", {"BAOBAB_ENVIRONMENT": "staging"}), \
                patch.object(RUNNER.dev, "prepare") as prepare:
            with self.assertRaisesRegex(RUNNER.dev.Refused, "EXPLICIT_DEVELOPMENT_REQUIRED"):
                RUNNER.run_native("pulse-intelligence", Path("."), 3600)
        prepare.assert_not_called()

    def test_no_source_validation_means_no_runtime_start(self):
        with patch.object(RUNNER.dev15_source, "checked_lock", return_value={
            "adopters": {"pulse-intelligence": {"sha": "a" * 40}}
        }), \
                patch.object(RUNNER.dev, "current", return_value=(Path("."), {"phase":"PREPARED"})), \
                patch.object(RUNNER, "owner_source", return_value=Path(".")), \
                patch.object(RUNNER.onboard, "source_plan", return_value={
                    "owner_support": "NOT_INSPECTED", "result": "BLOCKED",
                    "eng_onb_runtime_cases": "NOT_EXECUTED",
                }), \
                patch.object(RUNNER.dev15_registry_overlay, "install") as install:
            with self.assertRaisesRegex(RUNNER.dev.Refused, "DEV15_OWNER_CONTRACT_REFUSED"):
                RUNNER.plan_native("f"*32, "pulse-intelligence", Path("."))
        install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
