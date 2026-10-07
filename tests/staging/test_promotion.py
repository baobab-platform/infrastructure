import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("promote", ROOT / "deploy/verification/promote.py")
promote = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promote)


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.release = json.loads((ROOT / "terraform/environments/staging/tests/release.fixture.json").read_text())
        self.coordination = {
            "release_tag": "v0.1.0-staging",
            "components": {
                key: {
                    "tag": "v0.1.0-staging",
                    "source_revision": "a" * 40,
                    "digest": "sha256:" + "a" * 64,
                }
                for key in ("shared", "cp", "iam", "pulse", "keycloak")
            },
        }

    def files(self, release=None, coordination=None):
        directory = tempfile.TemporaryDirectory()
        root = pathlib.Path(directory.name)
        path = root / "v0.1.0-staging.tfvars.json"
        path.write_text(json.dumps(release or self.release))
        (root / "v0.1.0-staging.coordination.json").write_text(json.dumps(coordination or self.coordination))
        return directory, path

    def test_plan_promotes_only_runtime_components_with_exact_identity(self):
        directory, path = self.files()
        self.addCleanup(directory.cleanup)
        account, items = promote.promotion_plan(path)
        self.assertEqual(account, "123456789012")
        self.assertEqual([item["component"] for item in items], ["cp", "iam", "pulse", "keycloak"])
        self.assertTrue(all(item["source"].endswith("@sha256:" + "a" * 64) for item in items))
        self.assertTrue(all(item["target_repo"].startswith("123456789012.dkr.ecr.af-south-1.amazonaws.com/") for item in items))

    def test_plan_denies_source_revision_and_digest_drift(self):
        for mutation in ("source", "digest", "account"):
            release = copy.deepcopy(self.release)
            coordination = copy.deepcopy(self.coordination)
            if mutation == "source":
                coordination["components"]["pulse"]["source_revision"] = "b" * 40
            elif mutation == "digest":
                coordination["components"]["pulse"]["digest"] = "sha256:" + "b" * 64
            else:
                release["services"]["pulse"]["image"] = release["services"]["pulse"]["image"].replace("123456789012", "999999999999")
            directory, path = self.files(release, coordination)
            self.addCleanup(directory.cleanup)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                promote.promotion_plan(path)

    def test_existing_exact_digest_is_idempotent_without_docker(self):
        item = {
            "component": "pulse",
            "source": "ghcr.io/baobab-platform/baobab-pulse@sha256:" + "a" * 64,
            "source_revision": "a" * 40,
            "release_tag": "v0.1.0-staging",
            "digest": "sha256:" + "a" * 64,
            "target_repo": "123456789012.dkr.ecr.af-south-1.amazonaws.com/pulse",
            "repository": "pulse",
            "promotion_tag": "promotion-" + "a" * 20,
        }
        existing = {"imageId": {"imageDigest": item["digest"]}}
        with patch.object(promote, "ecr_image", return_value=existing), patch.object(promote, "command") as command:
            result = promote.promote(item)
        self.assertEqual(result["status"], "already-present")
        command.assert_not_called()

    def test_copy_must_preserve_digest(self):
        digest = "sha256:" + "a" * 64
        item = {
            "component": "pulse",
            "source": "ghcr.io/baobab-platform/baobab-pulse@" + digest,
            "source_revision": "a" * 40,
            "release_tag": "v0.1.0-staging",
            "digest": digest,
            "target_repo": "123456789012.dkr.ecr.af-south-1.amazonaws.com/pulse",
            "repository": "pulse",
            "promotion_tag": "promotion-" + "a" * 20,
        }
        promoted = {"imageId": {"imageDigest": digest}}
        def command(args):
            if args[:3] == ["docker", "image", "inspect"]:
                return json.dumps([item["source"]])
            return ""
        with patch.object(promote, "ecr_image", side_effect=[None, promoted, promoted]), patch.object(promote, "command", side_effect=command):
            result = promote.promote(item)
        self.assertEqual(result["status"], "promoted")

        wrong = {"imageId": {"imageDigest": "sha256:" + "b" * 64}}
        with patch.object(promote, "ecr_image", side_effect=[None, wrong]), patch.object(promote, "command", side_effect=command):
            with self.assertRaises(ValueError):
                promote.promote(item)


if __name__ == "__main__":
    unittest.main()
