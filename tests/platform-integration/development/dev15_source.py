#!/usr/bin/env python3
"""DEV-15 first-adopter source reconciliation; never a native acceptance runner.

Consume immutable reviewed Shared and engine checkouts through the existing
DEV-14 profile validator. All ENG-ONB and engine-specific cases remain
BLOCKED until *independently observed* real IAM/CP/native runtime execution
and teardown in Infrastructure's disposable DEV-01 lifecycle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import engine_onboarding as onboarding

HERE = Path(__file__).resolve().parent
LOCK = HERE / "dev15-owner-lock.json"
ALLOWED = {
    "pulse-intelligence": "baobab-platform/baobab-pulse",
    "payments-sandbox": "baobab-platform/baobab-payments",
}
CASE_IDS = {f"ENG-ONB-{n:02d}" for n in range(1, 10)}


def checked_lock(path: Path = LOCK) -> dict:
    lock = onboarding.checked_json(path)
    onboarding.require(set(lock) == {
        "schema", "shared", "adopters", "environment", "synthetic_only",
        "protected_acceptance",
    }, "DEV15_LOCK_SHAPE")
    onboarding.require(lock["schema"] == "infrastructure.dev15.first-adopters.source-lock.v1"
                       and lock["shared"] == onboarding.SHARED_SHA, "DEV15_LOCK_SHARED_MISMATCH")
    onboarding.require(lock["environment"] == "development"
                       and lock["synthetic_only"] is True
                       and lock["protected_acceptance"] is False, "DEV15_LOCK_ENVIRONMENT_REFUSED")
    onboarding.require(isinstance(lock["adopters"], dict)
                       and set(lock["adopters"]) == set(ALLOWED), "DEV15_LOCK_ADOPTER_ROSTER")
    for name, row in lock["adopters"].items():
        onboarding.require(isinstance(row, dict) and set(row) == {"repo", "sha"}
                           and row["repo"] == ALLOWED[name] and isinstance(row["sha"], str)
                           and bool(onboarding.SHA.fullmatch(row["sha"])), "DEV15_OWNER_LOCK_INVALID")
    return lock


def reconcile(shared: Path, owners: dict[str, Path], lock: dict) -> dict:
    onboarding.require(set(owners) == set(ALLOWED), "DEV15_OWNER_ROSTER_REQUIRED")
    result = {}
    for profile in sorted(ALLOWED):
        owner = owners[profile]
        owner_sha = lock["adopters"][profile]["sha"]
        # This invokes Shared's *real* canonical schema/semantic validation
        # and owner capability/provider evidence validation. No simulation.
        plan = onboarding.source_plan(profile, shared, owner, owner_sha)
        onboarding.require(plan["source"]["engine_sha"] == owner_sha
                           and plan["owner_support"] == "DECLARED_IMPLEMENTATION_ONLY"
                           and plan["result"] == "BLOCKED"
                           and plan["eng_onb_runtime_cases"] == "NOT_EXECUTED"
                           and plan["protected_acceptance"] is False
                           and plan["production_authorized"] is False,
                           "DEV15_SOURCE_VALIDATION_INCOMPLETE")
        profile_data = onboarding.checked_json(
            shared / onboarding.PROFILE_DIR / (profile + ".json")
        )
        cases = profile_data["reporting"]["case_ids"]
        onboarding.require(len(cases) == len(set(cases)) and CASE_IDS <= set(cases)
                           and profile_data["subject_engine"] == ALLOWED[profile].split("/")[-1],
                           "DEV15_REQUIRED_CASE_DRIFT")
        result[profile] = {
            "subject_engine": profile_data["subject_engine"],
            "owner_sha": owner_sha,
            "source_profile_sha256": plan["source"]["profile_sha256"],
            "owner_declaration_validated": True,
            "source_graph_validated": True,
            "required_services": plan["required_service_order"],
            "blockers": plan["blockers"],
            "runtime_status": "BLOCKED",
            "cases": {k: {"result": "BLOCKED", "reason": "NOT_EXECUTED",
                          "evidence": []} for k in cases},
            "independently_verified_teardown": False,
        }
    return {
        "schema": "infrastructure.dev15.first-adopters.source-inventory.v1",
        "shared_sha": onboarding.SHARED_SHA,
        "evidence_class": "SOURCE_ONLY",
        "adopters": result,
        "eng_onb_runtime_qualified": False,
        "dev15_accepted": False,
        "protected_acceptance": False,
        "production_authorized": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", type=Path, required=True)
    parser.add_argument("--pulse-root", type=Path, required=True)
    parser.add_argument("--payments-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        data = reconcile(args.shared_root, {
            "pulse-intelligence": args.pulse_root,
            "payments-sandbox": args.payments_root,
        }, checked_lock())
        blob = json.dumps(data, sort_keys=True, indent=2) + "\n"
        if args.output:
            # CI writes source inventory only; never private secrets, runtime
            # credentials, or claims that an engine actually served a request.
            args.output.write_text(blob, encoding="utf-8")
            print("DEV15_SOURCE_INVENTORY_SHA256 " + hashlib.sha256(blob.encode()).hexdigest())
        else:
            print(blob, end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError, onboarding.Refused) as err:
        # Stable error code only: don't leak owner paths or local configuration.
        code = str(err) if isinstance(err, onboarding.Refused) else "UNAVAILABLE_OR_INVALID_SOURCE"
        print("DEV15_REFUSED " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
