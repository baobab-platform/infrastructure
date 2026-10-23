"""Negative controls for Infrastructure #49's *non-authorising* preflight."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


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
        self.assertEqual(result["review_applicability"], "OPTIONAL_INDEPENDENT_49_ONLY")
        # HELD is specific to the optional #49 ceremony, never ADR-043 development.
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


class PrivatePacketCliTests(unittest.TestCase):
    """Real offline subprocess/Git checks; all packet actors and pins synthetic."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.root = self.directory / "source"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic packet test")
        self.git("config", "user.email", "packet-test@example.invalid")
        (self.root / "baseline").write_text("synthetic prerequisite")
        self.commit()
        lock = dict(LOCK, infrastructure_baseline=self.git("rev-parse", "HEAD"))
        self.modules = self.root / "tests/platform-integration/int03"
        self.modules.mkdir(parents=True)
        for name in ("int03c_approval_packet.py", "connected_identity_sources.py",
                     "connected_identity_evidence.py"):
            shutil.copyfile(module_path.with_name(name), self.modules / name)
        (self.modules / "int03c-lock.json").write_text(json.dumps(lock))
        self.commit()
        self.packet = synthetic_packet()
        self.packet["sources"]["infrastructure"] = self.git("rev-parse", "HEAD")
        # The private packet is deliberately outside the immutable source tree.
        self.file = self.directory / "private-sensitive-packet.json"
        self.write(json.dumps(self.packet, indent=2).replace("\n", "\r\n").encode())

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True).strip()

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic source")

    def write(self, raw):
        self.file.write_bytes(raw)
        self.file.chmod(0o600)

    def run_cli(self, path=None):
        return subprocess.run([sys.executable, "-B", str(self.modules / module_path.name),
                               "--packet", str(path or self.file)],
                              capture_output=True, text=True, timeout=5)

    def assert_blocked(self, path=None):
        result = self.run_cli(path)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertRegex(result.stderr, r"\ABLOCKED: [A-Za-z]+\n\Z")
        self.assertNotIn(str(self.directory), result.stderr)
        self.assertNotIn("actor-", result.stderr)

    def test_clean_exact_source_returns_held_and_original_byte_hash(self):
        original = self.file.read_bytes()
        first = self.run_cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        result = json.loads(first.stdout)
        self.assertFalse(result["authorised"])
        self.assertEqual(result["runtime_status"], "APPROVAL_REQUIRED_RUNTIME_HELD")
        self.assertEqual(result["packet_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(result["packet_size_bytes"], len(original))
        self.write(json.dumps(self.packet, separators=(",", ":")).encode())
        second = json.loads(self.run_cli().stdout)
        self.assertEqual(result["plan_sha256"], second["plan_sha256"])
        self.assertNotEqual(result["packet_sha256"], second["packet_sha256"])
        self.assertNotIn("actor-", first.stdout)
        self.assertNotIn("private-reviewed", first.stdout)
        self.write(self.file.read_bytes().ljust(approval.PACKET_LIMIT, b" "))
        self.file.chmod(0o400)
        boundary = self.run_cli()
        self.assertEqual(boundary.returncode, 0, boundary.stderr)
        self.assertEqual(json.loads(boundary.stdout)["packet_size_bytes"], approval.PACKET_LIMIT)

    def test_refuses_shared_permissions(self):
        for mode in (0o644, 0o640, 0o604):
            self.file.chmod(mode)
            with self.subTest(mode=mode):
                self.assert_blocked()

    def test_refuses_links_nonfiles_and_missing_input_without_blocking(self):
        link = self.directory / "symlink"
        link.symlink_to(self.file)
        self.assert_blocked(link)
        hardlink = self.directory / "hardlink"
        os.link(self.file, hardlink)
        self.assert_blocked(hardlink)
        self.assert_blocked()
        self.assert_blocked(self.directory)
        self.assert_blocked(self.directory / "absent")
        fifo = self.directory / "fifo"
        os.mkfifo(fifo, 0o600)
        self.assert_blocked(fifo)

    def test_refuses_empty_oversized_malformed_ambiguous_and_deep_json(self):
        for raw in (b"", b" " * (approval.PACKET_LIMIT + 1), b"\xff", b"{",
                    b'{"environment":"production","environment":"development"}',
                    b'{"nested":{"id":1,"id":2}}',
                    b'{"unexpected":NaN}', b'{"unexpected":Infinity}',
                    b'{"unexpected":-Infinity}', b"[" * 1500 + b"]" * 1500):
            self.write(raw)
            with self.subTest(length=len(raw)):
                self.assert_blocked()

    def test_cli_refuses_dirty_source_or_different_infrastructure_revision(self):
        (self.root / "untracked").write_text("source drift")
        self.assert_blocked()
        (self.root / "untracked").unlink()
        self.packet["sources"]["infrastructure"] = "0" * 40
        self.write(json.dumps(self.packet).encode())
        self.assert_blocked()

    def test_reader_rejects_foreign_owner_and_observed_mutation(self):
        with patch.object(approval.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaises(approval.PacketError):
                approval.read_private_packet(self.file)
        original_read = os.read

        def mutate_after_read(descriptor, limit):
            raw = original_read(descriptor, limit)
            self.file.chmod(0o644)
            return raw

        with patch.object(approval.os, "read", side_effect=mutate_after_read):
            with self.assertRaises(approval.PacketError):
                approval.read_private_packet(self.file)


if __name__ == "__main__":
    unittest.main()
