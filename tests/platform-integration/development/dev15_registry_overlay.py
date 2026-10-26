#!/usr/bin/env python3
"""Explicit, development-only authoritative workload registry overlay.

DEV-01's existing CP bundle stays frozen. This overlay can expose the six
Shared-approved DEV-15 client registrations to the disposable CP runtime
without changing its embedded contract snapshot or provisioning any client.
Hydra issuance, CP grants and live authority remain separate required steps.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import secrets
import stat
import sys

import yaml

import dev
import dev15_registry
import engine_onboarding as onboard

NAME = "dev15-workload-registry.yaml"


def install(run_id: str, shared_root: Path) -> dict:
    dev.require(os.environ.get("BAOBAB_ENVIRONMENT") == "development",
                "EXPLICIT_DEVELOPMENT_REQUIRED")
    directory, state = dev.current(run_id)
    dev.require(state["phase"] == "PREPARED"
                and state["environment"] == "development"
                and state["lease_seconds"] <= 3600
                and "dev15_registry_sha256" not in state,
                "DEV15_REGISTRY_PREPARED_ONLY")
    dev.require(not shared_root.is_symlink(), "DEV15_SHARED_SYMLINK_REFUSED")
    shared = shared_root.resolve(strict=True)
    sha, clean = onboard.git_identity(shared)
    dev.require(sha == onboard.SHARED_SHA and clean, "DEV15_SHARED_SOURCE_NOT_PINNED")
    profiles = {
        name: onboard.checked_json(shared / onboard.PROFILE_DIR / (name + ".json"))
        for name in dev15_registry.PROFILE_NAMES
    }
    file = shared / dev15_registry.SHARED_REGISTRY
    source_bytes = file.read_bytes()
    dev.require(len(source_bytes) <= 131072 and not file.is_symlink(),
                "DEV15_REGISTRY_SIZE_OR_SYMLINK")
    canonical = yaml.safe_load(source_bytes)["workloads"]
    # This validates registration, ACTIVE development status and audience/scope
    # ceilings, but expressly does NOT impersonate IAM issuer read-back.
    validation = dev15_registry.validate(profiles, canonical, canonical)
    dev.require(len(validation["registered_development_clients"]) == 6,
                "DEV15_CANONICAL_CLIENTS_REQUIRED")
    dest = directory / NAME
    dev.require(not dest.exists() and not dest.is_symlink(),
                "DEV15_REGISTRY_ALREADY_EXISTS")
    # Atomic 0644 file inside a 0700 host run directory: Docker can mount
    # read-only for CP's unprivileged process, unrelated users cannot browse.
    temp = directory / ("." + NAME + "." + secrets.token_hex(8))
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(source_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, dest)
        dev.require(stat.S_ISREG(dest.stat().st_mode) and not dest.is_symlink(),
                    "DEV15_REGISTRY_MATERIALIZATION_INVALID")
        handle = os.open(directory, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)
    finally:
        temp.unlink(missing_ok=True)
    digest = hashlib.sha256(source_bytes).hexdigest()
    state["dev15_registry_sha256"] = digest
    state["dev15_registry_source_sha"] = sha
    dev.persist(directory, state, "PREPARED")
    return {
        "schema": "infrastructure.dev15.registry-runtime-overlay.v1",
        "run_id": run_id,
        "source_sha": sha,
        "registry_sha256": digest,
        "registered_clients": validation["registered_development_clients"],
        "result": "SOURCE_MOUNT_PREPARED",
        "real_iam_credentials": "NOT_PROVISIONED",
        "current_cp_grants": "NOT_OBSERVED",
        "connected_acceptance": "BLOCKED",
        "protected_acceptance": False,
        "production_authorized": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--shared-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with dev.guarded(args.run_id):
            result = install(args.run_id, args.shared_root)
        print(__import__("json").dumps(result, sort_keys=True))
        return 0
    except (dev.Refused, onboard.Refused, OSError, ValueError, KeyError, TypeError,
            yaml.YAMLError) as exc:
        code = str(exc) if isinstance(exc, (dev.Refused, onboard.Refused)) else "INVALID_SOURCE"
        print("DEV15_REGISTRY_BLOCKED " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
