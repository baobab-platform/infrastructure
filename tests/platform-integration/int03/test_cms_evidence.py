"""Evidence custody tests: never use mock observations as qualified results."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import cms_evidence as custody


class Evidence(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        os.chmod(self.root,0o700)
        self.pins=dict.fromkeys(
            ["shared","baobab-cms","baobab-iam","baobab-cp","nabhold","infrastructure"],
            "a"*40)
        self.record=self.root/"issuer-observation.json"
        self.record.write_text(json.dumps({"schema":"runtime.readback.v1",
            "identities_created":False,"qualified":False,"fences":{"issuer":"UNVERIFIED"}}))
        os.chmod(self.record,0o600)

    def seal(self):
        return custody.seal(self.root,[self.record.name],run_id="a"*16,
                            sources=self.pins,workflow_run=39745271130)

    def test_content_addressed_bytes_and_two_separate_hashes(self):
        result=self.seal()
        self.assertFalse(result["qualified"])
        self.assertEqual(result["storage_immutability"],"NOT_PROVEN_BY_LOCAL_SEAL")
        self.assertEqual(custody.verify(self.root)["files"],result["files"])
        self.assertEqual((self.root/"manifest.json").stat().st_mode & 0o777,0o600)
        with self.assertRaises(custody.Refused):
            self.seal()

    def test_modified_evidence_denied(self):
        self.seal()
        self.record.write_text(json.dumps({"schema":"runtime.readback.v1","qualified":False,
              "identities_created":True}))
        with self.assertRaises(custody.Refused):
            custody.verify(self.root)

    def test_modified_manifest_denied(self):
        self.seal()
        manifest=self.root/"manifest.json"
        raw=json.loads(manifest.read_text())
        raw["qualified"]=True
        manifest.write_text(json.dumps(raw))
        with self.assertRaises(custody.Refused):
            custody.verify(self.root)

    def test_extra_files_denied(self):
        self.seal()
        other=self.root/"unexpected.json"
        other.write_text("{}")
        with self.assertRaises(custody.Refused):
            custody.verify(self.root)

    def test_credentials_and_fake_acceptance_denied(self):
        for bad in (
            {"nested":{"client_secret":"x"},"qualified":False},
            {"authorization":"Bearer protected","qualified":False},
            {"qualified":True},
            {"full_int03_acceptance":True},
        ):
            self.record.write_text(json.dumps(bad))
            with self.assertRaises(custody.Refused):
                self.seal()

    def test_world_readable_or_symlink_fails_closed(self):
        os.chmod(self.record,0o644)
        with self.assertRaises(custody.Refused):
            self.seal()
        os.chmod(self.record,0o600)
        self.record.unlink()
        target=self.root/"target.json"
        target.write_text("{}")
        self.record.symlink_to(target)
        with self.assertRaises(custody.Refused):
            self.seal()
        self.record.unlink()
        os.chmod(self.root,0o755)
        with self.assertRaises(custody.Refused):
            self.seal()

    def test_exact_pins_and_run_scope(self):
        self.pins.pop("infrastructure")
        with self.assertRaises(custody.Refused):
            self.seal()
        self.pins["infrastructure"]="a"*40
        with self.assertRaises(custody.Refused):
            custody.seal(self.root,["../secret.json"],run_id="a"*16,sources=self.pins)


if __name__=="__main__":
    unittest.main()
