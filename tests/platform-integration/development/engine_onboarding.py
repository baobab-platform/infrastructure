#!/usr/bin/env python3
"""DEV-14 source-bound engine profile planning.

This is deliberately NOT a substitute for the DEV-01 runtime executor. The
source plan cannot start a provider, mint tokens, set CP grants, or claim an
ENG-ONB runtime PASS. Infrastructure must separately connect the native owner
adapter before the engine-specific up/test/evidence/down path can be enabled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
import sys

SHARED_SHA = "9fa1bbd6ad9b5c9d4ec406c721bd75227803dcea"
PROFILE_DIR = Path("contracts/development/v1/examples/engines")
PROFILE_SCHEMA = "baobab.engine-integration-profile.v1"
IMAGE = re.compile(r"^[a-z0-9._/-]+(?::[a-zA-Z0-9._-]+)?@sha256:[0-9a-f]{64}$")
SHA = re.compile(r"^[a-f0-9]{40}$")
KEY = re.compile(r"^[a-z][a-z0-9-]{1,62}$")


class Refused(ValueError):
    """Only stable reason codes reach CI stdout/stderr."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise Refused(code)


def checked_json(path: Path, limit: int = 65536) -> dict:
    require(not path.is_symlink() and path.is_file(), "SOURCE_FILE_REQUIRED")
    require(stat.S_ISREG(path.stat().st_mode) and path.stat().st_size <= limit, "SOURCE_FILE_REFUSED")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Refused("INVALID_SOURCE_JSON") from exc
    require(isinstance(data, dict), "INVALID_SOURCE_JSON")
    return data


def git_identity(root: Path) -> tuple[str, bool]:
    """Always check the checkout's actual HEAD, not a caller's claim."""
    def git(*args):
        try:
            return subprocess.run(
                ["git", "-C", str(root), *args], text=True, capture_output=True,
                check=True, timeout=20,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise Refused("GIT_SOURCE_UNAVAILABLE") from exc
    sha = git("rev-parse", "HEAD")
    require(bool(SHA.fullmatch(sha)), "INVALID_SOURCE_REVISION")
    return sha, not bool(git("status", "--porcelain"))


def shared_profile(shared: Path, name: str) -> tuple[dict, str, Path]:
    """Use one exact reviewed Shared commit, and its actual DEV-14 validator."""
    require(bool(KEY.fullmatch(name)), "PROFILE_NAME_REFUSED")
    require(shared.exists() and not shared.is_symlink(), "SHARED_CHECKOUT_REQUIRED")
    revision, clean = git_identity(shared)
    require(revision == SHARED_SHA and clean, "SHARED_SOURCE_PIN_MISMATCH")
    path = shared / PROFILE_DIR / (name + ".json")
    data = checked_json(path)
    require(data.get("schema") == PROFILE_SCHEMA and data.get("profile_key") == name, "PROFILE_IDENTITY_MISMATCH")
    return data, hashlib.sha256(path.read_bytes()).hexdigest(), path


def shared_validate(shared: Path, path: Path, owner: Path | None) -> dict:
    """Invoke, never reimplement, the authoritative Shared schema/semantic checks."""
    args = [sys.executable, "-B", str(shared / "scripts/engine_integration_profile.py"), str(path)]
    if owner is not None:
        args += ["--engine-root", str(owner)]
    try:
        result = subprocess.run(args, cwd=shared / "scripts", capture_output=True,
                                text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise Refused("SHARED_VALIDATOR_UNAVAILABLE") from exc
    # The validator's error text is deliberately not forwarded: no path or
    # private engine data is allowed into an automation log by this wrapper.
    require(result.returncode == 0, "SHARED_PROFILE_REFUSED")
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise Refused("SHARED_RECEIPT_INVALID") from exc
    require(receipt.get("scope") == "SOURCE_PROFILE_VALIDATION_ONLY"
            and receipt.get("protected_acceptance") is False
            and receipt.get("production_authorized") is False, "SHARED_RECEIPT_INVALID")
    return receipt


def source_plan(name: str, shared_root: Path, engine_root: Path | None = None,
                engine_sha: str | None = None, image_lock: Path | None = None) -> dict:
    shared = shared_root.resolve(strict=True)
    data, profile_hash, profile_path = shared_profile(shared, name)
    owner = None
    owner_head = None
    if engine_root is not None:
        require(engine_sha is not None and bool(SHA.fullmatch(engine_sha)), "ENGINE_SOURCE_PIN_REQUIRED")
        require(not engine_root.is_symlink(), "OWNER_SYMLINK_REFUSED")
        owner = engine_root.resolve(strict=True)
        owner_head, clean = git_identity(owner)
        require(owner_head == engine_sha and clean, "ENGINE_SOURCE_PIN_MISMATCH")
    else:
        require(engine_sha is None, "OWNER_CHECKOUT_REQUIRED")

    verified = shared_validate(shared, profile_path, owner)
    required = data["services"]["required"]
    optional = data["services"]["optional"]
    graph = {node["key"]: node for node in required + optional}
    order = verified["service_order"]
    require(set(order) == {node["key"] for node in required}
            and len(order) == len(required), "PLANNER_GRAPH_DRIFT")
    # Strict, explicit image supply: each required container must have an exact
    # OCI digest. Image absence is BLOCKED, never inferred from the Dockerfile.
    image_pins: dict[str, str] = {}
    if image_lock is not None:
        image_lock = image_lock.resolve(strict=True)
        pinned = checked_json(image_lock)
        require(set(pinned) == {"schema", "profile_key", "images"}
                and pinned["schema"] == "infrastructure.dev14.images.v1"
                and pinned["profile_key"] == name and isinstance(pinned["images"], dict),
                "IMAGE_LOCK_SHAPE")
        require(set(pinned["images"]) <= set(graph), "IMAGE_LOCK_UNKNOWN_SERVICE")
        for key, digest in pinned["images"].items():
            require(isinstance(digest, str) and bool(IMAGE.fullmatch(digest)),
                    "IMAGE_DIGEST_REQUIRED")
            image_pins[key] = digest

    missing_images = sorted(set(order) - set(image_pins))
    blockers = []
    if owner is None:
        blockers.append("ENGINE_SOURCE_NOT_INSPECTED")
    if missing_images:
        blockers.append("REQUIRED_IMAGE_DIGEST_MISSING")
    # Even a complete source plan does NOT imply the native Compose adapter
    # exists in Infrastructure, or that the tokens/CP/engine were ever run.
    blockers.append("RUNTIME_ADAPTER_NOT_QUALIFIED")
    return {
        "schema": "infrastructure.dev14.source-plan.v1",
        "profile_key": name,
        "mode": data["mode"],
        "source": {"shared_sha": SHARED_SHA, "profile_sha256": profile_hash,
                   "engine_sha": owner_head},
        "required_service_order": order,
        "optional_services": sorted(node["key"] for node in optional),
        "required_images": {key: image_pins.get(key) for key in order},
        "missing_image_pins": missing_images,
        "canonical_capabilities": verified["capabilities"],
        "owner_support": verified["owner_support"],
        "blockers": blockers,
        "result": "BLOCKED",
        "evidence_class": "SOURCE",
        "eng_onb_runtime_cases": "NOT_EXECUTED",
        "synthetic_only": True,
        "protected_acceptance": False,
        "production_authorized": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("doctor", "plan"))
    parser.add_argument("--profile", required=True)
    parser.add_argument("--shared-root", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path)
    parser.add_argument("--engine-sha")
    parser.add_argument("--image-lock", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = source_plan(args.profile, args.shared_root, args.engine_root,
                           args.engine_sha, args.image_lock)
        if args.action == "doctor":
            # No Docker command is run by a source-only doctor. Runtime tools,
            # registry access, private networking and credentials are checked
            # by the later engine-specific Infrastructure executor.
            plan["doctor_scope"] = "SOURCE_AND_OWNER_DECLARATIONS_ONLY"
        print(json.dumps(plan, sort_keys=True))
        return 0
    except (Refused, OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, Refused) else "SOURCE_INPUT_UNAVAILABLE"
        print("DEV14_REFUSED " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
