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
    "baobab-trade": TRADE, "nabhold": "e" * 40,
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
            archive.writestr("playwright-report/index.html", "synthetic test display")
            archive.writestr("test-results/.last-run.json", '{"status":"passed"}')
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
            sha = HEAD if name.startswith("l4_") else PINS[name]
            self.bindings[name] = {"run_id": run_id, "sha": sha}
            base = f"/repos/baobab-platform/{item['repo']}/actions/runs/{run_id}"
            blob = artifact_data(name)
            self.blobs[("baobab-platform/" + item["repo"], index)] = blob
            self.urls[base] = {
                "id": run_id, "head_sha": sha, "path": item["workflow"],
                "status": "completed", "conclusion": "success", "event": "pull_request",
                "repository": {"full_name": "baobab-platform/" + item["repo"]},
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

    def test_forged_source_cannot_join(self):
        self.gh.urls["/repos/baobab-platform/nabhold/actions/runs/1001"]["head_sha"] = "0" * 40
        with self.assertRaises(Blocked) as error:
            self.check("nabhold")
        self.assertEqual(error.exception.code, "RUN_SOURCE_MISMATCH")

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
        base = "/repos/baobab-platform/infrastructure/actions/runs/1005/artifacts?per_page=100"
        entry = self.gh.urls[base]["artifacts"][0]
        original = self.gh.blobs[("baobab-platform/infrastructure", 5)]
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            doc = json.loads(archive.read("dev01-run/completed/receipt.json"))
        doc["teardown_verified"] = False
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("dev01-run/completed/receipt.json", json.dumps(doc))
        invalid = out.getvalue()
        self.gh.blobs[("baobab-platform/infrastructure", 5)] = invalid
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
            "NATIVE_OTLP_GRAPH_AND_BROKER_CONSUMER_NOT_QUALIFIED",
        )
        self.assertFalse(result["production_authorized"])
        self.assertFalse(result["protected_acceptance"])

    def test_missing_one_owner_is_explicit_blocker(self):
        del self.gh.bindings["thamani"]
        result = join(self.gh.bindings, PINS, self.gh.api, self.gh.download)
        self.assertFalse(result["join_http_and_estates_verified"])
        self.assertEqual(result["sources"]["thamani"]["reason"], "MISSING_RUN_PIN")
        self.assertEqual(result["l4_ops_01"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
