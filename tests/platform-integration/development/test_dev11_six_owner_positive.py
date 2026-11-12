"""DEV-11 immutable six-source admission and genuine-buyer fail-closed tests.

No fixture here is classified as actual buyer acceptance or emitted as a
connected run artifact. All test evidence remains source-only.
"""
from __future__ import annotations
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from dev11_six_owner_positive import Blocked, OWNERS, LOCK, sources, qualify

class SourceAndBuyerQualification(TestCase):
    def create_sources(self, root):
        for owner in (*OWNERS, "infrastructure"):
            path = root / owner
            path.mkdir()
            (path / ".git").mkdir()
        return root

    def test_exact_all_six_source_heads_are_required(self):
        import json
        lock = json.loads(LOCK.read_text())
        with tempfile.TemporaryDirectory() as folder:
            root = self.create_sources(Path(folder))
            expected = iter([lock["sources"][owner] for owner in OWNERS] +
                            ["a" * 40])
            with patch.dict(os.environ, {"DEV11_INFRA_HEAD": "a"*40}), \
                 patch("dev11_six_owner_positive.subprocess.check_output",
                       side_effect=lambda cmd, **kw:
                       next(expected) + "\n" if cmd[-1] == "HEAD" else ""):
                self.assertEqual(sources(root)["sources"], lock["sources"])

    def test_wrong_sha_refused_before_loading_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = self.create_sources(Path(folder))
            with patch.dict(os.environ, {"DEV11_INFRA_HEAD": "a"*40}), \
                 patch("dev11_six_owner_positive.subprocess.check_output",
                       return_value="b"*40 + "\n"):
                with self.assertRaisesRegex(Blocked, "SOURCE_HEAD_MISMATCH"):
                    sources(root)

    def test_workflow_source_pins_are_identical_to_manifest_and_bff_owner(self):
        import json
        import re
        manifest = json.loads(LOCK.read_text())
        base = LOCK.parent.parent.parent.parent / ".github" / "workflows"
        workflow = (base / "dev11-six-owner-genuine.yml").read_text()
        bff = (base / "dev11-connected-bff-trade.yml").read_text()
        for owner, source in manifest["sources"].items():
            with self.subTest(owner=owner):
                self.assertEqual(workflow.count("ref: " + source + chr(10)), 1)
        self.assertIn("DEV11_TRADE_SHA=" + manifest["sources"]["baobab-trade"], bff)
        self.assertIn("DEV11_ZURIBEANS_SHA=" + manifest["sources"]["zuribeans"], bff)
        # No older competing source commits may hide in owner refs.
        refs = re.findall(r"(?m)^[ \t]+ref: ([a-f0-9]{40})$", workflow)
        self.assertEqual(set(refs), set(manifest["sources"].values()))
        self.assertIn("if: github.event_name == 'workflow_dispatch'", workflow)

    def test_untracked_source_changes_are_included_in_exact_commit_validation(self):
        import inspect
        from dev11_six_owner_positive import sources
        self.assertIn("--untracked-files=all", inspect.getsource(sources))
        self.assertNotIn("--untracked-files=no", inspect.getsource(sources))

    def test_source_preflight_pass_is_explicitly_not_runtime_acceptance(self):
        from dev11_six_owner_positive import safe_report
        report = safe_report("CURRENT_IAM_CP_AUTHORITY_UNVERIFIED", source_verified=True)
        self.assertTrue(report["source_pins_checked"])
        self.assertEqual(report["l4_ops_01"], "BLOCKED")
        self.assertFalse(report["genuine_iam_cp_buyer_commitment_authority_qualified"])
        self.assertFalse(report["independently_exported_full_trace"])

    def test_missing_real_six_owner_runtime_never_becomes_a_positive(self):
        with patch("dev11_six_owner_positive.sources",
                   return_value={"sources": {key: "a"*40 for key in OWNERS}}), \
             patch("dev11_six_owner_positive.containers",
                   side_effect=Blocked("SIX_OWNER_RUNTIME_NOT_RUNNING")):
            args = type("Args", (), {"root": Path("/never"), "project": None, "event_id": None})()
            report = qualify(args)
            self.assertEqual(report["l4_ops_01"], "BLOCKED")
            self.assertFalse(report["synthetic_event_accepted"])
            self.assertFalse(report["enforced_medusa_buyer_origin"])
            self.assertEqual(report["reason"], "SIX_OWNER_RUNTIME_NOT_RUNNING")

    def test_build_provenance_required_before_container_labels_can_claim_source(self):
        from dev11_six_owner_positive import containers
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(Blocked, "SIX_OWNER_IMAGE_PROVENANCE_MISSING"):
                containers("dev11-six-1234567890", {"sources": {}})

    def test_run_private_custody_refuses_outside_path_and_duplicate_keys(self):
        from dev11_six_owner_positive import private_original, no_duplicate_keys
        with self.assertRaisesRegex(Blocked, "GOVERNED_BUYER_EVENT_REQUIRED"):
            private_original(Path("/tmp/not-private-event"), 80,
                             "GOVERNED_BUYER_EVENT_REQUIRED")
        with self.assertRaisesRegex(Blocked, "SIX_OWNER_IMAGE_PROVENANCE_MISSING"):
            no_duplicate_keys([("schema", "accepted"), ("schema", "forged")])

    def test_private_provenance_evidence_must_not_set_l4_from_source_only(self):
        from dev11_six_owner_positive import safe_report
        report = safe_report("OBSERVER_UNAVAILABLE", source_verified=True,
                             native_origin=True, exported=True,
                             independent_effect=True, network=True)
        self.assertEqual(report["l4_ops_01"], "BLOCKED")
        self.assertFalse(report["genuine_iam_cp_buyer_commitment_authority_qualified"])
        self.assertFalse(report["production_authorized"])

    def test_genuine_buyer_cannot_be_inferred_from_synthetic_outbox(self):
        with patch("dev11_six_owner_positive.sources",
                   return_value={"sources": {key: "a"*40 for key in OWNERS}}), \
             patch("dev11_six_owner_positive.containers", return_value=True), \
             patch("dev11_six_owner_positive.trade_origin",
                   side_effect=Blocked("NATIVE_BUYER_ORIGIN_REFUSED")), \
             patch("dev11_six_owner_positive.independent_graph") as forbidden:
            args = type("Args", (), {"root": Path("/never"),
                       "project": "dev11-six-1234567890", "event_id": None})()
            report = qualify(args)
            forbidden.assert_not_called()
            self.assertEqual(report["reason"], "NATIVE_BUYER_ORIGIN_REFUSED")
            self.assertFalse(report["genuine_iam_cp_buyer_commitment_authority_qualified"])

    def test_even_original_event_plus_exported_jvm_cannot_replace_fresh_buyer_authority(self):
        with patch("dev11_six_owner_positive.sources",
                   return_value={"sources": {key: "a"*40 for key in OWNERS}}), \
             patch("dev11_six_owner_positive.containers", return_value=True), \
             patch("dev11_six_owner_positive.trade_origin", return_value=True), \
             patch("dev11_six_owner_positive.independent_graph", return_value=True):
            args = type("Args", (), {"root": Path("/never"),
                       "project": "dev11-six-1234567890",
                       "event_id": "11111111-1111-4111-8111-111111111111"})()
            report = qualify(args)
            self.assertEqual(report["l4_ops_01"], "BLOCKED")
            self.assertEqual(report["reason"], "CURRENT_IAM_CP_AUTHORITY_UNVERIFIED")
            self.assertTrue(report["enforced_medusa_buyer_origin"])
            self.assertTrue(report["independently_exported_full_trace"])
