#!/usr/bin/env python3
"""DEV-14 native component execution on DEV-01's disposable IAM/CP topology.

Bounded, private and deliberately *not* a DEV-15 ENG-ONB acceptance runner.
Uses real pinned owner source/build, actual native stores and HTTP readiness.
No workload credential is minted by this runner, no CP capability activated,
and no money movement is executed. The ordinary DEV-01 watchdog, immutable
evidence, guarded cleanup and independent owned-resource check remain in force.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time

import adapter
import dev
import dev15_compose
import dev15_registry_overlay
import dev15_source
import engine_onboarding as onboard

BASE = Path(__file__).resolve().parent
NATIVE_HEALTH = BASE / "dev15_health.py"
QDRANT_LOCK = BASE / "external-lock.json"


def owner_source(directory: Path, state: dict, name: str, sha: str) -> Path:
    """Fetch precisely one reviewed engine source into the leased run's tree."""
    repo = dev15_compose.OWNERS[name]
    dev.require(re.fullmatch(r"[0-9a-f]{40}", sha), "DEV15_OWNER_SOURCE_PIN_REQUIRED")
    target = directory / "sources" / repo
    dev.require(not target.exists() and not target.is_symlink(), "DEV15_OWNER_ALREADY_PRESENT")
    dev.call(["git", "init", "-q", str(target)], state=state)
    dev.call(["git", "-C", str(target), "fetch", "--quiet", "--depth", "1",
              f"https://github.com/baobab-platform/{repo}.git", sha], state=state, timeout=180)
    dev.call(["git", "-C", str(target), "checkout", "--quiet", "--detach", "FETCH_HEAD"], state=state)
    observed, clean = onboard.git_identity(target)
    dev.require(observed == sha and clean, "DEV15_OWNER_SOURCE_DRIFT")
    state["sources"][repo] = sha
    dev.persist(directory, state, "PREPARED")
    return target


def plan_native(run_id: str, profile_name: str, shared: Path) -> None:
    """Reserve exact owner source and current canonical development registry."""
    directory, state = dev.current(run_id)
    dev.require(state["phase"] == "PREPARED", "DEV15_PREPARED_REQUIRED")
    lock = dev15_source.checked_lock()
    sha = lock["adopters"][profile_name]["sha"]
    owner = owner_source(directory, state, profile_name, sha)
    receipt = onboard.source_plan(profile_name, shared, owner, sha)
    dev.require(receipt["owner_support"] == "DECLARED_IMPLEMENTATION_ONLY"
                and receipt["result"] == "BLOCKED"
                and receipt["eng_onb_runtime_cases"] == "NOT_EXECUTED",
                "DEV15_OWNER_CONTRACT_REFUSED")
    dev15_registry_overlay.install(run_id, shared)
    directory, state = dev.current(run_id)
    state["dev15_profile"] = profile_name
    state["dev15_owner_sha"] = sha
    state["dev15_native_component"] = "NOT_STARTED"
    dev.persist(directory, state, "PREPARED")


def build_and_run(run_id: str, shared: Path, name: str) -> dict:
    """Run only native component/migrations and observe network/identity."""
    directory, state = dev.current(run_id)
    dev.require(state["phase"] == "RUNNING" and state.get("dev15_profile") == name,
                "DEV15_RUNTIME_NOT_PREPARED")
    source_sha = state["dev15_owner_sha"]
    source = directory / "sources" / dev15_compose.OWNERS[name]
    observed, clean = onboard.git_identity(source)
    dev.require(observed == source_sha and clean, "DEV15_OWNER_SOURCE_DRIFT")
    descriptor = onboard.checked_json(shared / onboard.PROFILE_DIR / (name + ".json"))
    dev.require(descriptor["profile_key"] == name
                and state["dev15_registry_source_sha"] == onboard.SHARED_SHA,
                "DEV15_SOURCE_OR_AUTHORITY_DRIFT")

    filename = "Dockerfile.integration" if name == "pulse-intelligence" else "Dockerfile"
    dev.check_dockerfile(source / filename)
    image = state["project"] + "-dev15-subject"
    args = ["docker", "build", "--tag", image, "--file", str(source / filename)]
    for key, value in {**dev.labels(state), "org.opencontainers.image.revision": source_sha}.items():
        args.extend(["--label", key + "=" + value])
    dev.call([*args, str(source)], state=state, timeout=1800)
    image_id = dev.call(["docker", "image", "inspect", image, "--format", "{{.Id}}"], state=state)
    dev.require(bool(dev15_compose.IMAGE_ID.fullmatch(image_id)),
                "DEV15_BUILT_IMAGE_ID_REQUIRED")
    state["images"]["dev15-subject"] = image
    state["image_ids"]["dev15-subject"] = image_id

    owned_images = {}
    if name == "pulse-intelligence":
        external = onboard.checked_json(QDRANT_LOCK)
        dev.require(external.get("schema") == "infrastructure.dev06.sources.v1"
                    and isinstance(external.get("qdrant"), str)
                    and onboard.IMAGE.fullmatch(external["qdrant"]), "DEV15_QDRANT_LOCK_REFUSED")
        owned_images["qdrant"] = external["qdrant"]
        state["secrets"]["pulse_db"] = secrets.token_hex(32)
        # The already reviewed DEV-01 base lock supplies PostgreSQL 17.
        owned_images["postgres"] = dev.load_lock(state["lock_file"])["images"]["postgres"]
        dev.call(["docker", "pull", owned_images["qdrant"]], state=state, timeout=180)
    else:
        dev.require(name == "payments-sandbox", "DEV15_PROFILE_REFUSED")

    baseline = dev.read(directory / "compose.json")
    composition = dev15_compose.apply(
        descriptor, baseline, subject_image=image_id,
        images=owned_images, secrets=state["secrets"], labels=dev.labels(state),
    )
    # Probe's fixed health witness was mounted before DEV-01 bootstrap.
    dev.write(directory / "compose.json", composition)
    state["compose_sha256"] = hashlib.sha256((directory / "compose.json").read_bytes()).hexdigest()
    dev.persist(directory, state, "RUNNING")
    dev.compose(directory, state, "config", "--quiet")

    if name == "pulse-intelligence":
        dev.compose(directory, state, "up", "-d", "--wait", "--wait-timeout", "120",
                    "pulse-db", "pulse-qdrant", timeout=180)
        # The adapter refuses missing or non-private development PostgreSQL.
        raw = dev.compose(
            directory, state, "run", "--rm", "--no-deps",
            "-e", "BAOBAB_DEV14_PRIVATE_RUN=1", "--entrypoint", "python",
            "dev15-subject", "/app/.baobab/development_adapter.py", "migrate",
            timeout=180,
        )
        migrated = json.loads(raw.splitlines()[-1])
        dev.require(migrated.get("phase") == "migrate" and migrated.get("result") == "PASS"
                    and migrated.get("native_effect_observed") is True
                    and migrated.get("runtime_eng_onb_qualified") is False,
                    "DEV15_NATIVE_MIGRATION_NOT_OBSERVED")
    dev.compose(directory, state, "up", "-d", "dev15-subject", timeout=120)

    verified = False
    for _ in range(30):
        try:
            raw = dev.compose(directory, state, "exec", "-T", "probe",
                              "python", "/dev15_health.py", name, timeout=15)
            result = json.loads(raw.splitlines()[-1])
            if (result.get("observed") is True and result.get("result") == "PASS"
                    and result.get("eng_onb_runtime_qualified") is False):
                verified = True
                break
        except (dev.Refused, ValueError, KeyError, TypeError):
            pass
        time.sleep(2)
    dev.require(verified, "DEV15_NATIVE_COMPONENT_UNAVAILABLE")

    native_container = dev.compose(directory, state, "ps", "-q", "dev15-subject")
    dev.require(bool(re.fullmatch(r"[0-9a-f]{12,64}", native_container)),
                "DEV15_NATIVE_CONTAINER_REQUIRED")
    native = json.loads(dev.call(["docker", "inspect", native_container], state=state))[0]
    network = native["NetworkSettings"]["Networks"]
    dev.require(native["Image"] == image_id
                and native["Config"]["Labels"].get("io.baobab.dev.run") == run_id
                and not native["HostConfig"]["PortBindings"]
                and not native["HostConfig"]["Privileged"]
                and len(network) == 1, "DEV15_NATIVE_RUNTIME_IDENTITY_REFUSED")
    inspected = json.loads(dev.call(["docker", "network", "inspect", next(iter(network))], state=state))[0]
    dev.require(inspected["Internal"] is True, "DEV15_PUBLIC_NATIVE_NETWORK_REFUSED")
    state["dev15_native_component"] = "PRIVATE_REAL_COMPONENT_OBSERVED"
    dev.persist(directory, state, "RUNNING")
    return {
        "profile": name, "native_image_id": image_id,
        "source_sha": source_sha,
        "component_health": "PASS", "network_private": True,
        "eng_onb_runtime_qualified": False, "protected_acceptance": False,
        "production_authorized": False,
    }


def run_native(name: str, shared: Path, lease: int) -> int:
    dev.require(name in dev15_compose.OWNERS, "DEV15_PROFILE_REFUSED")
    dev.require(os.environ.get("BAOBAB_ENVIRONMENT") == "development",
                "EXPLICIT_DEVELOPMENT_REQUIRED")
    run_id = None
    try:
        lock_name = "external-base-lock.json" if name == "pulse-intelligence" else "lock.json"
        run_id = dev.prepare(lease=lease, lock_name=lock_name)
        with dev.guarded(run_id):
            plan_native(run_id, name, shared)
            dev.up(run_id)
            build_and_run(run_id, shared, name)
            # This only qualifies the already-existing generic DEV-01 base
            # lifecycle. No capability grant or ENG-ONB case is promoted.
            dev.test(run_id)
        return 0
    finally:
        if run_id is not None:
            with dev.guarded(run_id):
                dev.down(run_id)
        # Host-owned resource labels must disappear even after exceptions.
        dev.recover()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(dev15_compose.OWNERS), required=True)
    parser.add_argument("--shared-root", required=True, type=Path)
    parser.add_argument("--lease-seconds", type=int, default=3600)
    args = parser.parse_args(argv)
    try:
        result = run_native(args.profile, args.shared_root, args.lease_seconds)
        print("DEV15_NATIVE_COMPONENT_RUN_COMPLETED_NO_ENG_ONB_ACCEPTANCE")
        return result
    except (dev.Refused, onboard.Refused, OSError, ValueError, KeyError, TypeError):
        print("DEV15_NATIVE_RUN_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
