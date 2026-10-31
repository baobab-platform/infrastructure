#!/usr/bin/env python3
"""Source-pinned disposable IAM-N07 provider/CP/Redis component run.

This RUNS real Hydra + Kratos + CP + PostgreSQL 17 + TLS Redis using the
existing DEV-01 lifecycle. It never simulates provider replies, grants TMS
authority, exercises a customer booking or calls protected infrastructure.
The original DEV-04 and IAM-N02 runs are unaffected.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import dev

REQUIRED_REDIS_KEYS = frozenset({
    "schema", "classification", "run_id", "source_pins", "redis_image",
    "tls_verified", "run_lease_isolated", "acl_cross_tenant_denied",
    "anonymous_denied", "invalid_password_denied",
    "untrusted_certificate_denied", "cross_worker_getdel_live",
    "one_use_getdel_observed", "issuer_cp_connected_accepted",
    "tms_native_booking_accepted", "protected_accepted",
})


def inspect_redis(directory, state):
    """Reconcile original run-owned Redis observations, never promote to IAM."""
    path = directory / "n07-redis-observation.json"
    observation = dev.read(path)
    dev.require(set(observation) == REQUIRED_REDIS_KEYS
                and observation["schema"] == "infrastructure.n07.redis-original.v1"
                and observation["classification"] ==
                    "REAL_REDIS_TLS_ACL_GETDEL_OBSERVED_UNATTESTED"
                and observation["run_id"] == state["run_id"]
                and observation["source_pins"] == {
                    name: state["sources"][name]
                    for name in ("shared", "baobab-cp", "baobab-iam",
                                 "thamani", "baobab-tms")
                }
                and observation["redis_image"] ==
                    state["runtime_images"]["redis"],
                "N07_REDIS_ORIGINAL_SOURCE_MISMATCH")
    for key in ("tls_verified", "run_lease_isolated",
                "acl_cross_tenant_denied", "anonymous_denied",
                "invalid_password_denied", "untrusted_certificate_denied",
                "one_use_getdel_observed"):
        dev.require(observation[key] is True, "N07_REAL_REDIS_NEGATIVE_MISSING")
    for key in ("cross_worker_getdel_live", "issuer_cp_connected_accepted",
                "tms_native_booking_accepted", "protected_accepted"):
        dev.require(observation[key] is False, "N07_REDIS_ACCEPTANCE_OVERCLAIM")
    return {
        "schema": "infrastructure.n07.redis-checkpoint.v1",
        "run_id": state["run_id"],
        "classification": "REAL_TLS_REDIS_COMPONENT_UNATTESTED",
        "original_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "run_source_pins": state["sources"],
        "tms_native_booking_accepted": False,
        "protected_accepted": False,
    }


def run():
    dev.require(os.environ.get("BAOBAB_ENVIRONMENT") == "development",
                "N07_EXPLICIT_DEVELOPMENT_REQUIRED")
    run_id = dev.prepare(lock_name="n07-base-lock.json")
    checkpoint = None
    try:
        with dev.guarded(run_id):
            directory, state = dev.current(run_id)
            dev.verify_sources(directory, state)
            dev.require(state["phase"] == "PREPARED"
                        and state["lock_file"] == "n07-base-lock.json"
                        and state.get("n07_profile") is True,
                        "N07_EXACT_SOURCE_LEASE_REQUIRED")
            print("N07_STAGE=REAL_ORY_CP_REDIS_UP", flush=True)
            dev.up(run_id)
            print("N07_STAGE=REAL_ORY_CP_HEALTH_AND_CANONICAL_IDENTITY", flush=True)
            dev.test(run_id)
            print("N07_STAGE=REAL_HYDRA_CP_NATIVE_AUTHORITY_NEGATIVES", flush=True)
            authority = dev.qualify(run_id)
            dev.require(set(authority["checks"]) == dev.AUTHORITY_CASES
                        and all(value is True for value in authority["checks"].values())
                        and authority["canonical_provider_qualified"] is False,
                        "N07_REAL_ISSUER_CP_NEGATIVES_MISSING")
            directory, state = dev.current(run_id)
            print("N07_STAGE=REAL_TLS_REDIS_ACL_AND_ONE_USE", flush=True)
            observed = dev.compose(directory, state, "exec", "-T", "probe",
                                   "python", "/n07_redis_probe.py", timeout=60)
            dev.require(observed.strip() == "N07_REAL_TLS_REDIS_OBSERVATION_UNATTESTED",
                        "N07_REDIS_PROBE_NOT_OBSERVED")
            checkpoint = inspect_redis(directory, state)
            state["n07_redis_checkpoint"] = checkpoint
            dev.persist(directory, state, "TESTED")
    finally:
        # The original owner + watchdog lifecycle owns all containers,
        # network, volumes, private issuer tokens and run secrets. Even a
        # partial failure must not retain a usable development service.
        with dev.guarded(run_id):
            dev.down(run_id)

    dev.require(checkpoint is not None and not dev.run_dir(run_id).exists()
                and not dev.resources(run_id), "N07_INDEPENDENT_TEARDOWN_REQUIRED")
    receipt_path = (dev.EVIDENCE / ("dev01-" + run_id)
                    / "completed" / "receipt.json")
    receipt = dev.read(receipt_path)
    digest = dev.read(receipt_path.with_name("receipt.sha256.json"))
    dev.require(hashlib.sha256(receipt_path.read_bytes()).hexdigest() ==
                digest["sha256"] and receipt["run_id"] == run_id
                and receipt.get("teardown_verified") is True
                and receipt.get("n07_redis_checkpoint") == checkpoint
                and receipt.get("protected_acceptance") is False
                and receipt.get("int03c_qualified") is False,
                "N07_FINAL_ORIGINAL_OR_TEARDOWN_MISMATCH")
    print("N07_REAL_IAM_CP_REDIS_COMPONENTS_OBSERVED_BOOKING_HELD", flush=True)
    return 0  # component-only runner, not connected N07 acceptance


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception as exc:
        error = str(exc) if isinstance(exc, dev.Refused) else "RUNTIME_UNAVAILABLE"
        raise SystemExit("N07_DEVELOPMENT_RUN_BLOCKED_NO_ACCEPTANCE " + error)
