"""Live named-caller qualification through Pulse's normal IAM/CP adapters.

Only fixed booleans leave this process. The native fixture supplies real
PostgreSQL evidence and real Qdrant projections; no token or context is mocked.
This slice alone cannot promote CP-02 or stand in for provider certification.
"""
import json
import uuid

import probe as p

CLIENT = "baobab-int02-pulse-consumer"
PULSE = "https://pulse.int02.test"
REQUIRED = (
    "pulse_http_exact_issuer_scopes_audiences", "pulse_http_caller_context",
    "pulse_http_search_current_canonical", "pulse_http_restricted_denied",
    "pulse_http_wrong_owner_denied", "pulse_http_neighbour_no_leak",
    "pulse_http_wrong_audience_denied", "pulse_http_fabricated_context_denied",
    "pulse_http_wrong_credential_denied", "pulse_http_disabled_issuance_denied",
    "pulse_http_client_restored",
)


def prove():
    checks = dict.fromkeys(REQUIRED, False)
    observations = {}
    fixture = json.loads((p.RUNTIME / "fixtures.json").read_text())
    secret = (p.RUNTIME / "pulse-secret").read_text().strip()
    cp_token = p.token(CLIENT, secret, "client_credentials", scope="context:resolve")
    pulse_token = p.token(CLIENT, secret, "client_credentials", scope="intelligence:evidence:search")
    cp_claims, pulse_claims = p.decode(cp_token), p.decode(pulse_token)
    checks[REQUIRED[0]] = bool(
        all(c.get("iss") == p.ISSUER and c.get("azp") == CLIENT and
            c.get("actor_type") == "workload" and c.get("sub") for c in (cp_claims, pulse_claims)) and
        cp_claims["sub"] == pulse_claims["sub"] and
        p.audience_set(cp_claims) == {"baobab-control-plane"} and
        p.audience_set(pulse_claims) == {"baobab-pulse"} and
        set(cp_claims.get("scope", "").split()) == {"context:resolve"} and
        set(pulse_claims.get("scope", "").split()) == {"intelligence:evidence:search"})
    context_body = {"tenant_id":fixture["tenant"], "organisation_id":fixture["organisation"]}
    context = p.context_for(cp_token, context_body)
    checks["pulse_http_caller_context"] = bool(context)
    if not context:
        p.diagnostic(step="pulse_http_context", status="absent")
        print(json.dumps({"checks":checks, "observations":observations}))
        return

    validator = p.token("baobab-pulse-workload", p.os.environ["L4_WORKLOAD_SEED"], "client_credentials", scope="context:validate")
    validator_claims=p.decode(validator)
    p.diagnostic(step="pulse_validator", has_sub=str(bool(validator_claims.get("sub"))).lower(),
                 scope_ok=str("context:validate" in validator_claims.get("scope", "").split()).lower())
    validation_status, validation=p.request("POST", p.CP+"/v1/platform-context/validate",
        {"context_id":context, "subject_token":pulse_token}, validator)
    allowed_codes={"AUTH_TOKEN_INVALID", "CAPABILITY_AUTHORITY_UNAVAILABLE", "CAPABILITY_ACCESS_DENIED",
        "CONTEXT_NOT_FOUND", "PULSE_INTERNAL_ERROR", "TENANT_CONTEXT_MISSING", "CAPABILITY_RUNTIME_UNAVAILABLE",
        "SEMANTIC_RETRIEVAL_UNAVAILABLE", "CONTEXT_STORE_UNAVAILABLE", "AUTH_VERIFIER_UNAVAILABLE",
        "CONTEXT_VALIDATION_UNAVAILABLE", "SUBJECT_TOKEN_INVALID", "VALIDATION_FAILED", "NONE"}
    def code_of(result):
        value=result.get("code", "NONE")
        return value if value in allowed_codes else "OTHER"
    observations["pulse_direct_validation_status"]=validation_status
    observations["pulse_direct_validation_code"]=code_of(validation)

    def search(label, token=pulse_token, context_id=context, evidence=None):
        body = {"query_text":"INT-02 synthetic canonical evidence for provider conformance.", "top_k":10}
        if evidence:
            body["evidence_set_id"] = evidence
        status,result=p.request("POST", PULSE + "/evidence/search", body, token,
                         headers={"X-Baobab-Context-Id":context_id})
        observations["pulse_"+label+"_status"]=status
        observations["pulse_"+label+"_code"]=code_of(result)
        return status,result

    status, result = search("positive")
    candidates = result.get("candidates", [])
    checks["pulse_http_search_current_canonical"] = bool(status == 200 and len(candidates) == 1 and
        candidates[0].get("canonical_object_id") == "evd_int02_native" and
        candidates[0].get("evidence_set_id") == "evs_int02_native" and
        candidates[0].get("is_stale") is False)
    status, result = search("restricted", evidence="evs_int02_restricted")
    checks["pulse_http_restricted_denied"] = status == 200 and result.get("candidates") == []
    wrong_owner = p.context_for(p.workload(), context_body)
    status, result = search("wrong_owner", context_id=wrong_owner or str(uuid.uuid4()))
    checks["pulse_http_wrong_owner_denied"] = bool(wrong_owner and status == 404 and result.get("code") == "CONTEXT_NOT_FOUND")
    neighbour = p.context_for(cp_token, {"tenant_id":fixture["other_tenant"],
                                         "organisation_id":fixture["other_organisation"]})
    status, result = search("neighbour", context_id=neighbour or str(uuid.uuid4()))
    checks["pulse_http_neighbour_no_leak"] = bool(neighbour and status == 200 and result.get("candidates") == [])
    status, result = search("wrong_audience", token=cp_token)
    checks["pulse_http_wrong_audience_denied"] = status == 401 and result.get("code") == "AUTH_TOKEN_INVALID"
    status, result = search("fabricated_context", context_id=str(uuid.uuid4()))
    checks["pulse_http_fabricated_context_denied"] = status == 404 and result.get("code") == "CONTEXT_NOT_FOUND"
    status, result = p.request("POST", p.ISSUER+"/protocol/openid-connect/token", {
        "grant_type":"client_credentials", "client_id":CLIENT, "client_secret":secret+"invalid",
        "scope":"context:resolve"})
    observations["pulse_wrong_credential_status"]=status
    observations["pulse_wrong_credential_code"]=(result.get("error").upper() if result.get("error") in p.OAUTH_ERRORS else "OTHER")
    checks["pulse_http_wrong_credential_denied"] = status in (400,401) and result.get("error") == "invalid_client"
    master = p.ISSUER.rsplit("/realms/", 1)[0]+"/realms/master"
    status, auth = p.request("POST", master+"/protocol/openid-connect/token", {
        "grant_type":"password", "client_id":"admin-cli", "username":"l4admin",
        "password":p.os.environ["L4_KC_ADMIN_PASSWORD"]})
    if status != 200 or not auth.get("access_token"):
        raise RuntimeError("fixture administrator unavailable")
    admin = p.ISSUER.rsplit("/realms/", 1)[0]+"/admin/realms/baobab"
    status, clients = p.request("GET", admin+"/clients?clientId="+CLIENT, token=auth["access_token"])
    if status != 200 or len(clients) != 1 or clients[0].get("clientId") != CLIENT:
        raise RuntimeError("ambiguous fixture caller")
    client_id = str(uuid.UUID(clients[0]["id"]))
    endpoint = admin+"/clients/"+client_id
    try:
        status, _ = p.request("PUT", endpoint, {**clients[0], "enabled":False}, auth["access_token"])
        if status != 204:
            raise RuntimeError("fixture disable failed")
        status, result = p.request("POST", p.ISSUER+"/protocol/openid-connect/token", {
            "grant_type":"client_credentials", "client_id":CLIENT, "client_secret":secret,
            "scope":"context:resolve"})
        checks["pulse_http_disabled_issuance_denied"] = status in (400, 401) and result.get("error") in ("invalid_client", "unauthorized_client")
    finally:
        status, _ = p.request("PUT", endpoint, clients[0], auth["access_token"])
        if status != 204:
            raise RuntimeError("fixture restore failed")
    restored = p.token(CLIENT, secret, "client_credentials", scope="context:resolve")
    checks["pulse_http_client_restored"] = bool(p.context_for(restored, context_body))
    print(json.dumps({"checks":checks, "observations":observations}))
