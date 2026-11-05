#!/usr/bin/env python3
"""DEV-11 exact six-owner source and genuine buyer->JVM qualification.

Execution is development-only and fail-closed. A synthetic Trade outbox event,
sequential independent labs, source-only pass, a non-exported W3C identifier,
or a browser buyer-context ALLOW are NOT a genuine order commitment.
Actual IAM/CP source and protected JVM evidence must be independently joined.

Two commands:
  sources: verify immutable heads and the controlled six-owner lock
  qualify: inspect ONE disposable running network and exact native Trade
           origin, then independent exported Jaeger/Trade/ERP/CP evidence.

No command grants a buyer, mutates a database or creates an event.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

LOCK = Path(__file__).with_name("dev11-six-owner-lock.json")
SHA = re.compile(r"^[0-9a-f]{40}$")
HEX_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
OWNERS = ("zuribeans", "baobab-iam", "baobab-cp",
          "baobab-trade", "baobab-erp")
SAFE = frozenset({
    "LOCK_INVALID", "SOURCE_MISSING", "SOURCE_HEAD_MISMATCH",
    "GOVERNED_BUYER_COMMIT_ENTRYPOINT_ABSENT",
    "SOURCE_NOT_CLEAN", "SIX_OWNER_RUNTIME_NOT_RUNNING",
    "SIX_OWNER_NETWORK_NOT_SHARED", "SIX_OWNER_SOURCE_IMAGE_MISMATCH",
    "GOVERNED_BUYER_EVENT_REQUIRED", "NATIVE_BUYER_ORIGIN_REFUSED",
    "CURRENT_IAM_CP_AUTHORITY_UNVERIFIED", "INDEPENDENT_NATIVE_EFFECT_REFUSED",
    "INDEPENDENT_EXPORT_REFUSED", "OBSERVER_UNAVAILABLE",
})
SERVICE = {
    "zuribeans": "zuribeans-bff",
    "baobab-iam": "iam",
    "baobab-cp": "cp",
    "baobab-trade": "trade",
    "baobab-erp": "erp",
    "infrastructure": "collector",
}

class Blocked(Exception):
    pass

def insist(ok, reason):
    if not ok:
        raise Blocked(reason)

def safe_report(reason, *, source_verified=False, native_origin=False,
                exported=False, independent_effect=False, network=False):
    return {
        "schema": "infrastructure.dev11.six-owner-genuine-positive.v1",
        "profile": "SINGLE_DISPOSABLE_NATIVE_B2B_ORDER",
        "source_pins_checked": source_verified,
        "one_disposable_network_observed": network,
        "enforced_medusa_buyer_origin": native_origin,
        "independently_exported_full_trace": exported,
        "independent_trade_erp_cp_native_effect": independent_effect,
        "genuine_iam_cp_buyer_commitment_authority_qualified": False,
        "synthetic_event_accepted": False,
        "l4_ops_01": "BLOCKED",
        "production_authorized": False,
        "reason": reason if reason in SAFE else "OBSERVER_UNAVAILABLE",
    }

def sources(root: Path):
    lock = json.loads(LOCK.read_text())
    insist(type(lock) is dict and lock.get("schema") ==
           "infrastructure.dev11.six-owner-source-lock.v1" and
           lock.get("scope") == "DEVELOPMENT_DISPOSABLE_ONLY" and
           lock.get("synthetic_business_inputs_accepted") is False and
           lock.get("decision9_enforcement_required") == "ENFORCED" and
           lock.get("owner") == "infrastructure" and
           lock.get("infrastructure_source") == "EXACT_RUNNING_PR_HEAD" and
           type(lock.get("sources")) is dict and
           set(lock["sources"]) == set(OWNERS) and
           all(type(value) is str and SHA.fullmatch(value)
               for value in lock["sources"].values()),
           "LOCK_INVALID")
    running = root / "infrastructure"
    insist((running / ".git").exists() or (running / ".git").is_file(),
           "SOURCE_MISSING")
    for owner in (*OWNERS, "infrastructure"):
        src = root / owner
        insist(src.is_dir() and (src / ".git").exists() or
               src.is_dir() and (src / ".git").is_file(), "SOURCE_MISSING")
        actual = subprocess.check_output(
            ["git", "-C", str(src), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL).strip()
        expected = os.getenv("DEV11_INFRA_HEAD", "") if owner == "infrastructure" else lock["sources"][owner]
        insist(bool(SHA.fullmatch(expected)) and actual == expected,
               "SOURCE_HEAD_MISMATCH")
        # No local source patches are allowed after checkout; consumers must
        # execute precisely what the source revision attests.
        dirty = subprocess.check_output(
            ["git", "-C", str(src), "status", "--porcelain", "--untracked-files=no"],
            text=True, stderr=subprocess.DEVNULL).strip()
        insist(not dirty, "SOURCE_NOT_CLEAN")
    return lock

def containers(project, lock):
    """Docker inspection of real containers, not a Compose YAML inventory."""
    insist(bool(re.fullmatch(r"dev11-six-[a-z0-9]{10,24}", project or "")),
           "SIX_OWNER_RUNTIME_NOT_RUNNING")
    ids = {}
    for owner, service in SERVICE.items():
        result = subprocess.run(
            ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={project}",
             "--filter", f"label=com.docker.compose.service={service}"],
            capture_output=True, text=True, timeout=10, check=False)
        insist(result.returncode == 0, "SIX_OWNER_RUNTIME_NOT_RUNNING")
        candidates = result.stdout.split()
        insist(len(candidates) == 1, "SIX_OWNER_RUNTIME_NOT_RUNNING")
        detail = subprocess.run(["docker", "inspect", candidates[0]],
            capture_output=True, text=True, timeout=10, check=False)
        insist(detail.returncode == 0, "SIX_OWNER_RUNTIME_NOT_RUNNING")
        record = json.loads(detail.stdout)[0]
        insist(record["State"]["Running"] is True and
               record["HostConfig"]["Privileged"] is False,
               "SIX_OWNER_RUNTIME_NOT_RUNNING")
        labels = record["Config"]["Labels"] or {}
        expected = os.environ["DEV11_INFRA_HEAD"] if owner == "infrastructure" else lock["sources"][owner]
        insist(labels.get("org.opencontainers.image.revision") == expected,
               "SIX_OWNER_SOURCE_IMAGE_MISMATCH")
        ids[owner] = set(record["NetworkSettings"]["Networks"])
    # Every real owner must be attached to a single, private, run-owned network.
    common = set.intersection(*ids.values())
    insist(len(common) == 1 and common.pop() == project + "_private",
           "SIX_OWNER_NETWORK_NOT_SHARED")
    return True

def require_genuine_entrypoint(root: Path):
    """Do not launch a costly stack when no authenticated purchase endpoint exists.

    This is ONLY a negative preflight: a source file's presence cannot establish
    legitimate IAM/CP authority or a native business effect. The runtime and
    read-only independent observer remain mandatory.
    """
    required = (
        root / "zuribeans/src/app/api/buyer/commit/route.ts",
        root / "baobab-trade/src/api/store/b2b/buyer-commit/route.ts",
    )
    insist(all(path.is_file() and path.stat().st_size > 100 for path in required),
           "GOVERNED_BUYER_COMMIT_ENTRYPOINT_ABSENT")
    return True

def trade_origin(root, event_id):
    from psycopg.rows import dict_row
    import psycopg
    insist(bool(HEX_ID.fullmatch(event_id or "")), "GOVERNED_BUYER_EVENT_REQUIRED")
    native_module = root / "baobab-trade/scripts/dev11_native_business_origin.py"
    spec = importlib.util.spec_from_file_location("dev11_native_origin_qualified", native_module)
    insist(spec is not None and spec.loader is not None, "OBSERVER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    with psycopg.connect(os.environ["DEV11_TRADE_READONLY_URL"],
                         row_factory=dict_row) as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        observed = module.assess_native_origin(db, event_id)
    insist(observed.qualified and observed.enforced_b2b_commit and
           observed.exact_commit_transaction and
           observed.spend_commit_same_transaction,
           "NATIVE_BUYER_ORIGIN_REFUSED")
    return True

def independent_graph(root, event_id):
    """Independently query actual exported spans and native DB effects."""
    import psycopg
    from psycopg.rows import dict_row
    sys.path.insert(0, str(root / "infrastructure/tests/platform-integration/development"))
    from dev11_full_vertical_trace import (
        read_native_sources, project_original_export)
    from dev11_exported_trace import query
    with psycopg.connect(os.environ["DEV11_TRADE_READONLY_URL"], row_factory=dict_row) as trade, \
         psycopg.connect(os.environ["DEV11_ERP_READONLY_URL"], row_factory=dict_row) as erp, \
         psycopg.connect(os.environ["DEV11_CP_READONLY_URL"], row_factory=dict_row) as cp:
        trace_id = read_native_sources(trade, erp, cp, event_id)
    exported = project_original_export(
        query("http://127.0.0.1:16686", trace_id), trace_id, event_id)
    insist(exported["same_persisted_event_id_in_three_exported_spans"] and
           exported["exported_bff_issuer_cp_trade_broker_erp_lineage"],
           "INDEPENDENT_EXPORT_REFUSED")
    return True

def qualify(args):
    lock = sources(args.root)
    report = safe_report("GOVERNED_BUYER_EVENT_REQUIRED", source_verified=True)
    try:
        insist(containers(args.project, lock), "SIX_OWNER_NETWORK_NOT_SHARED")
        report["one_disposable_network_observed"] = True
        insist(trade_origin(args.root, args.event_id), "NATIVE_BUYER_ORIGIN_REFUSED")
        report["enforced_medusa_buyer_origin"] = True
        insist(independent_graph(args.root, args.event_id),
               "INDEPENDENT_NATIVE_EFFECT_REFUSED")
        report["independently_exported_full_trace"] = True
        report["independent_trade_erp_cp_native_effect"] = True
        # The native Trade SQL observer and a trace do NOT independently
        # re-introspect the human buyer or verify the original CP operation
        # decision against current IAM. That additional independent authority
        # evidence is mandatory before a genuine buyer positive may pass.
        raise Blocked("CURRENT_IAM_CP_AUTHORITY_UNVERIFIED")
    except Exception as error:
        report["reason"] = str(error) if isinstance(error, Blocked) and str(error) in SAFE else "OBSERVER_UNAVAILABLE"
    return report

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["sources", "entrypoint", "qualify"])
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--project")
    p.add_argument("--private-event-id-file", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        lock = sources(args.root)
        if args.command == "sources":
            # Exact-source PASS is a *preflight only*, never the runtime gate.
            print("DEV11_SIX_OWNER_SOURCE_RECONCILED")
            return 0
        require_genuine_entrypoint(args.root)
        if args.command == "entrypoint":
            print("DEV11_GENUINE_ENTRYPOINT_PRESENT_SOURCE_ONLY")
            return 0
        # IDs remain within the disposable private run, never CLI/history.
        path = args.private_event_id_file
        insist(path is not None and path.is_file() and not path.is_symlink() and
               path.stat().st_size <= 80 and path.stat().st_mode & 0o077 == 0,
               "GOVERNED_BUYER_EVENT_REQUIRED")
        args.event_id = path.read_text().strip()
        report = qualify(args)
    except Exception as exc:
        reason = str(exc) if isinstance(exc, Blocked) and str(exc) in SAFE else "OBSERVER_UNAVAILABLE"
        report = safe_report(reason)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("DEV11_GENUINE_SIX_OWNER="+("QUALIFIED" if report["l4_ops_01"]=="ACCEPTED" else "BLOCKED"))
    return 0 if report["l4_ops_01"] == "ACCEPTED" else 2

if __name__ == "__main__":
    sys.exit(main())
