#!/usr/bin/env python3
"""Independent DEV-11 L4-OPS-01 custody join: actual GitHub jobs and artifacts.

This process is intentionally a SEPARATE GitHub Actions job from every owner.
Only read-only GitHub API facts and sha256-verified, bounded artifact ZIPs enter
its decisions. No self-reported PASS, skipped step, screenshot, raw log or
source-only graph can satisfy a required runtime/browser gate.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import math
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

SHA = re.compile(r"^[a-f0-9]{40}$")
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
LABELS = {
    "nabhold": {
        "repo": "nabhold", "workflow": ".github/workflows/ci.yml",
        "job": "Quality gates", "artifact": "nabhold-experience-browser-evidence",
        "steps": {
            "playwright": "Public functional end-to-end journeys (five browser profiles)",
            "accessibility": "WCAG 2.2 AA public accessibility gate",
            "visual": "Landing-page visual and layout gate",
            "lighthouse": "Isolated production-build Lighthouse lab",
            "static_budget": "Enforce approved static budgets after all browser diagnostics",
        },
    },
    "zuribeans": {
        "repo": "zuribeans", "workflow": ".github/workflows/ci.yml",
        "job": "Quality gates", "artifact": "zuribeans-experience-browser-evidence",
        "steps": {
            "playwright": "End-to-end tests",
            "accessibility": "Landing-page accessibility checks",
            "visual": "Landing-page visual regression checks",
            "lighthouse": "Isolated Lighthouse performance lab",
            "static_budget": "Enforce frontend performance budgets",
        },
    },
    "thamani": {
        "repo": "thamani", "workflow": ".github/workflows/ci.yml",
        "job": "Logistics browser keyboard and accessibility",
        "artifact": "thamani-logistics-browser",
        "steps": {
            "playwright": "Verify landing and Next.js logistics routes",
            "logistics_keyboard": "Logistics keyboard and browser journeys",
            "accessibility": "WCAG landing-page and logistics-route accessibility",
            "visual": "Independent homepage visual layout and screenshot evidence",
            "lighthouse": "Isolated Lighthouse production-build lab",
            "static_budget": "Enforce emitted-asset performance budget",
        },
    },
    "l4_exporter": {
        "repo": "infrastructure", "workflow": ".github/workflows/dev11-otel-runtime.yml",
        "job": "Real OTel SDK -> Collector -> independent Jaeger v2 API",
        "artifact": "dev11-otel-real-exporter-only",
        "steps": {
            "native_sdk": "Export actual official SDK spans, not synthetic verifier input",
            "independent_query": "Independent process queries Jaeger v3 read API after exported batch",
            "teardown": "Independently tear down every disposable trace resource",
        },
    },
    "l4_rabbit": {
        "repo": "baobab-trade", "workflow": ".github/workflows/dev11-rabbit-connected.yml",
        "job": "Real RabbitMQ confirms and signed ERP inbox replay/denial",
        "artifact": "dev11-real-rabbit-erp-inbox",
        "steps": {
            "native_outbox": "Prepare canonical event with the actual Medusa module and native locking",
            "broker_and_consumer": "Real RabbitMQ publisher confirmation, durable ERP inbox and replay/forgery negatives",
            "independent_query": "Independently query actual native Trade, publisher and ERP spans",
            "teardown": "Independently tear down disposable OTel runtime and remove private source IDs",
        },
    },
    "l4_iam_cp": {
        "repo": "infrastructure", "workflow": ".github/workflows/dev11-connected-int02.yml",
        "job": "Real Keycloak -> CP L4-01 acceptance",
        "artifact": "int02-synthetic-real-component-receipt",
        "steps": {"native": "INT-02 inside the integration devcontainer",
                  "teardown": "Destroy any disposable resources left behind"},
    },
    "l4_erp_native": {
        "repo": "baobab-erp", "workflow": ".github/workflows/dev11-real-native-engine.yml",
        "job": "Actual Hydra and CP authority, RabbitMQ, ERP and JVM veto native order",
        "artifact": "dev11-real-hydra-cp-native-jvm-engine-local",
        "steps": {
            "real_engine": "Build REAL iDempiere13 JVM with finance veto, then real Gate D OSGi acceptance driver",
            "native_process": "Actual CP/Ory, RabbitMQ, durable inbox, protected JVM, independent CP/native/negative tests",
            "teardown": "Retain only sanitised engine-local independent receipts",
        },
    },
    "l4_bff_trade": {
        "repo": "infrastructure", "workflow": ".github/workflows/dev11-connected-bff-trade.yml",
        "job": "Current IAM/CP and native BFF Trade W3C allow/deny/teardown",
        "artifact": "dev11-native-bff-iam-cp-trade",
        "steps": {"native": "Run real candidate sources and current authority positives and negatives",
                  "teardown": "Independent host cleanup",
                  "container_teardown": "Independent devcontainer cleanup"},
    },
}
CLOSED = {
    "MISSING_RUN_PIN", "INVALID_RUN_PIN", "GITHUB_EVIDENCE_UNAVAILABLE",
    "RUN_IDENTITY_MISMATCH", "RUN_SOURCE_MISMATCH", "RUN_STALE_HEAD", "RUN_NOT_COMPLETE",
    "RUN_FAILED", "RUN_WORKFLOW_MISMATCH", "RUN_EVENT_UNTRUSTED",
    "JOB_NOT_UNIQUE", "JOB_FAILED", "REQUIRED_STEP_NOT_PASSED",
    "ARTIFACT_NOT_UNIQUE", "ARTIFACT_EXPIRED", "ARTIFACT_TOO_LARGE",
    "ARTIFACT_DIGEST_MISSING", "ARTIFACT_DIGEST_MISMATCH",
    "ARTIFACT_ARCHIVE_INVALID", "BROWSER_REPORT_MISSING",
    "INT02_NATIVE_RECEIPT_INVALID", "BFF_NATIVE_RECEIPT_INVALID",
    "PROTECTED_EVIDENCE_FORBIDDEN",
    "OTLP_EXPORTER_RECEIPT_INVALID", "RABBIT_CONNECTED_RECEIPT_INVALID",
    "ERP_NATIVE_CONNECTED_RECEIPT_INVALID",
    "PLAYWRIGHT_RESULT_INVALID", "LIGHTHOUSE_RESULT_INVALID",
    "STATIC_BUDGET_RESULT_INVALID",
}
MAX_ZIP = 200 * 1024 * 1024

class Blocked(Exception):
    def __init__(self, code):
        assert code in CLOSED
        self.code = code
        super().__init__(code)

def require(ok, code):
    if not ok:
        raise Blocked(code)

def untrusted_json(data):
    require(len(data) <= 12_000_000, "ARTIFACT_ARCHIVE_INVALID")
    try:
        return json.loads(data)
    except (ValueError, UnicodeError):
        raise Blocked("ARTIFACT_ARCHIVE_INVALID") from None

# These are the existing approved owner budgets, not values supplied by an
# untrusted artifact. Raising a figure in an estate JSON can never grant PASS.
BUDGETS = (800 * 1024, 250 * 1024, 64 * 1024, 250 * 1024)
GATES = ("functional", "accessibility", "visual", "lighthouse")

def finite_number(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum

def _one_path(names, expected, reason):
    found = [name for name in names if name == expected]
    require(len(found) == 1, reason)
    return found[0]

def _browser_summary(archive, names, owner):
    required_gates = (*GATES, "logistics") if owner == "thamani" else GATES
    counts = {}
    for gate in required_gates:
        name = _one_path(names, f"reports/dev11-{gate}-playwright.json",
                         "PLAYWRIGHT_RESULT_INVALID")
        html = f"playwright-report/dev11-{gate}/index.html"
        require(html in names, "BROWSER_REPORT_MISSING")
        summary = untrusted_json(archive.read(name))
        require(type(summary) is dict and isinstance(summary.get("suites"), list)
                and summary["suites"] and isinstance(summary.get("stats"), dict),
                "PLAYWRIGHT_RESULT_INVALID")
        stats = summary["stats"]
        require(type(stats.get("expected")) is int and stats["expected"] > 0
                and stats.get("unexpected") == 0
                and stats.get("flaky") == 0
                and isinstance(summary.get("errors", []), list)
                and not summary.get("errors"),
                "PLAYWRIGHT_RESULT_INVALID")
        counts[gate] = stats["expected"]

    budget = untrusted_json(archive.read(
        _one_path(names, "reports/static-budget.json", "STATIC_BUDGET_RESULT_INVALID")))
    require(type(budget) is dict and budget.get("profile") == "CI_PRODUCTION_BUILD"
            and budget.get("oversized") == []
            and isinstance(budget.get("limits"), dict),
            "STATIC_BUDGET_RESULT_INVALID")
    if owner == "nabhold":
        keys = ("totalJavaScript", "largestJavaScriptChunk",
                "totalCss", "largestPublicImage")
        measured = budget.get("measured")
        require(type(measured) is list and len(measured) == 4,
                "STATIC_BUDGET_RESULT_INVALID")
        labels = ("All emitted client JavaScript", "Largest JavaScript chunk",
                  "All emitted CSS", "Largest public raster image")
        values = []
        for i, row in enumerate(measured):
            require(type(row) is dict and
                    isinstance(row.get("label"), str) and
                    row["label"].startswith(labels[i]) and
                    row.get("max") == BUDGETS[i] and
                    finite_number(row.get("actual")) and row["actual"] <= BUDGETS[i],
                    "STATIC_BUDGET_RESULT_INVALID")
            values.append(row["actual"])
    else:
        keys = ("totalJavaScript", "largestJavaScriptChunk",
                "totalCss", "largestPublicImage") if owner == "zuribeans" else (
                    "allClientJavaScript", "largestClientChunk",
                    "allCss", "largestPublicImage")
        measured = budget.get("measured")
        require(type(measured) is dict and set(measured) == set(keys),
                "STATIC_BUDGET_RESULT_INVALID")
        values = [measured[k] for k in keys]
        require(all(finite_number(v) and v <= BUDGETS[i]
                    for i, v in enumerate(values)), "STATIC_BUDGET_RESULT_INVALID")
    require(set(budget["limits"]) == set(keys)
            and all(budget["limits"][key] == BUDGETS[i]
                    for i, key in enumerate(keys)),
            "STATIC_BUDGET_RESULT_INVALID")

    routes = ("home", "quotes") if owner == "thamani" else ("home", "markets")
    lab = {}
    for route in routes:
        matching = [name for name in names if
                    name.startswith("test-results/dev11-lighthouse/") and
                    name.endswith("/lighthouse-" + route + ".json")]
        require(len(matching) == 1, "LIGHTHOUSE_RESULT_INVALID")
        result = untrusted_json(archive.read(matching[0]))
        require(type(result) is dict and isinstance(result.get("categories"), dict)
                and isinstance(result.get("audits"), dict),
                "LIGHTHOUSE_RESULT_INVALID")
        categories = result["categories"]
        minimums = {"performance": 0.9, "accessibility": 0.95,
                    "best-practices": 0.95}
        if owner != "thamani" or route == "home":
            minimums["seo"] = 0.95
        for key, minimum in minimums.items():
            entry = categories.get(key)
            value = entry.get("score") if isinstance(entry, dict) else None
            # Match each owning Playwright spec's Math.round(score * 100)
            # threshold, without accepting a different owner budget.
            require(finite_number(value) and value <= 1
                    and math.floor(value * 100 + 0.5) >= minimum * 100,
                    "LIGHTHOUSE_RESULT_INVALID")
        audits = result["audits"]
        cls = audits.get("cumulative-layout-shift")
        lcp = audits.get("largest-contentful-paint")
        cls_value = cls.get("numericValue") if isinstance(cls, dict) else None
        lcp_value = lcp.get("numericValue") if isinstance(lcp, dict) else None
        require(finite_number(cls_value) and cls_value <= 0.1
                and finite_number(lcp_value), "LIGHTHOUSE_RESULT_INVALID")
        resource = audits.get("resource-summary")
        details = resource.get("details") if isinstance(resource, dict) else None
        items = details.get("items") if isinstance(details, dict) else None
        scripts = [row for row in items if isinstance(row, dict)
                   and row.get("resourceType") == "script"] if isinstance(items, list) else []
        require(len(scripts) == 1 and finite_number(scripts[0].get("transferSize"))
                and scripts[0]["transferSize"] <= 250 * 1024,
                "LIGHTHOUSE_RESULT_INVALID")
        lab[route] = {
            "performance_score": math.floor(categories["performance"]["score"] * 100 + 0.5),
            "accessibility_score": math.floor(categories["accessibility"]["score"] * 100 + 0.5),
            "best_practices_score": math.floor(categories["best-practices"]["score"] * 100 + 0.5),
            "seo_score": math.floor(categories["seo"]["score"] * 100 + 0.5) if
                         "seo" in minimums else None,
            "cls": round(cls_value, 4),
            "lcp_lab_ms": round(lcp_value),
            "transferred_script_bytes": scripts[0]["transferSize"],
        }
    # This is an independently projected, allowlisted numerical summary;
    # browser originals (including screenshots and raw Lighthouse JSON) stay
    # solely within their owning GitHub Actions artifact.
    return {
        "playwright_passed_tests": counts,
        "measured_static_bytes": dict(zip(
            ("javascript_total", "javascript_largest", "css_total", "image_largest"),
            values)),
        "lighthouse_labs": lab,
    }

def verify_zip(blob, claimed_digest, category):
    require(len(blob) <= MAX_ZIP and blob[:4] == b"PK\x03\x04", "ARTIFACT_ARCHIVE_INVALID")
    require("sha256:" + hashlib.sha256(blob).hexdigest() == claimed_digest,
            "ARTIFACT_DIGEST_MISMATCH")
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
        rows = archive.infolist()
        require(0 < len(rows) <= 10000, "ARTIFACT_ARCHIVE_INVALID")
        names = [r.filename for r in rows]
        for item in rows:
            path = item.filename
            require(not path.startswith("/") and not path.startswith("\\")
                    and "\\" not in path and ".." not in Path(path).parts
                    and item.file_size <= 80 * 1024 * 1024,
                    "ARTIFACT_ARCHIVE_INVALID")
        if category in ("nabhold", "zuribeans", "thamani"):
            return _browser_summary(archive, names, category)
        if category == "l4_iam_cp":
            matches = [x for x in names if x.endswith("-int02.json")]
            require(len(matches) == 1, "INT02_NATIVE_RECEIPT_INVALID")
            return untrusted_json(archive.read(matches[0]))
        if category == "l4_bff_trade":
            matches = [x for x in names if x.endswith("/completed/receipt.json")]
            require(len(matches) == 1, "BFF_NATIVE_RECEIPT_INVALID")
            return untrusted_json(archive.read(matches[0]))
        if category == "l4_exporter":
            matches = [x for x in names if x == "dev11-exported-runtime.json"
                       or x.endswith("/dev11-exported-runtime.json")]
            require(len(matches) == 1, "OTLP_EXPORTER_RECEIPT_INVALID")
            return untrusted_json(archive.read(matches[0]))
        if category == "l4_erp_native":
            def receipt(suffix):
                rows = [n for n in names if n == suffix or n.endswith("/" + suffix)]
                require(len(rows) == 1, "ERP_NATIVE_CONNECTED_RECEIPT_INVALID")
                return untrusted_json(archive.read(rows[0]))
            return {
                "engine": receipt("dev11-engine-local.json"),
                "native": receipt("dev11-native-effect.json"),
                "lineage": receipt("dev11-cp-jvm-lineage.json"),
                "teardown": receipt("dev09-cleanup.json"),
            }
        if category == "l4_rabbit":
            def exact(suffix):
                matches = [x for x in names if x == suffix or x.endswith("/" + suffix)]
                require(len(matches) == 1, "RABBIT_CONNECTED_RECEIPT_INVALID")
                return untrusted_json(archive.read(matches[0]))
            return {"connected": exact("connected.json"),
                    "exported": exact("independent-exported.json"),
                    "source_pins": exact("source-pins.json")}
        return None
    except (zipfile.BadZipFile, OSError, RuntimeError, KeyError, ValueError):
        raise Blocked("ARTIFACT_ARCHIVE_INVALID") from None

def native_receipt(category, value, pins):
    require(type(value) is dict, "GITHUB_EVIDENCE_UNAVAILABLE")
    if category == "l4_exporter":
        require(value.get("schema") == "infrastructure.dev11.exported-observation.v1"
                and value.get("exported_lineage_observed") is True
                and value.get("native_source_attested") is False
                and value.get("consumer_business_effect_qualified") is False
                and value.get("l4_ops_01") == "BLOCKED"
                and value.get("observed_services") == ["dev11-telemetry-probe"]
                and type(value.get("observed_spans")) is int
                and value["observed_spans"] >= 2
                and type(value.get("parent_edges")) is int
                and value["parent_edges"] >= 1
                and value.get("production_authorized") is False,
                "OTLP_EXPORTER_RECEIPT_INVALID")
        return
    if category == "l4_erp_native":
        e = value.get("engine")
        n = value.get("native")
        a = value.get("lineage")
        t = value.get("teardown")
        require(all(type(x) is dict for x in (e, n, a, t))
                and e.get("schema") == "erp.dev11.real-hydra-cp-rabbit-jvm-engine-local.v1"
                and e.get("real_hydra_workload_token_observed") is True
                and e.get("real_cp_runtime_context_and_mandate_observed") is True
                and e.get("real_rabbitmq_durable_signed_event_to_erp_inbox") is True
                and e.get("real_cp_authorized_idempiere_jvm_sales_order") is True
                and e.get("independent_native_order_and_cp_lineage_readback") is True
                and e.get("real_live_cp_mandate_revocation_denied_next_order") is True
                and e.get("real_broker_redelivery_one_native_order") is True
                and e.get("synthetic_trade_origin_not_authorized_commitment") is True
                and e.get("full_medusa_buyer_commitment_proven") is False
                and e.get("independent_exported_trace_graph_proven") is False
                and e.get("l4_ops_01") == "BLOCKED"
                and e.get("protected_acceptance") is False
                and n.get("schema") == "erp.dev11.independent-real-native-order.v1"
                and n.get("native_order_effect_qualified") is True
                and n.get("native_jvm_authority_attribution_observed") is True
                and n.get("l4_ops_01") == "BLOCKED"
                and a.get("schema") == "baobab.erp.dev11.independent-cp-jvm-lineage.v1"
                and a.get("source") == "TWO_INDEPENDENT_POSTGRES_READ_ONLY_OBSERVERS"
                and a.get("immutable_cp_decisions_match_jvm_native_attributions") is True
                and a.get("native_cp_lineage_qualified") is True
                and a.get("independent_maker_checker_mandate_history") is True
                and a.get("l4_ops_01") == "BLOCKED"
                and t.get("status") == "COMPLETE"
                and t.get("remaining") == {"container": 0, "network": 0, "volume": 0}
                and t.get("temporary_directory_removed") is True
                and t.get("host_or_image_teardown") is False,
                "ERP_NATIVE_CONNECTED_RECEIPT_INVALID")
        return
    if category == "l4_rabbit":
        connected = value.get("connected")
        exported = value.get("exported")
        sources = value.get("source_pins")
        required = {
            "native_medusa_outbox_persisted", "real_rabbitmq_publisher_confirmed",
            "erp_postgres_canonical_admission",
            "real_crash_after_inbox_commit_before_ack_recovered",
            "unchanged_event_redelivery_deduplicated",
            "changed_business_replay_rejected", "bad_signature_rejected_to_dlx",
            "mandatory_unroutable_rejected",
        }
        require(type(connected) is dict and type(exported) is dict
                and type(sources) is dict
                and connected.get("schema") == "trade.dev11.real-rabbit-erp-inbox.v1"
                and connected.get("run_class") == "REAL_NATIVE_MEDUSA_PG_RABBIT_ERPINBOX"
                and all(connected.get(key) is True for key in required)
                and connected.get("native_erp_business_effect_qualified") is False
                and connected.get("l4_ops_01") == "BLOCKED"
                and exported.get("schema") == "infrastructure.dev11.exported-observation.v1"
                and exported.get("exported_lineage_observed") is True
                and all(x in exported.get("observed_services", []) for x in (
                    "baobab-trade", "baobab-trade-rabbit-publisher", "baobab-erp"))
                and exported.get("l4_ops_01") == "BLOCKED"
                and sources.get("trade_sha") == pins["baobab-trade"]
                and sources.get("erp_sha") == pins["baobab-erp"]
                and sources.get("infrastructure_sha") == pins["infrastructure"]
                and connected.get("production_authorized") is False
                and exported.get("production_authorized") is False,
                "RABBIT_CONNECTED_RECEIPT_INVALID")
        return
    require(value.get("protected_acceptance") is not True
            and value.get("production_authorized") is not True, "PROTECTED_EVIDENCE_FORBIDDEN")
    if category == "l4_iam_cp":
        required = {
            "dev11_actual_issuer_cp_authorised_operation",
            "dev11_cp_w3c_child_of_upstream", "dev11_cp_correlation_preserved",
            "dev11_wrong_audience_denied_with_trace",
            "dev11_foreign_organisation_denied_with_trace",
            "dev11_missing_bearer_denied_with_trace",
            "dev11_untrusted_trace_creates_root_without_authority",
        }
        checks = value.get("checks")
        require(value.get("teardown_verified") is True and value.get("passed") is True
                and value.get("qualification_checks_passed") is True
                and isinstance(checks, dict)
                and all(checks.get(k) is True for k in required)
                and value.get("source_pins", {}).get("baobab-cp") == pins["cp"],
                "INT02_NATIVE_RECEIPT_INVALID")
    else:
        conn = value.get("dev11_bff_connected")
        require(type(conn) is dict and conn.get("scope") == "LIVE_NEXT_IAM_CP_MEDUSA_HTTP_ONLY"
                and conn.get("runtime_qualified") is False
                and conn.get("outbox_consumer_qualified") is False
                and value.get("teardown_verified") is True
                and value.get("dev07_bff_runtime_identity_verified") is True
                and value.get("dev07_issuer_cleanup") is True
                and value.get("dev07_binding_revocation_verified") is True
                and all(conn.get("source_pins", {}).get(repo) == pins[repo]
                        for repo in ("baobab-cp", "baobab-trade", "zuribeans"))
                and isinstance(conn.get("checks"), dict)
                and len(conn["checks"]) == 6
                and all(v is True for v in conn["checks"].values()),
                "BFF_NATIVE_RECEIPT_INVALID")

def verify_one(name, binding, pins, api, download):
    spec = LABELS[name]
    repo = "baobab-platform/" + spec["repo"]
    run_id, sha = binding.get("run_id"), binding.get("sha")
    require(type(run_id) is int and run_id > 0 and isinstance(sha, str)
            and SHA.fullmatch(sha), "INVALID_RUN_PIN")
    root = f"/repos/{repo}/actions"
    run = api(f"{root}/runs/{run_id}")
    require(run.get("id") == run_id and run.get("repository", {}).get("full_name", repo) == repo,
            "RUN_IDENTITY_MISMATCH")
    require(run.get("head_sha") == sha, "RUN_SOURCE_MISMATCH")
    require(run.get("path") == spec["workflow"], "RUN_WORKFLOW_MISMATCH")
    require(run.get("event") in ("pull_request", "push", "workflow_dispatch"),
            "RUN_EVENT_UNTRUSTED")
    # Independently read the *current* remote PR or main/dispatch branch.
    # Matching an old historical workflow SHA is not current-head evidence.
    if run["event"] == "pull_request":
        prs = run.get("pull_requests")
        require(isinstance(prs, list) and len(prs) == 1,
                "RUN_STALE_HEAD")
        row = prs[0]
        number = row.get("number")
        require(type(number) is int and number > 0
                and row.get("head", {}).get("sha") == sha,
                "RUN_STALE_HEAD")
        live_pr = api(f"/repos/{repo}/pulls/{number}")
        require(live_pr.get("state") == "open"
                and live_pr.get("head", {}).get("sha") == sha
                and live_pr.get("head", {}).get("repo", {}).get("full_name") == repo,
                "RUN_STALE_HEAD")
    else:
        branch = run.get("head_branch")
        require(isinstance(branch, str) and re.fullmatch(
                r"[a-zA-Z0-9._/-]{1,120}", branch)
                and not branch.startswith("-") and ".." not in branch,
                "RUN_STALE_HEAD")
        if run["event"] == "push":
            require(branch == "main", "RUN_STALE_HEAD")
        live_branch = api(f"/repos/{repo}/branches/{urllib.parse.quote(branch, safe='')}")
        require(live_branch.get("commit", {}).get("sha") == sha,
                "RUN_STALE_HEAD")
    require(run.get("status") == "completed", "RUN_NOT_COMPLETE")
    require(run.get("conclusion") == "success", "RUN_FAILED")
    if name.startswith("l4_"):
        required_sha = (pins["baobab-trade"] if name == "l4_rabbit" else
                        pins["baobab-erp"] if name == "l4_erp_native" else
                        pins["infrastructure"])
        require(sha == required_sha, "RUN_SOURCE_MISMATCH")
    else:
        require(sha == pins[name], "RUN_SOURCE_MISMATCH")
    if name == "l4_rabbit":
        # A passing Trade workflow pinned to a superseded ERP or Infrastructure
        # companion is never current native evidence.
        for dependent, number, pin in (
            ("baobab-erp", 125, "baobab-erp"),
            ("infrastructure", 72, "infrastructure"),
        ):
            owner = api(f"/repos/baobab-platform/{dependent}/pulls/{number}")
            require(owner.get("state") == "open"
                    and owner.get("head", {}).get("sha") == pins[pin],
                    "RUN_STALE_HEAD")
    jobs = api(f"{root}/runs/{run_id}/jobs?per_page=100")
    items = jobs.get("jobs")
    require(isinstance(items, list) and len(items) == jobs.get("total_count")
            and len(items) <= 100, "JOB_NOT_UNIQUE")
    matches = [x for x in items if x.get("name") == spec["job"]
               or str(x.get("name", "")).endswith(" / " + spec["job"])]
    require(len(matches) == 1, "JOB_NOT_UNIQUE")
    job = matches[0]
    require(job.get("conclusion") == "success", "JOB_FAILED")
    steps = job.get("steps")
    require(isinstance(steps, list), "REQUIRED_STEP_NOT_PASSED")
    observed = {key: [s for s in steps if s.get("name") == step]
                for key, step in spec["steps"].items()}
    require(all(len(v) == 1 and v[0].get("conclusion") == "success"
                for v in observed.values()), "REQUIRED_STEP_NOT_PASSED")
    artifacts = api(f"{root}/runs/{run_id}/artifacts?per_page=100")
    rows = artifacts.get("artifacts")
    require(isinstance(rows, list) and len(rows) == artifacts.get("total_count")
            and len(rows) <= 100, "ARTIFACT_NOT_UNIQUE")
    matched = [a for a in rows if a.get("name") == spec["artifact"]]
    require(len(matched) == 1, "ARTIFACT_NOT_UNIQUE")
    art = matched[0]
    require(art.get("expired") is False, "ARTIFACT_EXPIRED")
    require(type(art.get("size_in_bytes")) is int and
            0 < art["size_in_bytes"] <= MAX_ZIP, "ARTIFACT_TOO_LARGE")
    digest = art.get("digest")
    require(isinstance(digest, str) and DIGEST.fullmatch(digest), "ARTIFACT_DIGEST_MISSING")
    blob = download(repo, art["id"])
    receipt = verify_zip(blob, digest, name)
    if name.startswith("l4_"):
        native_receipt(name, receipt, pins)
    if name == "l4_exporter":
        detail = {"actual_otlp_exporter_and_query": "PASS",
                  "disposable_teardown": "PASS",
                  "native_authority_or_effect": "NOT_PROVEN"}
    elif name == "l4_erp_native":
        detail = {
            "real_hydra_cp_broker_native_idempiere": "PASS",
            "independently_verified_cp_jvm_lineage": "PASS",
            "isolated_native_order_and_cleanup": "PASS",
            "real_medusa_buyer_commitment": "NOT_PROVEN",
            "cross_system_otel_lineage": "NOT_PROVEN",
        }
    elif name == "l4_rabbit":
        detail = {"real_trade_rabbit_erp_admission": "PASS",
                  "independently_exported_component_spans": "PASS",
                  "native_idempiere_business_effect": "NOT_PROVEN"}
    elif name.startswith("l4_"):
        detail = {"native_runtime_negatives": "PASS",
                  "independent_teardown": "PASS"}
    else:
        detail = {"measured_results": receipt}
    return {"result": "PASS", "run_id": run_id, "source_sha": sha,
            "job_id": job.get("id"), "artifact_id": art.get("id"),
            "run_url": f"https://github.com/{repo}/actions/runs/{run_id}",
            "artifact_zip_sha256": digest,
            "checks": {key: "PASS" for key in spec["steps"]},
            **detail}

def join(bindings, pins, api, download):
    rows = {}
    for name in LABELS:
        try:
            require(isinstance(bindings.get(name), dict), "MISSING_RUN_PIN")
            rows[name] = verify_one(name, bindings[name], pins, api, download)
        except Blocked as exc:
            rows[name] = {"result": "BLOCKED", "reason": exc.code}
        except (OSError, urllib.error.URLError, TimeoutError):
            rows[name] = {"result": "BLOCKED", "reason": "GITHUB_EVIDENCE_UNAVAILABLE"}
        except (TypeError, AttributeError, KeyError, ValueError):
            rows[name] = {"result": "BLOCKED", "reason": "GITHUB_EVIDENCE_UNAVAILABLE"}
    all_verified = all(row["result"] == "PASS" for row in rows.values())
    # Actual cross-collector exporter and real broker/inbox component tests
    # and real iDempiere engine-local readback can be independently joined.
    # Neither synthetic ERP-A order provenance nor disjoint component traces
    # establish genuine Medusa buyer commitment or one end-to-end L4 run.
    # Never promote an engine-local/component test to
    # L4-OPS-01, regardless of individual GitHub green statuses.
    return {"schema": "infrastructure.dev11.l4-ops-01-join.v1",
            "run_class": "INDEPENDENT_GITHUB_EVIDENCE_JOIN",
            "join_http_and_estates_verified": all_verified,
            "component_and_estates_verified": all_verified,
            "native_idempiere_engine_local_verified":
                rows["l4_erp_native"]["result"] == "PASS",
            "exporter_and_broker_verified": (
                rows["l4_exporter"]["result"] == "PASS" and
                rows["l4_rabbit"]["result"] == "PASS"),
            "l4_ops_01": "BLOCKED",
            "l4_ops_01_reason": "GOVERNED_MEDUSA_COMMITMENT_AND_CROSS_ENGINE_TRACE_NOT_PROVEN"
                                if all_verified else "CONNECTED_OR_ESTATE_EVIDENCE_INCOMPLETE",
            "protected_acceptance": False,
            "production_authorized": False, "sources": rows}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

class GitHub:
    def __init__(self, token):
        self.token = token
        self.opener = urllib.request.build_opener(NoRedirect())

    def api(self, endpoint):
        req = urllib.request.Request("https://api.github.com" + endpoint, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + self.token,
            "User-Agent": "baobab-dev11-independent-evidence-join",
            "X-GitHub-Api-Version": "2022-11-28"})
        with self.opener.open(req, timeout=30) as response:
            return untrusted_json(response.read(2_000_001))

    def download(self, repo, artifact_id):
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip",
            headers={"Authorization": "Bearer " + self.token,
                     "User-Agent": "baobab-dev11-independent-evidence-join"})
        try:
            self.opener.open(req, timeout=30)
        except urllib.error.HTTPError as error:
            require(error.code == 302, "GITHUB_EVIDENCE_UNAVAILABLE")
            location = error.headers.get("Location", "")
        else:
            raise Blocked("GITHUB_EVIDENCE_UNAVAILABLE")
        url = urllib.parse.urlsplit(location)
        host = (url.hostname or "").lower()
        require(url.scheme == "https" and (
            host.endswith(".blob.core.windows.net") or
            host.endswith(".githubusercontent.com")),
            "GITHUB_EVIDENCE_UNAVAILABLE")
        # GitHub's short-lived signed artifact URL is fetched WITHOUT the
        # GitHub access token, to avoid forwarding credentials to cloud storage.
        with urllib.request.urlopen(urllib.request.Request(
             location, headers={"User-Agent": "baobab-dev11-independent-evidence-join"}), timeout=90) as stream:
            data = stream.read(MAX_ZIP + 1)
        require(len(data) <= MAX_ZIP, "ARTIFACT_TOO_LARGE")
        return data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bindings", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        # The binding document is per-run operator-supplied immutable run/sha
        # selections, not mutable branch names or arbitrary external URLs.
        data = untrusted_json(args.bindings.read_bytes())
        require(set(data) == {"schema", "pins", "runs"}
                and data["schema"] == "infrastructure.dev11.join-input.v1"
                and set(data["pins"]) == {"infrastructure", "cp", "baobab-cp",
                                          "baobab-trade", "baobab-erp",
                                          "nabhold", "zuribeans", "thamani"}
                and all(isinstance(v, str) and SHA.fullmatch(v)
                        for v in data["pins"].values())
                and data["pins"]["cp"] == data["pins"]["baobab-cp"],
                "INVALID_RUN_PIN")
        token = os.environ.get("DEV11_EVIDENCE_READ_TOKEN", "")
        require(len(token) >= 15, "GITHUB_EVIDENCE_UNAVAILABLE")
        gh = GitHub(token)
        result = join(data["runs"], data["pins"], gh.api, gh.download)
    except Blocked as exc:
        result = {"schema": "infrastructure.dev11.l4-ops-01-join.v1",
                  "run_class": "INDEPENDENT_GITHUB_EVIDENCE_JOIN",
                  "join_http_and_estates_verified": False, "l4_ops_01": "BLOCKED",
                  "l4_ops_01_reason": exc.code, "sources": {},
                  "protected_acceptance": False, "production_authorized": False}
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        result = {"schema": "infrastructure.dev11.l4-ops-01-join.v1",
                  "run_class": "INDEPENDENT_GITHUB_EVIDENCE_JOIN",
                  "join_http_and_estates_verified": False, "l4_ops_01": "BLOCKED",
                  "l4_ops_01_reason": "GITHUB_EVIDENCE_UNAVAILABLE", "sources": {},
                  "protected_acceptance": False, "production_authorized": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    args.output.write_bytes(raw)
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        hashlib.sha256(raw).hexdigest() + "  " + args.output.name + "\n")
    print("L4-OPS-01=" + result["l4_ops_01"] + " REASON=" + result["l4_ops_01_reason"])
    if not result["join_http_and_estates_verified"]:
        return 2
    # Full L4-OPS-01 is deliberately BLOCKED until real OTel graph and native
    # broker/consumer effects are independently captured and checked.
    return 3

if __name__ == "__main__":
    sys.exit(main())
