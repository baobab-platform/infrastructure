"""Disposable topology fixtures and observed health around real CP governance.

Tenant grants/bindings and topology faults are synthetic, explicit fixtures.
Provider activation, release approval and certification use the owning HTTP
APIs exclusively. Health is recorded only after real HTTPS readiness/search.
STANDARD UNKNOWN remains CP-eligible; the qualification gate independently
requires a current HEALTHY observation and never rewrites that policy.
"""
import hashlib
import json
import os
import re
import uuid

API_REQUIRED = ("cp02_release_recorded", "cp02_self_certification_denied",
    "cp02_independent_certification", "cp02_release_approved",
    "cp02_provider_activated", "cp02_current_scoped_certification", "cp02_revoked_certification_unqualified")
REQUIRED = API_REQUIRED + ("cp02_actual_provider_resolution", "cp02_missing_grant_denied",
    "cp02_missing_binding_denied", "cp02_wrong_contract_denied", "cp02_wrong_market_denied",
    "cp02_wrong_instance_denied", "cp02_invalid_isolation_denied",
    "cp02_stale_health_unqualified", "cp02_outage_observed", "cp02_outage_resolution_denied",
    "cp02_recovery_positive", "cp02_current_health")


def prove(o, project, directory, envfile, report):
    checks = dict.fromkeys(REQUIRED, False)
    report.setdefault("checks", {}).update(checks)
    # Freeze only already-observed native/HTTP evidence, never future results.
    if not all(report["checks"].get(n) is True for n in o.PULSE_NATIVE_REQUIRED + o.PULSE_HTTP_REQUIRED):
        report["scenarios"]["L4-CP-02"] = "FAIL"
        return
    def sql(statement):
        return o.cp_sql(project, envfile, "provider_qualification", statement).strip()
    fixture = json.loads((directory/"fixtures.json").read_text())
    tenant = fixture["tenant"]
    o.must(re.fullmatch(r"tn_l4[0-9a-f]{16}", tenant) is not None, "Invalid provider fixture tenant")
    raw = sql("SELECT p.provider_id::text || '|' || p.canonical_provider_id || '|' || b.id::text || '|' || b.engine_instance_id::text FROM capability.capability_provider p CROSS JOIN capability.capability_binding b JOIN capability.capability_scope s ON s.scope_id=b.scope_id WHERE p.provider_key='baobab-pulse.core' AND s.tenant_id='"+tenant+"';")
    provider_uuid, provider_id, binding, instance = raw.split("|")
    for value in (provider_uuid, binding, instance):
        uuid.UUID(value)
    o.must(re.fullmatch(r"provider_[a-z0-9]+", provider_id) is not None, "Invalid canonical provider")
    # Separate binding scope from the grant so each negative isolates one fact.
    scope = str(uuid.uuid4())
    sql(f"INSERT INTO capability.capability_scope(scope_id,tenant_id) VALUES ('{scope}','{tenant}'); UPDATE capability.capability_binding SET provider_id='{provider_uuid}',scope_id='{scope}' WHERE id='{binding}';")
    frozen = {"classification":"REAL_COMPONENT_SYNTHETIC_DATA", "sources":project["sources"],
        "harness_sha":o.harness_sha(), "provider_key":"baobab-pulse.core", "contract_version":1,
        "native_and_http_checks":{n:report["checks"][n] for n in o.PULSE_NATIVE_REQUIRED+o.PULSE_HTTP_REQUIRED},
        "pulse_image_config_digest":o.image_id(envfile, "L4_PULSE_IMAGE"),
        "declaration_sha256":"sha256:"+hashlib.sha256((directory/"baobab-pulse/.baobab/capability-provider.yaml").read_bytes()).hexdigest(),
        "limits":"Local built image, deterministic reference embeddings; synthetic run only"}
    encoded = json.dumps(frozen, sort_keys=True, indent=2)+"\n"
    evidence_digest = "sha256:"+hashlib.sha256(encoded.encode()).hexdigest()
    o.EVIDENCE.mkdir(exist_ok=True)
    (o.EVIDENCE/(project["project"]+"-provider-proof.json")).write_text(encoded)
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    # devcontainer does not necessarily inherit Actions run metadata. The
    # orchestrator forwards the actual numeric run ID explicitly below.
    uri = ("https://github.com/baobab-platform/infrastructure/actions/runs/"+run_id if run_id.isdigit()
           else "https://github.com/baobab-platform/infrastructure/commit/"+o.harness_sha())
    image = frozen["pulse_image_config_digest"]
    o.must(re.fullmatch(r"sha256:[0-9a-f]{64}", image) is not None, "Actual Pulse image digest missing")
    source = {"provider_id":provider_id,
        "release":{"engine_id":"baobab-pulse", "release_version":"0.0.0-int02-"+project["project"],
            "source_revision":project["sources"]["baobab-pulse"],
            "artifacts":[{"artifact_type":"OCI_IMAGE", "repository":"local.int02.test/baobab-pulse", "digest":image}],
            "provider_support":[{"provider_key":"baobab-pulse.core", "capability_key":key, "contract_versions":[1]}
                for key in ("intelligence.evidence.search", "intelligence.research-mission.manage")],
            "capability_provider_declaration_digest":frozen["declaration_sha256"],
            "reason":"Disposable INT-02 local-image source qualification; no publication or production approval"},
        "evidence":[{"type":"INTEGRATION_TEST", "uri":uri, "digest":evidence_digest,
                     "description":"Frozen native and HTTP proof in this run's provider-proof artifact"}]}
    o.private(directory/"provider-input.json", json.dumps(source)+"\n")

    def health(status="HEALTHY", expired=False):
        # Each observation derives from this run's live readiness/search or
        # explicit stopped-provider fault. Never manufacture a healthy probe.
        stamp = "now()-interval '2 minutes'" if expired else "now()"
        expiry = "now()-interval '1 minute'" if expired else "now()+interval '5 minutes'"
        reasons = "ARRAY[]::text[]" if status == "HEALTHY" else "ARRAY['PROVIDER_UNAVAILABLE']"
        for columns, values, predicate in (
            ("engine_instance_id", f"'{instance}'::uuid", f"engine_instance_id='{instance}'"),
            ("provider_id", f"'{provider_uuid}'::uuid", f"provider_id='{provider_uuid}' AND capability_id IS NULL"),
            ("provider_id,capability_id", f"'{provider_uuid}'::uuid,(SELECT capability_id FROM capability.capability WHERE code='intelligence.evidence.search')", f"provider_id='{provider_uuid}' AND capability_id IS NOT NULL")):
            sql(f"DELETE FROM topology.health_observation WHERE {predicate}; INSERT INTO topology.health_observation({columns},status,observed_at,expires_at,source,reasons) VALUES ({values},'{status}',{stamp},{expiry},'ACTIVE_PROBE',{reasons});")

    def decide(name, decision, reason="", contract=1, neighbour=False, current=True):
        expectation = {"decision":decision,"reason":reason,"contract_version":contract,
            "current_resolution":current,"provider_id":provider_id,"instance_id":"ei_"+instance.replace("-", ""),"neighbour":neighbour}
        o.private(directory/"provider-expect.json",json.dumps(expectation)+"\n")
        result=json.loads(o.run_probe(project, envfile, "provider-resolution"))
        checks[name]=result.get("matched") is True
        # Retain only fixed CP vocabulary/status returned by the probe.
        report.setdefault("observations", {})[name+"_decision"]=result.get("decision", "OTHER")
        report["observations"][name+"_reason"]=result.get("reason", "OTHER")

    health()
    api = json.loads(o.run_probe(project, envfile, "provider-api"))
    checks.update({n:api.get("checks", {}).get(n) is True for n in API_REQUIRED})
    identifiers={key:api.get(key, "") for key in ("certification_id", "release_id")}
    o.must(re.fullmatch(r"cert_[0-9a-f]{32}", identifiers["certification_id"]) is not None and
           re.fullmatch(r"erl_[a-z0-9]+", identifiers["release_id"]) is not None, "Invalid CP qualification identifiers")
    o.private(directory/"provider-current.json",json.dumps(identifiers)+"\n")
    decide("cp02_actual_provider_resolution", "RESOLVED")
    decide("cp02_missing_grant_denied", "DENIED", "GRANT_NOT_FOUND", neighbour=True)
    sql(f"UPDATE capability.capability_binding SET status='SUSPENDED' WHERE id='{binding}';")
    try:
        decide("cp02_missing_binding_denied", "UNAVAILABLE", "BINDING_NOT_FOUND")
    finally:
        sql(f"UPDATE capability.capability_binding SET status='ACTIVE' WHERE id='{binding}';")
    decide("cp02_wrong_contract_denied", "INCOMPATIBLE", "CONTRACT_VERSION_UNSUPPORTED", contract=2)
    sql(f"UPDATE capability.capability_scope SET include_countries=ARRAY['UG'] WHERE scope_id='{scope}';")
    try:
        decide("cp02_wrong_market_denied", "UNAVAILABLE", "BINDING_NOT_FOUND")
    finally:
        sql(f"UPDATE capability.capability_scope SET include_countries=ARRAY[]::text[] WHERE scope_id='{scope}';")
    sql(f"UPDATE topology.engine_instance SET status='MAINTENANCE' WHERE engine_instance_id='{instance}';")
    try:
        decide("cp02_wrong_instance_denied", "UNAVAILABLE", "PROVIDER_UNAVAILABLE")
    finally:
        sql(f"UPDATE topology.engine_instance SET status='ACTIVE' WHERE engine_instance_id='{instance}';")
    isolation = str(uuid.uuid4())
    sql(f"INSERT INTO policy.isolation_profile(isolation_profile_id,name,strategy) VALUES ('{isolation}','int02-incompatible','schema_per_tenant'); UPDATE capability.capability_scope SET isolation_profile_id='{isolation}' WHERE scope_id='{scope}';")
    try:
        decide("cp02_invalid_isolation_denied", "UNAVAILABLE", "BINDING_NOT_FOUND")
    finally:
        sql(f"UPDATE capability.capability_scope SET isolation_profile_id=NULL WHERE scope_id='{scope}';")
    health(expired=True)
    # Shared deliberately permits UNKNOWN for STANDARD capabilities. Observe
    # that exact policy, while rejecting it as current qualification evidence.
    decide("cp02_stale_health_unqualified", "RESOLVED", current=False)
    stale = sql(f"SELECT count(*) FROM topology.health_observation WHERE (engine_instance_id='{instance}' OR provider_id='{provider_uuid}') AND expires_at>now();")
    checks["cp02_stale_health_unqualified"] &= stale == "0"
    o.compose(project, envfile, "stop", "pulse", timeout=60)
    try:
        outage=json.loads(o.run_probe(project, envfile, "provider-outage"))
        checks["cp02_outage_observed"]=outage.get("outage") is True
        if checks["cp02_outage_observed"]:
            health("UNAVAILABLE")
        decide("cp02_outage_resolution_denied", "UNAVAILABLE", "PROVIDER_UNAVAILABLE")
    finally:
        o.compose(project, envfile, "up", "-d", "pulse", timeout=120)
    readiness=json.loads(o.run_probe(project, envfile, "wait-pulse"))
    recovered=json.loads(o.run_probe(project, envfile, "pulse-http"))
    if readiness.get("pulse_native_https_readiness") is True and all(recovered.get("checks", {}).get(n) is True for n in o.PULSE_HTTP_REQUIRED):
        health()
        decide("cp02_recovery_positive", "RESOLVED")
        checks["cp02_current_health"]=sql(f"SELECT count(*) FROM topology.health_observation WHERE (engine_instance_id='{instance}' OR provider_id='{provider_uuid}') AND status='HEALTHY' AND observed_at<=now() AND expires_at>now();") == "3"
    current=json.loads(o.run_probe(project, envfile, "provider-current"))
    checks["cp02_current_scoped_certification"] &= current.get("current") is True
    report["checks"].update(checks)
    report["scenarios"]["L4-CP-02"]="PASS" if all(checks.values()) else "FAIL"
    report["provider_evidence_sha256"]=evidence_digest
