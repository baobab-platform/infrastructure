"""Governed real CP release/certification/activation for the private lab.

Human credentials come exclusively from the actual browser ceremony. The
release recorder, changeset requester and checker are different Principals.
Neither the Pulse caller nor the provider's validator receives admin scopes.
"""
from datetime import datetime, timedelta, timezone
import json
import uuid

import probe as p

REQUIRED = ("cp02_release_recorded", "cp02_self_certification_denied",
            "cp02_independent_certification", "cp02_release_approved",
            "cp02_provider_activated", "cp02_current_scoped_certification", "cp02_revoked_certification_unqualified")


def call(method, path, who, body=None, expected=200, headers=None):
    status, result, response_headers = p.request_with_headers(method, p.CP+path, body, p.human(who),
                                               headers=headers)
    if status != expected:
        code = result.get("code", "OTHER") if isinstance(result, dict) else "OTHER"
        p.diagnostic(step="provider_api", status=status,
                     code=code if isinstance(code, str) and p.REASON.fullmatch(code) else "OTHER")
        raise RuntimeError("governed provider API refused")
    return result, response_headers


def govern(desired, label):
    requester, checker = "parent", "subsidiary"
    changeset, headers = call("POST", "/v1/admin/changesets", requester,
        {"title":"INT-02 disposable "+label, "reason":"Synthetic source qualification only",
         "desired_change":desired}, 201, {"Idempotency-Key":"int02-"+str(uuid.uuid4())})
    endpoint = "/v1/admin/changesets/"+changeset["changeset_id"]
    submitted, _ = call("POST", endpoint+"/submit", requester, headers={"If-Match":next(v for k,v in headers.items() if k.lower()=="etag")})
    if submitted.get("blocking_reasons"):
        for blocker in submitted["blocking_reasons"][:10]:
            code = blocker.get("code", "OTHER")
            p.diagnostic(step="provider_plan", code=code if p.REASON.fullmatch(code) else "OTHER")
        raise RuntimeError("governed provider plan blocked")
    current, headers = call("GET", endpoint, requester)
    plan = current["current_plan"]
    call("POST", endpoint+"/approve", checker, {
        "plan_id":plan["plan_id"], "plan_version":plan["plan_version"],
        "plan_digest":plan["plan_digest"], "decision":"APPROVED"},
        headers={"If-Match":next(v for k,v in headers.items() if k.lower()=="etag")})
    _, headers = call("GET", endpoint, requester)
    call("POST", endpoint+"/apply", requester, expected=202,
        headers={"If-Match":next(v for k,v in headers.items() if k.lower()=="etag"),
                 "Idempotency-Key":"int02-apply-"+str(uuid.uuid4())})
    outcome, _ = call("GET", endpoint+"/outcome", requester)
    return outcome.get("final_state") == "COMPLETED" and outcome.get("verification_result", {}).get("status") == "PASSED"


def scoped_current(cert, source, release_id):
    until = cert.get("valid_until")
    return bool(cert.get("status") == "CERTIFIED" and cert.get("provider_id") == source["provider_id"] and
        cert.get("capability_key") == "intelligence.evidence.search" and cert.get("contract_version") == 1 and
        cert.get("release_id") == release_id and cert.get("qualification_profile") == "int02-synthetic" and
        until and datetime.fromisoformat(until.replace("Z", "+00:00")) > datetime.now(timezone.utc) and
        cert.get("evidence") == source["evidence"])


def prove():
    source = json.loads((p.RUNTIME / "provider-input.json").read_text())
    checks = dict.fromkeys(REQUIRED, False)
    release, _ = call("POST", "/v1/engine-releases", "human", source["release"], 201)
    release_id = release["release_id"]
    checks["cp02_release_recorded"] = (release.get("status") == "CANDIDATE" and
        all(release.get(k) == source["release"][k] for k in
            ("source_revision", "artifacts", "provider_support", "capability_provider_declaration_digest")))
    certification = {"provider_id":source["provider_id"], "capability_key":"intelligence.evidence.search",
        "contract_version":1, "release_id":release_id, "qualification_profile":"int02-synthetic",
        "evidence":source["evidence"],
        "valid_until":(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat(),
        "reason":"Actual native and caller-bound HTTP proof; synthetic disposable run only"}
    status, denied = p.request("POST", p.CP+"/v1/provider-capability-certifications", certification, p.human())
    checks["cp02_self_certification_denied"] = status == 403 and denied.get("code") == "CERTIFICATION_MAKER_CHECKER_REQUIRED"
    cert, _ = call("POST", "/v1/provider-capability-certifications", "subsidiary", certification, 201)
    checks["cp02_independent_certification"] = bool(cert.get("certified_by") and
        cert.get("certified_by") != release.get("recorded_by") and scoped_current(cert, source, release_id))
    checks["cp02_release_approved"] = govern({"kind":"ENGINE_RELEASE_APPROVAL", "release_id":release_id}, "release approval")
    approved, _ = call("GET", "/v1/engine-releases/"+release_id, "human")
    checks["cp02_release_approved"] &= approved.get("status") == "APPROVED"
    checks["cp02_provider_activated"] = govern({"kind":"PROVIDER_ACTIVATION", "provider_id":source["provider_id"]}, "provider activation")
    revoked, _ = call("POST", "/v1/provider-capability-certifications/"+cert["certification_id"]+"/revocations",
        "subsidiary", {"reason":"INT-02 deliberate qualification revocation differential"})
    checks["cp02_revoked_certification_unqualified"] = revoked.get("status") == "REVOKED" and not scoped_current(revoked, source, release_id)
    cert, _ = call("POST", "/v1/provider-capability-certifications", "subsidiary", certification, 201)
    current, _ = call("GET", "/v1/provider-capability-certifications/"+cert["certification_id"], "human")
    checks["cp02_current_scoped_certification"] = scoped_current(current, source, release_id)
    print(json.dumps({"checks":checks, "certification_id":cert["certification_id"], "release_id":release_id}))


def current_proof():
    source = json.loads((p.RUNTIME / "provider-input.json").read_text())
    identifiers = json.loads((p.RUNTIME / "provider-current.json").read_text())
    cert, _ = call("GET", "/v1/provider-capability-certifications/"+identifiers["certification_id"], "human")
    release, _ = call("GET", "/v1/engine-releases/"+identifiers["release_id"], "human")
    print(json.dumps({"current":scoped_current(cert, source, identifiers["release_id"]) and release.get("status")=="APPROVED"}))
