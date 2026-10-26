"""DEV-14 native service graph stays private and never grants IAM/CP rights."""
import copy
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dev15_compose", HERE / "dev15_compose.py")
comp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comp)

DIGEST = "a" * 64
LABELS = {"io.baobab.dev.namespace": "synthetic", "io.baobab.dev.run": "f" * 32,
          "io.baobab.dev.deadline": "0"}
BASE = {"name": "test-synthetic", "services": {"cp": {}, "hydra": {}, "kratos": {}},
        "networks": {"lab": {"internal": True}}, "volumes": {}}
IMAGES = {"postgres": "postgres@sha256:" + DIGEST,
          "qdrant": "qdrant/qdrant@sha256:" + DIGEST}
SECRETS = {"pulse_db": "b" * 64}


def profile(name):
    engine = "baobab-pulse" if name == "pulse-intelligence" else "baobab-payments"
    required = [
        {"key": "iam", "kind": "iam", "owner": "baobab-iam"},
        {"key": "control-plane", "kind": "control-plane", "owner": "baobab-cp"},
        {"key": "subject", "kind": "engine", "owner": engine},
    ]
    if name == "pulse-intelligence":
        required += [
            {"key": "canonical-store", "kind": "postgresql", "owner": engine},
            {"key": "semantic-projection", "kind": "qdrant", "owner": engine},
        ]
    return {"profile_key": name, "subject_engine": engine, "mode": "l4",
            "services": {"required": required, "optional": []},
            "run_policy": {"environment": "development", "network": "private",
                           "synthetic_only": True, "expose_admin_ports": False,
                           "cleanup": "required"}}


class ComposeTests(unittest.TestCase):
    def make(self, name, **overrides):
        inputs = {"subject_image": "sha256:" + DIGEST,
                  "images": IMAGES, "secrets": SECRETS, "labels": LABELS}
        inputs.update(overrides)
        original = copy.deepcopy(BASE)
        result = comp.apply(profile(name), original, **inputs)
        self.assertEqual(original, BASE)
        self.assertEqual(result["networks"]["lab"]["internal"], True)
        self.assertTrue({"cp", "hydra", "kratos"} <= set(result["services"]))
        self.assertFalse({"cms", "bff"} & set(result["services"]))
        for key in set(result["services"]) - set(original["services"]):
            service = result["services"][key]
            self.assertNotIn("ports", service)
            self.assertNotIn("privileged", service)
            self.assertNotIn("build", service)
            self.assertIn("no-new-privileges:true", service["security_opt"])
        return result

    def test_pulse_real_stores_and_owner_migration_dns(self):
        services = self.make("pulse-intelligence")["services"]
        self.assertEqual(services["dev15-subject"]["environment"]["PULSE_DATABASE_URL"],
                         "postgresql://pulse:" + SECRETS["pulse_db"] + "@pulse-db:5432/pulse")
        self.assertIn("pulse-qdrant", services)
        self.assertIn("pulse-db", services)
        self.assertEqual(services["dev15-subject"]["depends_on"]["pulse-db"]["condition"],
                         "service_healthy")

    def test_payments_has_no_psp_or_cms_and_is_explicitly_sandbox(self):
        result = self.make("payments-sandbox")
        self.assertEqual(set(result["services"]) - {"cp", "hydra", "kratos"},
                         {"dev15-subject"})
        environment = result["services"]["dev15-subject"]["environment"]
        self.assertEqual(environment["PAYMENT_PROVIDER"], "sandbox")
        self.assertNotIn("HYPERSWITCH_API_KEY", environment)

    def test_unpinned_image_or_public_base_is_denied(self):
        with self.assertRaisesRegex(comp.onboard.Refused, "DEV15_ACTUAL_IMAGE_ID_REQUIRED"):
            self.make("payments-sandbox", subject_image="baobab-payments:latest")
        unsafe = copy.deepcopy(BASE)
        unsafe["networks"]["lab"]["internal"] = False
        with self.assertRaisesRegex(comp.onboard.Refused, "DEV15_DEV01_PRIVATE_STACK_REQUIRED"):
            comp.apply(profile("pulse-intelligence"), unsafe, subject_image="sha256:" + DIGEST,
                       images=IMAGES, secrets=SECRETS, labels=LABELS)

    def test_unknown_services_or_missing_native_pin_refuse(self):
        desc = profile("pulse-intelligence")
        desc["services"]["required"].append({"key": "cms", "kind": "cms", "owner": "other"})
        with self.assertRaisesRegex(comp.onboard.Refused, "DEV15_SERVICE_SELECTION_REFUSED"):
            comp.apply(desc, BASE, subject_image="sha256:" + DIGEST, images=IMAGES,
                       secrets=SECRETS, labels=LABELS)
        with self.assertRaisesRegex(comp.onboard.Refused, "DEV15_NATIVE_STORE_IMAGE_OR_SECRET_REQUIRED"):
            self.make("pulse-intelligence", images={"postgres": IMAGES["postgres"]})

    def test_unrecognised_environment_is_denied(self):
        desc = profile("payments-sandbox")
        desc["run_policy"]["environment"] = "staging"
        with self.assertRaisesRegex(comp.onboard.Refused, "DEV15_ENVIRONMENT_REFUSED"):
            comp.apply(desc, BASE, subject_image="sha256:" + DIGEST, images=IMAGES,
                       secrets=SECRETS, labels=LABELS)


if __name__ == "__main__":
    unittest.main()
