import hashlib
import io
import json
import unittest
import zipfile

from dev11_evidence_join import LABELS, Blocked, join, verify_one, verify_zip

HEAD = "a" * 40
CP = "b" * 40
TRADE = "c" * 40
ZURI = "d" * 40
PINS = {
    "infrastructure": HEAD, "cp": CP, "baobab-cp": CP,
    "baobab-trade": TRADE, "baobab-erp": "9" * 40,
    "baobab-iam": "8" * 40, "nabhold": "e" * 40,
    "zuribeans": ZURI, "thamani": "f" * 40,
}
REQUIRED_BFF = (
    "dev11_bff_authorised_route_w3c", "dev11_bff_csrf_denied_w3c",
    "dev11_bff_missing_session_denied_w3c", "dev11_native_bff_log_joined",
    "dev11_native_trade_log_joined", "dev11_native_cp_log_joined",
)


def artifact_data(name):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if name in ("nabhold", "zuribeans", "thamani"):
            from dev11_evidence_join import BUDGETS, GATES
            gates = (*GATES, "logistics") if name == "thamani" else GATES
            for gate in gates:
                archive.writestr(
                    f"playwright-report/dev11-{gate}/index.html",
                    "synthetic test display",
                )
                archive.writestr(
                    f"reports/dev11-{gate}-playwright.json",
                    json.dumps({
                        "stats": {"expected": 2, "unexpected": 0, "flaky": 0, "skipped": 0},
                        "suites": [{"title": "synthetic pass"}], "errors": [],
                    }),
                )
            labels = ("totalJavaScript", "largestJavaScriptChunk", "totalCss",
                      "largestPublicImage") if name != "thamani" else (
                      "allClientJavaScript", "largestClientChunk",
                      "allCss", "largestPublicImage")
            if name == "nabhold":
                budget = {"profile": "CI_PRODUCTION_BUILD",
                          "limits": dict(zip(labels, BUDGETS)),
                          "measured": [
                              {"label": label, "actual": maximum // 2, "max": maximum}
                              for label, maximum in zip(
                                  ("All emitted client JavaScript",
                                   "Largest JavaScript chunk (sample)",
                                   "All emitted CSS",
                                   "Largest public raster image (sample)"),
                                  BUDGETS)],
                          "oversized": []}
            else:
                budget = {"profile": "CI_PRODUCTION_BUILD",
                          "limits": dict(zip(labels, BUDGETS)),
                          "measured": {key: maximum // 2 for key, maximum in zip(labels, BUDGETS)},
                          "oversized": []}
            archive.writestr("reports/static-budget.json", json.dumps(budget))
            for route in (("home", "quotes") if name == "thamani" else ("home", "markets")):
                report = {
                    "categories": {k: {"score": .96} for k in
                                   ("performance", "accessibility", "best-practices", "seo")},
                    "audits": {
                        "cumulative-layout-shift": {"numericValue": .02},
                        "largest-contentful-paint": {"numericValue": 1100},
                        "resource-summary": {"details": {"items": [
                            {"resourceType": "script", "transferSize": 200000}]}},
                    },
                }
                archive.writestr(
                    f"test-results/dev11-lighthouse/example/lighthouse-{route}.json",
                    json.dumps(report),
                )
        elif name == "l4_exporter":
            doc = {
                "schema": "infrastructure.dev11.exported-observation.v1",
                "type": "READ_ONLY_JAEGER_V3_QUERY",
                "exported_lineage_observed": True,
                "native_source_attested": False,
                "consumer_business_effect_qualified": False,
                "observed_services": ["dev11-telemetry-probe"],
                "observed_spans": 2, "parent_edges": 1,
                "l4_ops_01": "BLOCKED", "production_authorized": False,
            }
            archive.writestr("dev11-exported-runtime.json", json.dumps(doc))
        elif name == "l4_rabbit":
            connected = {
                "schema": "trade.dev11.real-rabbit-erp-inbox.v1",
                "run_class": "REAL_NATIVE_MEDUSA_PG_RABBIT_ERPINBOX",
                "native_medusa_outbox_persisted": True,
                "real_rabbitmq_publisher_confirmed": True,
                "erp_postgres_canonical_admission": True,
                "real_crash_after_inbox_commit_before_ack_recovered": True,
                "unchanged_event_redelivery_deduplicated": True,
                "changed_business_replay_rejected": True,
                "bad_signature_rejected_to_dlx": True,
                "mandatory_unroutable_rejected": True,
                "native_erp_business_effect_qualified": False,
                "l4_ops_01": "BLOCKED", "production_authorized": False,
            }
            exported = {
                "schema": "infrastructure.dev11.exported-observation.v1",
                "type": "READ_ONLY_JAEGER_V3_QUERY",
                "exported_lineage_observed": True,
                "observed_services": ["baobab-trade",
                                      "baobab-trade-rabbit-publisher", "baobab-erp"],
                "l4_ops_01": "BLOCKED", "production_authorized": False,
            }
            sources = {"trade_sha": TRADE, "erp_sha": PINS["baobab-erp"],
                       "infrastructure_sha": HEAD}
            for name, doc in (("connected.json", connected),
                              ("independent-exported.json", exported),
                              ("source-pins.json", sources)):
                archive.writestr(name, json.dumps(doc))
        elif name == "l4_erp_native":
            engine = {
                "schema": "erp.dev11.real-hydra-cp-rabbit-jvm-engine-local.v1",
                "source_pins": {
                    "baobab-cp": CP, "baobab-iam": PINS["baobab-iam"],
                    "baobab-erp": PINS["baobab-erp"]},
                "real_hydra_workload_token_observed": True,
                "real_cp_runtime_context_and_mandate_observed": True,
                "real_rabbitmq_durable_signed_event_to_erp_inbox": True,
                "real_cp_authorized_idempiere_jvm_sales_order": True,
                "independent_native_order_and_cp_lineage_readback": True,
                "real_live_cp_mandate_revocation_denied_next_order": True,
                "real_broker_redelivery_one_native_order": True,
                "synthetic_trade_origin_not_authorized_commitment": True,
                "full_medusa_buyer_commitment_proven": False,
                "independent_exported_trace_graph_proven": False,
                "l4_ops_01": "BLOCKED", "protected_acceptance": False,
            }
            native = {
                "schema": "erp.dev11.independent-real-native-order.v1",
                "native_order_effect_qualified": True,
                "native_jvm_authority_attribution_observed": True,
                "l4_ops_01": "BLOCKED",
            }
            lineage = {
                "schema": "baobab.erp.dev11.independent-cp-jvm-lineage.v1",
                "source": "TWO_INDEPENDENT_POSTGRES_READ_ONLY_OBSERVERS",
                "immutable_cp_decisions_match_jvm_native_attributions": True,
                "native_cp_lineage_qualified": True,
                "independent_maker_checker_mandate_history": True,
                "l4_ops_01": "BLOCKED",
            }
            teardown = {
                "status": "COMPLETE",
                "remaining": {"container": 0, "network": 0, "volume": 0},
                "temporary_directory_removed": True, "host_or_image_teardown": False,
            }
            for file, receipt in (
                    ("dev11-engine-local.json", engine),
                    ("dev11-native-effect.json", native),
                    ("dev11-cp-jvm-lineage.json", lineage),
                    ("dev09-cleanup.json", teardown)):
                archive.writestr(file, json.dumps(receipt))
        elif name == "l4_iam_cp":
            doc = {"source_pins": {"baobab-cp": CP},
                   "teardown_verified": True, "passed": True,
                   "qualification_checks_passed": True,
                   "checks": {key: True for key in (
                       "dev11_actual_issuer_cp_authorised_operation",
                       "dev11_cp_w3c_child_of_upstream",
                       "dev11_cp_correlation_preserved",
                       "dev11_wrong_audience_denied_with_trace",
                       "dev11_foreign_organisation_denied_with_trace",
                       "dev11_missing_bearer_denied_with_trace",
                       "dev11_untrusted_trace_creates_root_without_authority")}}
            archive.writestr("l4-001-int02.json", json.dumps(doc))
        else:
            doc = {"teardown_verified": True, "dev07_bff_runtime_identity_verified": True,
                   "dev07_issuer_cleanup": True, "dev07_binding_revocation_verified": True,
                   "dev11_bff_connected": {
                       "scope": "LIVE_NEXT_IAM_CP_MEDUSA_HTTP_ONLY",
                       "runtime_qualified": False, "outbox_consumer_qualified": False,
                       "source_pins": {"baobab-cp": CP, "baobab-trade": TRADE,
                                       "zuribeans": ZURI},
                       "checks": {key: True for key in REQUIRED_BFF}}}
            archive.writestr("dev01-run/completed/receipt.json", json.dumps(doc))
    return out.getvalue()


class FakeGitHub:
    def __init__(self):
        self.blobs = {}
        self.urls = {}
        self.bindings = {}
        for index, (name, item) in enumerate(LABELS.items(), 1):
            run_id = 1000 + index
            sha = (TRADE if name == "l4_rabbit" else
                   PINS["baobab-erp"] if name == "l4_erp_native" else
                   HEAD) if name.startswith("l4_") else PINS[name]
            self.bindings[name] = {"run_id": run_id, "sha": sha}
            base = f"/repos/baobab-platform/{item['repo']}/actions/runs/{run_id}"
            blob = artifact_data(name)
            self.blobs[("baobab-platform/" + item["repo"], index)] = blob
            self.urls[base] = {
                "id": run_id, "head_sha": sha, "path": item["workflow"],
                "status": "completed", "conclusion": "success", "event": "pull_request",
                "repository": {"full_name": "baobab-platform/" + item["repo"]},
                "pull_requests": [{"number": index, "head": {"sha": sha}}],
            }
            self.urls[f"/repos/baobab-platform/{item['repo']}/pulls/{index}"] = {
                "state": "open", "head": {
                    "sha": sha, "repo": {"full_name": "baobab-platform/" + item["repo"]},
                },
            }
            self.urls[base + "/jobs?per_page=100"] = {
                "total_count": 1,
                "jobs": [{
                    "id": 2000 + index, "name": item["job"], "conclusion": "success",
                    "steps": [{"name": step, "conclusion": "success"}
                              for step in item["steps"].values()],
                }],
            }
            self.urls[base + "/artifacts?per_page=100"] = {
                "total_count": 1,
                "artifacts": [{
                    "id": index, "name": item["artifact"], "expired": False,
                    "size_in_bytes": len(blob),
                    "digest": "sha256:" + hashlib.sha256(blob).hexdigest(),
                }],
            }

        # Candidate companions are verified independently by current PR
        # head, not an arbitrarily pinned historical ERP/Infrastructure SHA.
        for repo, number, pin in (
            ("baobab-cp", 458, CP), ("baobab-iam", 153, PINS["baobab-iam"])):
            self.urls[f"/repos/baobab-platform/{repo}/pulls/{number}"] = {
                "state": "open", "head": {"sha": pin},
            }
        self.urls["/repos/baobab-platform/baobab-erp/pulls/125"] = {
            "state": "open", "head": {"sha": PINS["baobab-erp"]},
        }
        self.urls["/repos/baobab-platform/infrastructure/pulls/72"] = {
            "state": "open", "head": {"sha": HEAD},
        }

    def api(self, url):
        return self.urls[url]

    def download(self, repo, artifact_id):
        return self.blobs[(repo, artifact_id)]


class DEV11IndependentJoinTests(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()

    def check(self, name):
        return verify_one(name, self.gh.bindings[name], PINS,
                          self.gh.api, self.gh.download)

    def test_green_owner_job_artifact_sha_and_five_real_gates(self):
        result = self.check("nabhold")
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(set(result["checks"]),
                         {"playwright", "accessibility", "visual",
                          "lighthouse", "static_budget"})
        self.assertEqual(result["measured_results"]["playwright_passed_tests"]["functional"], 2)
        self.assertGreaterEqual(
            result["measured_results"]["lighthouse_labs"]["home"]["performance_score"], 90)
        self.assertEqual(
            result["measured_results"]["measured_static_bytes"]["css_total"], 32 * 1024)

    def test_skipped_lighthouse_is_not_pass(self):
        base = "/repos/baobab-platform/nabhold/actions/runs/1001/jobs?per_page=100"
        jobs = self.gh.urls[base]
        jobs["jobs"][0]["steps"][3]["conclusion"] = "skipped"
        with self.assertRaises(Blocked) as error:
            self.check("nabhold")
        self.assertEqual(error.exception.code, "REQUIRED_STEP_NOT_PASSED")

    def test_failed_owner_run_with_artifact_is_not_pass(self):
        self.gh.urls["/repos/baobab-platform/nabhold/actions/runs/1001"]["conclusion"] = "failure"
        with self.assertRaises(Blocked) as error:
            self.check("nabhold")
        self.assertEqual(error.exception.code, "RUN_FAILED")

    def test_historical_success_with_new_pr_head_is_stale(self):
        pr = "/repos/baobab-platform/nabhold/pulls/1"
        self.gh.urls[pr]["head"]["sha"] = "9" * 40
        with self.assertRaises(Blocked) as error:
            self.check("nabhold")
        self.assertEqual(error.exception.code, "RUN_STALE_HEAD")

    def test_forged_source_cannot_join(self):
        self.gh.urls["/repos/baobab-platform/nabhold/actions/runs/1001"]["head_sha"] = "0" * 40
        with self.assertRaises(Blocked) as error:
            self.check("nabhold")
        self.assertEqual(error.exception.code, "RUN_SOURCE_MISMATCH")

    def test_github_success_cannot_override_failed_playwright_json(self):
        original = self.gh.blobs[("baobab-platform/nabhold", 1)]
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            rows = {key: archive.read(key) for key in archive.namelist()}
        key = "reports/dev11-functional-playwright.json"
        report = json.loads(rows[key])
        report["stats"]["expected"] = 0
        rows[key] = json.dumps(report).encode()
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            for path, body in rows.items():
                archive.writestr(path, body)
        modified = out.getvalue()
        self.gh.blobs[("baobab-platform/nabhold", 1)] = modified
        art = self.gh.urls[
            "/repos/baobab-platform/nabhold/actions/runs/1001/artifacts?per_page=100"
        ]["artifacts"][0]
        art["digest"] = "sha256:" + hashlib.sha256(modified).hexdigest()
        art["size_in_bytes"] = len(modified)
        with self.assertRaises(Blocked) as error:
            self.check("nabhold")
        self.assertEqual(error.exception.code, "PLAYWRIGHT_RESULT_INVALID")

    def test_lighthouse_below_threshold_is_rejected(self):
        original = self.gh.blobs[("baobab-platform/zuribeans", 2)]
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            rows = {key: archive.read(key) for key in archive.namelist()}
        key = "test-results/dev11-lighthouse/example/lighthouse-home.json"
        report = json.loads(rows[key])
        report["categories"]["performance"]["score"] = .89
        rows[key] = json.dumps(report).encode()
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            for path, body in rows.items():
                archive.writestr(path, body)
        modified = out.getvalue()
        self.gh.blobs[("baobab-platform/zuribeans", 2)] = modified
        art = self.gh.urls[
            "/repos/baobab-platform/zuribeans/actions/runs/1002/artifacts?per_page=100"
        ]["artifacts"][0]
        art["digest"] = "sha256:" + hashlib.sha256(modified).hexdigest()
        art["size_in_bytes"] = len(modified)
        with self.assertRaises(Blocked) as error:
            self.check("zuribeans")
        self.assertEqual(error.exception.code, "LIGHTHOUSE_RESULT_INVALID")

    def test_static_budget_threshold_inflation_does_not_grant_pass(self):
        original = self.gh.blobs[("baobab-platform/thamani", 3)]
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            rows = {path: archive.read(path) for path in archive.namelist()}
        key = "reports/static-budget.json"
        budget = json.loads(rows[key])
        budget["limits"]["allCss"] *= 2
        rows[key] = json.dumps(budget).encode()
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            for path, body in rows.items():
                archive.writestr(path, body)
        modified = out.getvalue()
        self.gh.blobs[("baobab-platform/thamani", 3)] = modified
        entry = self.gh.urls[
            "/repos/baobab-platform/thamani/actions/runs/1003/artifacts?per_page=100"
        ]["artifacts"][0]
        entry["digest"] = "sha256:" + hashlib.sha256(modified).hexdigest()
        entry["size_in_bytes"] = len(modified)
        with self.assertRaises(Blocked) as error:
            self.check("thamani")
        self.assertEqual(error.exception.code, "STATIC_BUDGET_RESULT_INVALID")

    def test_unverified_artifact_digest_is_blocked(self):
        base = "/repos/baobab-platform/nabhold/actions/runs/1001/artifacts?per_page=100"
        self.gh.urls[base]["artifacts"][0]["digest"] = "sha256:" + "0" * 64
        with self.assertRaises(Blocked) as error:
            self.check("nabhold")
        self.assertEqual(error.exception.code, "ARTIFACT_DIGEST_MISMATCH")

    def test_archive_path_traversal_denied(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as f:
            f.writestr("../token.txt", "secret")
        blob = out.getvalue()
        with self.assertRaises(Blocked) as error:
            verify_zip(blob, "sha256:" + hashlib.sha256(blob).hexdigest(), "nabhold")
        self.assertEqual(error.exception.code, "ARTIFACT_ARCHIVE_INVALID")

    def test_missing_runtime_teardown_blocks_l4_http(self):
        base = "/repos/baobab-platform/infrastructure/actions/runs/1008/artifacts?per_page=100"
        entry = self.gh.urls[base]["artifacts"][0]
        original = self.gh.blobs[("baobab-platform/infrastructure", 8)]
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            doc = json.loads(archive.read("dev01-run/completed/receipt.json"))
        doc["teardown_verified"] = False
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("dev01-run/completed/receipt.json", json.dumps(doc))
        invalid = out.getvalue()
        self.gh.blobs[("baobab-platform/infrastructure", 8)] = invalid
        entry["digest"] = "sha256:" + hashlib.sha256(invalid).hexdigest()
        entry["size_in_bytes"] = len(invalid)
        with self.assertRaises(Blocked) as error:
            self.check("l4_bff_trade")
        self.assertEqual(error.exception.code, "BFF_NATIVE_RECEIPT_INVALID")

    def test_full_http_and_estate_join_does_not_fake_l4_ops_completion(self):
        result = join(self.gh.bindings, PINS, self.gh.api, self.gh.download)
        self.assertTrue(result["join_http_and_estates_verified"])
        self.assertEqual(result["l4_ops_01"], "BLOCKED")
        self.assertEqual(
            result["l4_ops_01_reason"],
            "GOVERNED_MEDUSA_COMMITMENT_AND_CROSS_ENGINE_TRACE_NOT_PROVEN",
        )
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["protected_acceptance"])

    def test_independent_native_cp_jvm_engine_local_evidence_cannot_grant_l4(self):
        observed = self.check("l4_erp_native")
        self.assertEqual(observed["real_hydra_cp_broker_native_idempiere"], "PASS")
        self.assertEqual(observed["real_medusa_buyer_commitment"], "NOT_PROVEN")
        result = join(self.gh.bindings, PINS, self.gh.api, self.gh.download)
        self.assertTrue(result["native_idempiere_engine_local_verified"])
        self.assertEqual(result["l4_ops_01"], "BLOCKED")

    def test_stale_cp_or_iam_source_rejects_past_engine_native_success(self):
        for source, number in (("baobab-cp", 458), ("baobab-iam", 153)):
            with self.subTest(source=source):
                path = f"/repos/baobab-platform/{source}/pulls/{number}"
                original = self.gh.urls[path]["head"]["sha"]
                self.gh.urls[path]["head"]["sha"] = "0" * 40
                try:
                    with self.assertRaises(Blocked) as reason:
                        self.check("l4_erp_native")
                    self.assertEqual(reason.exception.code, "RUN_STALE_HEAD")
                finally:
                    self.gh.urls[path]["head"]["sha"] = original

    def test_fake_native_order_or_missing_cp_jvm_lineage_does_not_join(self):
        key = ("baobab-platform/baobab-erp", 7)
        old = self.gh.blobs[key]
        with zipfile.ZipFile(io.BytesIO(old)) as archive:
            all_rows = {name: archive.read(name) for name in archive.namelist()}
        lineage = json.loads(all_rows["dev11-cp-jvm-lineage.json"])
        lineage["native_cp_lineage_qualified"] = False
        all_rows["dev11-cp-jvm-lineage.json"] = json.dumps(lineage).encode()
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            for path, body in all_rows.items():
                archive.writestr(path, body)
        blob = out.getvalue()
        self.gh.blobs[key] = blob
        artifact = self.gh.urls[
            "/repos/baobab-platform/baobab-erp/actions/runs/1007/artifacts?per_page=100"
        ]["artifacts"][0]
        artifact["digest"] = "sha256:" + hashlib.sha256(blob).hexdigest()
        artifact["size_in_bytes"] = len(blob)
        with self.assertRaises(Blocked) as error:
            self.check("l4_erp_native")
        self.assertEqual(error.exception.code, "ERP_NATIVE_CONNECTED_RECEIPT_INVALID")

    def test_real_exporter_component_does_not_prove_native_business_effect(self):
        record = self.check("l4_exporter")
        self.assertEqual(record["actual_otlp_exporter_and_query"], "PASS")
        self.assertEqual(record["native_authority_or_effect"], "NOT_PROVEN")

    def test_signed_rabbit_erp_inbox_and_three_exported_services_join(self):
        record = self.check("l4_rabbit")
        self.assertEqual(record["independently_exported_component_spans"], "PASS")
        self.assertEqual(record["native_idempiere_business_effect"], "NOT_PROVEN")

    def test_rabbit_workflow_stale_erp_companion_head_denied(self):
        pr = "/repos/baobab-platform/baobab-erp/pulls/125"
        self.gh.urls[pr]["head"]["sha"] = "0" * 40
        with self.assertRaises(Blocked) as error:
            self.check("l4_rabbit")
        self.assertEqual(error.exception.code, "RUN_STALE_HEAD")

    def test_false_broker_ack_report_cannot_be_admitted(self):
        key = ("baobab-platform/baobab-trade", 5)
        original = self.gh.blobs[key]
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            rows = {name: archive.read(name) for name in archive.namelist()}
        report = json.loads(rows["connected.json"])
        report["real_rabbitmq_publisher_confirmed"] = False
        rows["connected.json"] = json.dumps(report).encode()
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            for path, body in rows.items():
                archive.writestr(path, body)
        blob = out.getvalue()
        self.gh.blobs[key] = blob
        art = self.gh.urls[
            "/repos/baobab-platform/baobab-trade/actions/runs/1005/artifacts?per_page=100"
        ]["artifacts"][0]
        art["digest"] = "sha256:" + hashlib.sha256(blob).hexdigest()
        art["size_in_bytes"] = len(blob)
        with self.assertRaises(Blocked) as error:
            self.check("l4_rabbit")
        self.assertEqual(error.exception.code, "RABBIT_CONNECTED_RECEIPT_INVALID")

    def test_missing_one_owner_is_explicit_blocker(self):
        del self.gh.bindings["thamani"]
        result = join(self.gh.bindings, PINS, self.gh.api, self.gh.download)
        self.assertFalse(result["join_http_and_estates_verified"])
        self.assertEqual(result["sources"]["thamani"]["reason"], "MISSING_RUN_PIN")
        self.assertEqual(result["l4_ops_01"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
