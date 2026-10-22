"""Real local Git histories, synthetic source plans; no runtime approval."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import connected_identity_sources as sources
from connected_identity_evidence import EvidenceRefused


class SourcePins(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "source-test@example.invalid")
        self.git("config", "user.name", "Synthetic source test")
        (self.root / "baseline").write_text("synthetic merged prerequisite")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")
        self.baseline = self.git("rev-parse", "HEAD")
        self.lock = sources.read_lock()
        self.lock["infrastructure_baseline"] = self.baseline
        self.path = self.root / "int03c-lock.json"
        self.write()
        self.git("add", ".")
        self.git("commit", "-qm", "source lock")
        self.plan = {"sources": dict(self.lock["sources"], infrastructure=self.git("rev-parse", "HEAD"))}
        for name, value in (("ROOT", self.root), ("LOCK", self.path)):
            active = patch.object(sources, name, value)
            active.start()
            self.addCleanup(active.stop)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def write(self):
        self.path.write_text(json.dumps(self.lock))

    def test_clean_descendant_returns_exact_copy_without_promoting_authority(self):
        result = sources.source_pins(self.plan)
        self.assertEqual(result, self.plan["sources"])
        self.assertIsNot(result, self.plan["sources"])
        self.assertFalse(sources.read_lock()["qualified"])
        self.assertEqual(sources.read_lock()["cms_activation"], "HELD")

    def test_floating_missing_extra_malformed_or_old_cms_pins_refused(self):
        old = json.loads((sources.BASE / "cms-lock.json").read_text())["sources"]
        variants = [dict(old, infrastructure=self.plan["sources"]["infrastructure"])]
        for key in self.plan["sources"]:
            for value in ("main", "a" * 40 + "\n", None, "a" * 40):
                variant = dict(self.plan["sources"], **{key: value})
                if variant != self.plan["sources"]:
                    variants.append(variant)
            variant = dict(self.plan["sources"])
            del variant[key]
            variants.append(variant)
        variants.append(dict(self.plan["sources"], shadow="a" * 40))
        for pins in variants:
            with self.subTest(pins=pins), self.assertRaises(EvidenceRefused):
                sources.source_pins({"sources": pins})

    def test_modified_tracked_or_untracked_source_refused(self):
        for path in (self.root / "baseline", self.root / "untracked"):
            original = path.read_text() if path.exists() else None
            path.write_text("unreviewed change")
            with self.assertRaises(EvidenceRefused):
                sources.source_pins(self.plan)
            if original is None:
                path.unlink()
            else:
                path.write_text(original)

    def test_unrelated_or_missing_baseline_refused_even_in_clean_source(self):
        for baseline in ("0" * 40,):
            self.lock["infrastructure_baseline"] = baseline
            self.write()
            self.git("add", ".")
            self.git("commit", "-qm", "unavailable baseline")
            self.plan["sources"]["infrastructure"] = self.git("rev-parse", "HEAD")
            with self.assertRaises(EvidenceRefused):
                sources.source_pins(self.plan)
        # A real but unrelated branch is as invalid as a nonexistent object.
        branch = self.git("symbolic-ref", "--short", "HEAD")
        self.git("checkout", "--orphan", "unrelated")
        self.git("commit", "--allow-empty", "-qm", "unrelated root")
        unrelated = self.git("rev-parse", "HEAD")
        self.git("checkout", branch)
        self.lock["infrastructure_baseline"] = unrelated
        self.write()
        self.git("add", ".")
        self.git("commit", "-qm", "unrelated baseline")
        self.plan["sources"]["infrastructure"] = self.git("rev-parse", "HEAD")
        with self.assertRaises(EvidenceRefused):
            sources.source_pins(self.plan)

    def test_lock_cannot_claim_approval_acceptance_or_use_ambiguous_fields(self):
        original = copy.deepcopy(self.lock)
        for key, value in (("topology_approval", "APPROVED"), ("cms_activation", "ACTIVE"),
                           ("qualified", True), ("extra", False), ("schema", "cms"),
                           ("infrastructure_baseline", "main")):
            self.lock = dict(original, **{key: value})
            self.write()
            with self.assertRaises(EvidenceRefused):
                sources.read_lock()
        self.path.write_text('{"sources": {}, "sources": {}}')
        with self.assertRaises(EvidenceRefused):
            sources.read_lock()


if __name__ == "__main__":
    unittest.main()
