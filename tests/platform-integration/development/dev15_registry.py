#!/usr/bin/env python3
"""DEV-15 registry parity preflight, not an IAM or CP permission oracle.

The embedded CP snapshot can lag Shared even when an operator supplies a
newer runtime registry. Neither a registration nor a valid source profile
issues an IAM credential or grants canonical Tenant authority. Keep these
three states separate for every new engine.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import yaml
import engine_onboarding as onboarding

PROFILE_NAMES = ("pulse-intelligence", "payments-sandbox")
CP_REGISTRY = Path("internal/contracts/shared/identity/v1/workload-registry.yaml")
SHARED_REGISTRY = Path("contracts/identity/v1/workload-registry.yaml")


def validate(client_profiles: dict, shared_registry: dict, cp_registry: dict) -> dict:
    names = {}
    for name in PROFILE_NAMES:
        profile = client_profiles[name]
        onboarding.require(profile["profile_key"] == name
                           and profile["run_policy"]["environment"] == "development"
                           and profile["run_policy"]["synthetic_only"] is True,
                           "DEV15_PROFILE_DEVELOPMENT_ONLY")
        for role in ("caller", "neighbour", "validator"):
            row = profile["iam"][role]
            client_id = row["client_id"]
            onboarding.require(client_id not in names, "DEV15_IDENTITY_NOT_DISTINCT")
            registered = shared_registry.get(client_id)
            onboarding.require(isinstance(registered, dict)
                               and registered.get("status") == "ACTIVE"
                               and registered.get("environment") == "development",
                               "DEV15_CANONICAL_CLIENT_NOT_ACTIVE")
            onboarding.require(set(row["scopes"]) <= set(registered.get("allowed_scopes", []))
                               and set(row["audiences"]) <= set(registered.get("allowed_audiences", [])),
                               "DEV15_CLIENT_SCOPE_OR_AUDIENCE_EXCEEDED")
            names[client_id] = {
                "profile": name,
                "role": role,
                "in_embedded_cp_snapshot": client_id in cp_registry
                                          and cp_registry[client_id] == registered,
            }
    onboarding.require(len(names) == 6, "DEV15_CLIENT_ROSTER_INVALID")
    stale = sorted(client for client, result in names.items() if not result["in_embedded_cp_snapshot"])
    return {
        "schema": "infrastructure.dev15.registry-adoption-preflight.v1",
        "source_status": "VALIDATED",
        "registered_development_clients": sorted(names),
        "cp_embedded_registry_stale_for": stale,
        "embedded_registry_parity": not bool(stale),
        "effective_cp_runtime_registry": "NOT_INSPECTED",
        "real_iam_clients_issued": "NOT_OBSERVED",
        "real_tenant_context_and_grants": "NOT_OBSERVED",
        "dev15_connected_status": "BLOCKED",
        "eng_onb_runtime_qualified": False,
        "protected_acceptance": False,
        "production_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared-root", required=True, type=Path)
    parser.add_argument("--cp-root", required=True, type=Path)
    parser.add_argument("--cp-sha", required=True)
    args = parser.parse_args(argv)
    try:
        shared = args.shared_root.resolve(strict=True)
        cp = args.cp_root.resolve(strict=True)
        onboarding.require(not args.shared_root.is_symlink() and not args.cp_root.is_symlink(),
                           "DEV15_SYMLINK_SOURCE_REFUSED")
        shared_sha, shared_clean = onboarding.git_identity(shared)
        cp_sha, cp_clean = onboarding.git_identity(cp)
        onboarding.require(shared_sha == onboarding.SHARED_SHA and shared_clean,
                           "SHARED_SOURCE_PIN_MISMATCH")
        onboarding.require(cp_sha == args.cp_sha and bool(onboarding.SHA.fullmatch(cp_sha)) and cp_clean,
                           "CP_SOURCE_PIN_MISMATCH")
        profiles = {
            name: onboarding.checked_json(shared / onboarding.PROFILE_DIR / (name + ".json"))
            for name in PROFILE_NAMES
        }
        shared_reg = yaml.safe_load((shared / SHARED_REGISTRY).read_text())["workloads"]
        cp_reg = yaml.safe_load((cp / CP_REGISTRY).read_text())["workloads"]
        report = validate(profiles, shared_reg, cp_reg)
        report["source"] = {"shared_sha": shared_sha, "cp_sha": cp_sha}
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, KeyError, TypeError, ValueError, onboarding.Refused, yaml.YAMLError) as exc:
        code = str(exc) if isinstance(exc, onboarding.Refused) else "SOURCE_INVALID_OR_UNAVAILABLE"
        print("DEV15_REGISTRY_REFUSED " + code, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
