"""DEV-15 registered source authority is not issuer/CP runtime authority."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).with_name("dev15_registry.py")
spec = importlib.util.spec_from_file_location("dev15_registry", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def profile(name, role_to_id):
    return {
        "profile_key": name,
        "run_policy": {"environment": "development", "synthetic_only": True},
        "iam": {
            role: {
                "client_id": identity,
                "audiences": ["baobab-control-plane"],
                "scopes": ["context:resolve"] if role != "validator" else ["context:validate"],
            }
            for role, identity in role_to_id.items()
        },
    }


def fixture():
    clients = {
        "pulse-intelligence": {"caller": "pulse-caller", "neighbour": "pulse-neighbour", "validator": "pulse-validator"},
        "payments-sandbox": {"caller": "payments-caller", "neighbour": "payments-neighbour", "validator": "payments-validator"},
    }
    profiles = {name: profile(name, identities) for name, identities in clients.items()}
    shared = {
        ident: {
            "status": "ACTIVE", "environment": "development",
            "allowed_audiences": ["baobab-control-plane"],
            "allowed_scopes": ["context:resolve", "context:validate"],
        }
        for identities in clients.values() for ident in identities.values()
    }
    return profiles, shared


class Dev15RegistryTests(unittest.TestCase):
    def test_current_source_still_never_asserts_connected_runtime(self):
        profiles, shared = fixture()
        result = mod.validate(profiles, shared, shared)
        self.assertTrue(result["embedded_registry_parity"])
        self.assertEqual(result["dev15_connected_status"], "BLOCKED")
        self.assertEqual(result["real_iam_clients_issued"], "NOT_OBSERVED")
        self.assertFalse(result["production_authorized"])

    def test_embedded_cp_snapshot_lag_is_reported_not_ignored(self):
        profiles, shared = fixture()
        lagging = {key: row for key, row in shared.items() if key.startswith("pulse")}
        result = mod.validate(profiles, shared, lagging)
        self.assertEqual(len(result["cp_embedded_registry_stale_for"]), 3)
        self.assertFalse(result["embedded_registry_parity"])
        self.assertEqual(result["effective_cp_runtime_registry"], "NOT_INSPECTED")

    def test_unregistered_or_protected_clients_refused(self):
        profiles, shared = fixture()
        shared["pulse-caller"]["status"] = "REVOKED"
        with self.assertRaisesRegex(mod.onboarding.Refused, "DEV15_CANONICAL_CLIENT_NOT_ACTIVE"):
            mod.validate(profiles, shared, {})

    def test_cross_role_scope_violation_denied(self):
        profiles, shared = fixture()
        profiles["pulse-intelligence"]["iam"]["caller"]["scopes"].append("admin:all")
        with self.assertRaisesRegex(mod.onboarding.Refused, "DEV15_CLIENT_SCOPE_OR_AUDIENCE_EXCEEDED"):
            mod.validate(profiles, shared, {})

    def test_client_namespace_must_not_overlap_engines(self):
        profiles, shared = fixture()
        profiles["payments-sandbox"]["iam"]["caller"]["client_id"] = "pulse-caller"
        with self.assertRaisesRegex(mod.onboarding.Refused, "DEV15_IDENTITY_NOT_DISTINCT"):
            mod.validate(profiles, shared, {})


if __name__ == "__main__":
    unittest.main()
