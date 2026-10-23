"""Negative controls for Infrastructure #49's *non-authorising* preflight."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


module_path = Path(__file__).with_name("int03c_approval_packet.py")
spec = importlib.util.spec_from_file_location("int03c_approval_packet", module_path)
approval = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(approval)

PIN_NAMES = ("shared", "baobab-iam", "baobab-cp", "baobab-cms", "nabhold")
ROLES = {
    "executive_approver": ("Wekhaso Nabusiu", "actor-w"),
    "run_approver": ("Wekhaso Nabusiu", "actor-w"),
    "security_reviewer": ("Brenda Adams", "actor-brenda"),
    "cp_maker": ("Brian James Nabusiu", "actor-brian"),
    "cp_checker": ("Brenda Adams", "actor-brenda"),
    "runtime_operator": ("Brian James Nabusiu", "actor-brian"),
    "independent_witness": ("Edo Watalu", "actor-edo"),
    "evidence_custodian": ("Edo Watalu", "actor-edo"),
}
# All values below are synthetic unit-test input, NOT identity, topology,
# approval, accepted evidence or a usable runtime manifest.
LOCK = {
    "schema": "infrastructure.int03c.sources.v1",
    "profile": "governed-connected-identity",
    "decision": "shared:docs/architecture/int03c-governed-proof-bootstrap-decision.md",
    "infrastructure_baseline": "9" * 40,
    "sources": {key: char * 40 for key, char in zip(PIN_NAMES, "abcde")},
    "topology_approval": "REQUIRED_INFRASTRUCTURE_49",
    "cms_activation": "HELD",
    "qualified": False,
}


def synthetic_packet():
    sources = dict(LOCK["sources"], infrastructure="f" * 40)
    return {
        "schema": approval.SCHEMA,
        "issue": "baobab-platform/infrastructure#49",
        "environment": "development",
        "synthetic_only": True,
        "run_id": "a" * 32,
        "window": {"start_utc": "2026-12-01T00:00:00Z", "deadline_utc": "2026-12-01T01:30:00Z"},
        "sources": sources,
        "image_digests": {key: "sha256:" + char * 64 for key, char in
                          (("cp", "a"), ("iam", "b"), ("postgres", "c"), ("verifier", "d"))},
        "roles": {role: {"person": values[0], "authenticated_actor_ref": values[1]}
                  for role, values in ROLES.items()},
        "topology": {
            "private_host_ref": "private-reviewed-host",
            "private_network_ref": "private-reviewed-network",
            "threat_model_ref": "private-reviewed-threat-model",
            "private_ca_sha256": "e" * 64,
            "external_deadline_supervisor_ref": "private-reviewed-controller",
            "external_immutable_custody_ref": "private-reviewed-object-lock",
            "custody_retention_policy_ref": "private-reviewed-retention",
            "cp_origin": "https://cp.int03.test",
            "hydra_origin": "https://hydra.int03.test",
        },
    }


class ApprovalGateTests(unittest.TestCase):
    def test_only_returns_held_even_if_structurally_complete(self):
        result = approval.inspect(synthetic_packet(), LOCK)
        self.assertFalse(result["authorised"])
        self.assertEqual(result["classification"], "STRUCTURAL_REVIEW_ONLY")
        self.assertEqual(result["runtime_status"], "APPROVAL_REQUIRED_RUNTIME_HELD")
        self.assertEqual(len(result["plan_sha256"]), 64)

    def test_canonical_digest_does_not_depend_on_key_order(self):
        packet = synthetic_packet()
        result = approval.inspect(packet, LOCK)
        reverse = dict(reversed(list(packet.items())))
        self.assertEqual(result["plan_sha256"], approval.inspect(reverse, LOCK)["plan_sha256"])

    def test_rejects_unapproved_execution_claim(self):
        packet = synthetic_packet()
        packet["approved"] = True
        with self.assertRaises(approval.PacketError):
            approval.inspect(packet, LOCK)

    def test_rejects_prod_or_non_synthetic(self):
        for attr, value in (("environment", "production"), ("synthetic_only", False)):
            packet = synthetic_packet()
            packet[attr] = value
            with self.assertRaises(approval.PacketError):
                approval.inspect(packet, LOCK)

    def test_rejects_expired_or_unbounded_window_structure(self):
        for end in ("2026-12-01T01:30:01Z", "2026-12-01T00:00:00Z",
                    "2026-11-30T23:00:00Z", "2026-12-01T01:00:00+00:00"):
            packet = synthetic_packet()
            packet["window"]["deadline_utc"] = end
            with self.assertRaises(approval.PacketError):
                approval.inspect(packet, LOCK)

    def test_rejects_lost_role_separation(self):
        pairs = (
            ("cp_checker", "cp_maker"),
            ("run_approver", "runtime_operator"),
            ("independent_witness", "runtime_operator"),
            ("evidence_custodian", "cp_checker"),
            ("security_reviewer", "cp_maker"),
            ("executive_approver", "runtime_operator"),
        )
        for left, right in pairs:
            packet = synthetic_packet()
            packet["roles"][left]["authenticated_actor_ref"] = packet["roles"][right]["authenticated_actor_ref"]
            with self.subTest(left=left, right=right), self.assertRaises(approval.PacketError):
                approval.inspect(packet, LOCK)

    def test_rejects_ambiguous_nested_and_top_level_json(self):
        # The first of two contradictory values must not be discarded.
        for raw in (
            '{"environment":"production","environment":"development"}',
            '{"roles":{"cp_maker":{"person":"A","person":"B"}}}',
            '{"topology":{"cp_origin":"https://bad.example","cp_origin":"https://cp.int03.test"}}',
        ):
            with self.subTest(raw=raw), self.assertRaises(approval.PacketError):
                approval.parse_protected_json(raw)

    def test_rejects_incomplete_or_forged_source_lock(self):
        packet = synthetic_packet()
        with self.assertRaises(approval.PacketError):
            approval.inspect(packet, {"sources": LOCK["sources"]})
        for key, value in (
            ("schema", "untrusted"),
            ("infrastructure_baseline", "unverified"),
            ("cms_activation", "ACTIVE"),
            ("topology_approval", "GRANTED"),
            ("qualified", True),
        ):
            forged = dict(LOCK, **{key: value})
            with self.subTest(key=key), self.assertRaises(approval.PacketError):
                approval.inspect(packet, forged)

    def test_rejects_every_forbidden_approver_collision(self):
        for left in ("executive_approver", "run_approver"):
            for right in ("cp_maker", "cp_checker", "runtime_operator",
                          "independent_witness", "evidence_custodian"):
                packet = synthetic_packet()
                packet["roles"][right]["authenticated_actor_ref"] = packet["roles"][left]["authenticated_actor_ref"]
                with self.subTest(left=left, right=right), self.assertRaises(approval.PacketError):
                    approval.inspect(packet, LOCK)

    def test_rejects_checker_operating_own_run(self):
        packet = synthetic_packet()
        packet["roles"]["runtime_operator"]["authenticated_actor_ref"] = (
            packet["roles"]["cp_checker"]["authenticated_actor_ref"]
        )
        with self.assertRaises(approval.PacketError):
            approval.inspect(packet, LOCK)

    def test_rejects_assistant_as_credentialed_actor(self):
        packet = synthetic_packet()
        packet["roles"]["support_ops"] = {
            "person": "support-nominee",
            "authenticated_actor_ref": "assistant-actor",
        }
        with self.assertRaises(approval.PacketError):
            approval.inspect(packet, LOCK)
        packet = synthetic_packet()
        packet["roles"]["cp_maker"]["assistant"] = "support-nominee"
        with self.assertRaises(approval.PacketError):
            approval.inspect(packet, LOCK)

    def test_rejects_source_drift_and_unpinned_image(self):
        packet = synthetic_packet()
        packet["sources"]["baobab-cp"] = "0" * 40
        with self.assertRaises(approval.PacketError):
            approval.inspect(packet, LOCK)
        packet = synthetic_packet()
        packet["image_digests"]["cp"] = "cp:latest"
        with self.assertRaises(approval.PacketError):
            approval.inspect(packet, LOCK)

    def test_rejects_missing_shutdown_or_immutable_custody(self):
        for key in ("external_deadline_supervisor_ref", "external_immutable_custody_ref",
                    "custody_retention_policy_ref", "private_ca_sha256"):
            packet = synthetic_packet()
            packet["topology"].pop(key)
            with self.subTest(key=key), self.assertRaises(approval.PacketError):
                approval.inspect(packet, LOCK)

    def test_rejects_control_plane_endpoint_change(self):
        packet = synthetic_packet()
        packet["topology"]["hydra_origin"] = "https://evil.example"
        with self.assertRaises(approval.PacketError):
            approval.inspect(packet, LOCK)

    def test_rejects_placeholder_and_unverified_identity_reference(self):
        packet = synthetic_packet()
        packet["roles"]["cp_maker"]["authenticated_actor_ref"] = "TODO"
        with self.assertRaises(approval.PacketError):
            approval.inspect(packet, LOCK)


if __name__ == "__main__":
    unittest.main()
