"""Non-authorising, offline structural inspection for Infrastructure issue #49.

This tool deliberately cannot unlock a runtime. It never contacts IAM, CP,
GitHub, a host or custody: those independent human/provider proofs are gates,
not values that a JSON document may assert on its own.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys


SCHEMA = "infrastructure.int03c.infrastructure49.review-packet.v1"
ROLES = (
    "executive_approver",
    "run_approver",
    "security_reviewer",
    "cp_maker",
    "cp_checker",
    "runtime_operator",
    "independent_witness",
    "evidence_custodian",
)
SOURCES = ("shared", "baobab-iam", "baobab-cp", "baobab-cms", "nabhold", "infrastructure")
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
NONCE = re.compile(r"[0-9a-f]{32}\Z")


class PacketError(ValueError):
    """Source-only, fail-closed review error; never indicates runtime acceptance."""


def unique_object(pairs):
    """Reject duplicate JSON members before canonical hashing or policy checks."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise PacketError("duplicate field in protected approval JSON")
        result[key] = value
    return result


def parse_protected_json(raw: str) -> dict:
    """Always decode the full packet as strict, unambiguous JSON."""
    return json.loads(raw, object_pairs_hook=unique_object)


def validate_source_lock(lock: dict) -> dict:
    """Require the complete closed #49 source lock, not a free-form sources map."""
    if (type(lock) is not dict or set(lock) != {
            "schema", "profile", "decision", "infrastructure_baseline",
            "sources", "topology_approval", "cms_activation", "qualified"} or
        lock["schema"] != "infrastructure.int03c.sources.v1" or
        lock["profile"] != "governed-connected-identity" or
        lock["decision"] != "shared:docs/architecture/int03c-governed-proof-bootstrap-decision.md" or
        lock["topology_approval"] != "REQUIRED_INFRASTRUCTURE_49" or
        lock["cms_activation"] != "HELD" or lock["qualified"] is not False or
        type(lock["infrastructure_baseline"]) is not str or
        not SHA.fullmatch(lock["infrastructure_baseline"]) or
        type(lock["sources"]) is not dict or
        set(lock["sources"]) != set(SOURCES) - {"infrastructure"} or
        any(type(value) is not str or not SHA.fullmatch(value)
            for value in lock["sources"].values())):
        raise PacketError("source lock must be the complete, non-authorising INT-03C lock")
    return lock


def _require(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise PacketError(f"{field}: nonempty bounded text required")
    if any(c in value.lower() for c in ("placeholder", "todo", "replace_me", "example-only")):
        raise PacketError(f"{field}: placeholder is not evidence")
    return value


def _utc(value: object, field: str) -> datetime:
    raw = _require(value, field)
    if not raw.endswith("Z"):
        raise PacketError(f"{field}: explicit UTC Z is mandatory")
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PacketError(f"{field}: invalid UTC timestamp") from exc
    if when.utcoffset() != timezone.utc.utcoffset(when):
        raise PacketError(f"{field}: UTC required")
    return when


def inspect(packet: dict, source_lock: dict) -> dict:
    """Validate constraints without verifying signatures, grants or resources.

    A structurally complete packet remains HELD until separate authorised
    people verify the signed plan digest, live CP rights, topology and custody.
    """
    if not isinstance(packet, dict) or set(packet) != {
        "schema", "issue", "environment", "synthetic_only", "run_id",
        "window", "sources", "image_digests", "roles", "topology",
    }:
        raise PacketError("packet: missing or unexpected fields")
    if packet["schema"] != SCHEMA or packet["issue"] != "baobab-platform/infrastructure#49":
        raise PacketError("schema/issue: unexpected approval gate")
    if packet["environment"] != "development" or packet["synthetic_only"] is not True:
        raise PacketError("development-only synthetic scope required")
    if not isinstance(packet["run_id"], str) or not NONCE.fullmatch(packet["run_id"]):
        raise PacketError("run_id: private independent 32-character hex nonce required")

    window = packet["window"]
    if not isinstance(window, dict) or set(window) != {"start_utc", "deadline_utc"}:
        raise PacketError("window: explicit start and deadline required")
    start = _utc(window["start_utc"], "window.start_utc")
    deadline = _utc(window["deadline_utc"], "window.deadline_utc")
    duration = (deadline - start).total_seconds()
    if not 0 < duration <= 90 * 60:
        raise PacketError("window: must be positive and at most 90 minutes")

    sources = packet["sources"]
    locked = validate_source_lock(source_lock)["sources"]
    if not isinstance(sources, dict) or set(sources) != set(SOURCES):
        raise PacketError("sources: exactly six pinned repository SHAs required")
    for name in SOURCES:
        value = sources[name]
        if not isinstance(value, str) or not SHA.fullmatch(value):
            raise PacketError(f"sources.{name}: exact 40-hex SHA required")
        if name in locked and value != locked[name]:
            raise PacketError(f"sources.{name}: differs from current immutable lock")

    images = packet["image_digests"]
    if not isinstance(images, dict) or not {"cp", "iam", "postgres", "verifier"}.issubset(images):
        raise PacketError("image_digests: CP, IAM, PostgreSQL and verifier required")
    for service, digest in images.items():
        _require(service, "image service")
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise PacketError(f"image_digests.{service}: OCI sha256 digest required")

    roles = packet["roles"]
    if not isinstance(roles, dict) or set(roles) != set(ROLES):
        raise PacketError("roles: all eight accountable functions required")
    ids = {}
    for role in ROLES:
        actor = roles[role]
        if not isinstance(actor, dict) or set(actor) != {"person", "authenticated_actor_ref"}:
            raise PacketError(f"roles.{role}: person and identity reference required")
        _require(actor["person"], f"roles.{role}.person")
        ids[role] = _require(actor["authenticated_actor_ref"], f"roles.{role}.authenticated_actor_ref")
    # One corporate approver cannot also operate, check or witness the run.
    # Technical reviewer and CP checker may be the same independently
    # qualified adult; CP maker and runtime operator may be the same adult.
    # Witness and evidence custodian may also coincide, but neither can
    # create/mutate the resources they are independently verifying.
    approval_roles = ("executive_approver", "run_approver")
    mutating_and_witness_roles = (
        "cp_maker", "cp_checker", "runtime_operator",
        "independent_witness", "evidence_custodian",
    )
    excluded = [
        (a, b) for a in approval_roles for b in mutating_and_witness_roles
    ]
    excluded += [
        (a, b) for a in ("security_reviewer", "cp_checker")
        for b in ("cp_maker", "runtime_operator")
    ]
    excluded += [
        (a, b) for a in ("independent_witness", "evidence_custodian")
        for b in ("cp_maker", "cp_checker", "runtime_operator")
    ]
    for left, right in excluded:
        if ids[left] == ids[right]:
            raise PacketError(f"role separation: {left} must differ from {right}")

    topology = packet["topology"]
    required = {
        "private_host_ref", "private_network_ref", "threat_model_ref",
        "private_ca_sha256", "external_deadline_supervisor_ref",
        "external_immutable_custody_ref", "custody_retention_policy_ref",
        "cp_origin", "hydra_origin",
    }
    if not isinstance(topology, dict) or set(topology) != required:
        raise PacketError("topology: all independent control references required")
    for key in required:
        _require(topology[key], f"topology.{key}")
    if topology["cp_origin"] != "https://cp.int03.test" or topology["hydra_origin"] != "https://hydra.int03.test":
        raise PacketError("topology: only reviewed development control-plane origins")
    if not re.fullmatch(r"[0-9a-f]{64}", topology["private_ca_sha256"]):
        raise PacketError("topology.private_ca_sha256: exact fingerprint required")

    canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {
        "classification": "STRUCTURAL_REVIEW_ONLY",
        "authorised": False,
        "runtime_status": "APPROVAL_REQUIRED_RUNTIME_HELD",
        "plan_sha256": hashlib.sha256(canonical).hexdigest(),
        "outstanding": [
            "Independently authenticate each named person and verify actual role acceptance",
            "Verify CP human Principals, effective grants and immutable provenance",
            "Independently authenticate run and technical approvals against plan_sha256",
            "Verify real private host, image/source ancestry, runtime shutdown and WORM custody",
            "Execute seven real cases and independent original-byte teardown witness",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline review only; NEVER grants Infrastructure #49 approval")
    parser.add_argument("--packet", type=Path, required=True, help="Private review packet, no credentials")
    args = parser.parse_args()
    try:
        # The canonical Shared/IAM/CP lock and clean execution source ancestry
        # are validated by the already-governed INT-03C source authority module.
        # A caller cannot override the lock path with a fabricated local file.
        from connected_identity_evidence import EvidenceRefused
        from connected_identity_sources import read_lock, source_pins

        if args.packet.stat().st_size > 16384:
            raise PacketError("packet too large")
        packet = parse_protected_json(args.packet.read_text(encoding="utf-8"))
        lock = read_lock()
        source_pins(packet)
        outcome = inspect(packet, lock)
    except (PacketError, OSError, ValueError, TypeError, EvidenceRefused) as exc:
        # Never print private packet contents or references in diagnostics.
        print(f"BLOCKED: {type(exc).__name__}", file=sys.stderr)
        return 2
    print(json.dumps(outcome, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
