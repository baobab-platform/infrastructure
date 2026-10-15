#!/usr/bin/env python3
"""INT-02 real IAM -> CP integration profile; no protected credentials.

Executes the same CLI on Codespaces and Actions. All source repositories are
materialised only at full, audited Git commits; both application images are
built from those commits. No simulated issuer, shadow Control Plane,
production IAM credentials, public ports or blanket skip is permitted.

This runner records actual results, never predeclares unobserved acceptance.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
LOCK = BASE / "lock.json"
COMPOSE = BASE / "compose.yaml"
STATE = ROOT / "tests/platform-integration/.runtime"
SESSION = STATE / "int02-session.json"
EVIDENCE = ROOT / "tests/platform-integration/evidence"
REQUIRED = {"L4-IAM-01", "L4-IAM-02", "L4-CP-01", "L4-CP-02", "L4-CP-03"}
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
IMAGE = re.compile(r"^[a-z0-9][a-z0-9./_-]*@sha256:[0-9a-f]{64}$")

class Blocked(Exception):
    pass

def must(ok, reason):
    if not ok:
        raise Blocked(reason)

def load():
    data = json.loads(LOCK.read_text())
    must(data.get("profile") == "iam-cp" and data.get("authority") ==
         ["ADR-SHARED-036", "EA-v2.2"], "Unexpected normative authority")
    must(data.get("evidence_class") == "REAL_COMPONENT_SYNTHETIC_DATA" and
         data.get("synthetic_fixture") is True and
         data.get("no_protected_credentials") is True and
         data.get("no_production_tenant_data") is True,
         "Invalid real-process/synthetic-data boundary")
    must(set(data.get("mandatory", [])) == REQUIRED, "Missing mandatory scenario")
    must(all(SHA40.fullmatch(v) for v in data["sources"].values()),
         "Floating source ref is prohibited")
    must(all(data["sources"].get(x) for x in ("baobab-iam", "baobab-cp", "shared", "infrastructure")),
         "Missing source pin")
    must(set(data["services"]) == {"keycloak", "iam-db", "cp", "cp-db", "probe"},
         "Unexpected services")
    must(data["requirements"]["public_ports"] == 0 and
         not re.search(r"(?m)^\s+ports\s*:", COMPOSE.read_text()), "Host ports forbidden")
    must(IMAGE.fullmatch(data["runtime_images"]["postgres"]) is not None,
         "Postgres must be digest pinned")
    return data

def execute(args, capture=False, input_text=None, env=None, timeout=300):
    # Failure output can contain credentials. Never relay raw stderr to CI.
    p = subprocess.run(args, input=input_text, text=True, capture_output=True,
                       env=env, timeout=timeout, check=False)
    if p.returncode:
        # IAM's product bootstrap can create dozens of clients/scopes and may
        # fail long after successful readiness. Emit ONLY a filtered operation
        # label, never raw stderr, HTTP responses, token material or secrets.
        checkpoint = ""
        if args[-1] == "/opt/keycloak/bootstrap.sh":
            for line in p.stdout.splitlines():
                label = line.strip()
                if re.fullmatch(r"(Creating realm 'baobab'\.\.\.|"
                                r"Creating client scope '[A-Za-z0-9:._-]+' \.\.\.|"
                                r"Creating workload client '[A-Za-z0-9._-]+' \.\.\.|"
                                r"Importing client '[A-Za-z0-9._-]+' \.\.\.|"
                                r"Creating client role '[A-Za-z0-9:._/-]+' \.\.\.|"
                                r"Bootstrap completed\.)", label):
                    checkpoint = label
        # Export only a tightly allowlisted bootstrap failure class; never
        # print kcadm stderr (which can include server replies, bearer
        # material, URLs or command arguments). A missing progress checkpoint
        # means admin login itself was the last attempted bootstrap stage.
        stage = ""
        if args[-1] == "/opt/keycloak/bootstrap.sh":
            if "Keycloak admin login did not succeed within 5 minutes" in p.stderr:
                stage = "ADMIN_LOGIN_UNAVAILABLE"
            elif "Failed to create config file" in p.stderr:
                stage = "KCADM_SESSION_UNWRITABLE"
            elif not checkpoint:
                stage = "BEFORE_REALM_CREATION"
            else:
                stage = "AFTER_REALM_CREATION"
        # The fixture shell also emits only a fixed, pre-approved stage
        # marker on failure. Do not propagate any other fixture stdout.
        fixture_stage = ""
        if args[-2:] == ["/bin/bash", "-se"]:
            approved = {"admin-login", "admin-client-lookup", "admin-client-create",
                        "audience-client-lookup", "audience-client-create",
                        "human-user-lookup", "human-user-create",
                        "human-password-set", "human-role-add"}
            for line in p.stdout.splitlines():
                marker = re.fullmatch(r"INT02_FIXTURE_FAILURE_STAGE=([a-z-]+)", line)
                if marker and marker.group(1) in approved:
                    fixture_stage = marker.group(1)
        fixture_http = ""
        if args[-2:] == ["/bin/bash", "-se"]:
            for line in p.stdout.splitlines():
                marker = re.fullmatch(
                    r"INT02_FIXTURE_HTTP_CLASS=(HTTP_400|HTTP_401|HTTP_403|HTTP_409|HTTP_500|OTHER)",
                    line)
                if marker:
                    fixture_http = marker.group(1)
        raise Blocked("External command failed: " + Path(args[0]).name +
                      (f"; INT-02 fixture HTTP class: {fixture_http}" if fixture_http else "") +
                      (f"; INT-02 fixture class: {fixture_stage}" if fixture_stage else "") +
                      (f"; IAM bootstrap class: {stage}" if stage else "") +
                      (f"; last safe IAM bootstrap checkpoint: {checkpoint}" if checkpoint else "") +
                      " (raw output suppressed)")
    return p.stdout if capture else ""

def private(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(handle, "w") as out:
        out.write(value)

def current():
    must(SESSION.is_file(), "INT-02 has no session; run materialise")
    p = json.loads(SESSION.read_text())
    must(re.fullmatch(r"l4-[0-9a-f]{16}", p.get("project", "")) is not None,
         "Unrecognised project")
    directory = Path(p["directory"])
    must(directory.is_dir() and directory.resolve().is_relative_to(STATE.resolve()),
         "Untrusted runtime directory")
    envfile = directory / "runtime.env"
    must(envfile.is_file() and envfile.stat().st_mode & 0o077 == 0,
         "Private runtime environment unavailable")
    return p, directory, envfile

def compose(p, envfile, *args, capture=False, stdin=None, timeout=600):
    base = ["docker", "compose", "--env-file", str(envfile), "-f",
            str(COMPOSE), "-p", p["project"]]
    try:
        return execute([*base, *args], capture=capture,
                       input_text=stdin, timeout=timeout)
    except Blocked as cause:
        # Docker stderr may contain connection URLs or fixture credentials;
        # never release it into Actions. Compose ps is a structured status
        # interface: allowlist only service, state and health, never commands,
        # mount paths, environment or raw log messages. Keep this available
        # even when initial startup or the issuer bootstrap fails.
        snapshot = []
        try:
            raw = subprocess.run([*base, "ps", "--all", "--format", "json"],
                                 capture_output=True, text=True, timeout=15)
            if raw.returncode == 0:
                rows = [json.loads(line) for line in raw.stdout.splitlines() if line.strip()]
                for entry in rows:
                    service = entry.get("Service", "")
                    if service in {"iam-db", "cp-db", "keycloak", "cp-migrate", "cp", "probe"}:
                        snapshot.append(f"{service}={entry.get('State','unknown')}/{entry.get('Health','none')}")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        stage = args[0] if args and args[0] in {"up", "build", "wait", "exec", "config", "down"} else "unknown"
        target = (args[2] if len(args)>2 and args[0]=="exec" and args[1]=="-T"
                  and args[2] in {"keycloak","probe","cp-db"} else "service")
        # Only forward our own allowlisted class/checkpoint strings from
        # execute(), never the underlying command output or raw credentials.
        safe_cause = str(cause) if any(
            marker in str(cause) for marker in
            ("IAM bootstrap class:", "INT-02 fixture class:",
             "INT-02 fixture HTTP class:")) else ""
        raise Blocked(f"Compose {stage}/{target} failed; service states: "
                      + (", ".join(sorted(snapshot)) if snapshot else "unavailable")
                      + (f"; {safe_cause}" if safe_cause else "")) from cause

def check_prerequisites(lock, static=False):
    must((BASE / "cp.Dockerfile").is_file() and (BASE / "probe.py").is_file(),
         "INT-02 source incomplete")
    if static:
        return
    must(IMAGE.fullmatch(lock["runtime_images"]["python_probe"]) is not None,
         "Probe OCI digest not reviewed")
    must(shutil.which("git") is not None and shutil.which("docker") is not None,
         "Git and Docker required")
    must((os.cpu_count() or 0) >= lock["requirements"]["min_cpus"],
         "Insufficient CPU capacity")
    if sys.platform == "linux":
        mem = next(int(x.split()[1]) for x in Path("/proc/meminfo").read_text().splitlines()
                   if x.startswith("MemTotal:"))
        must(mem >= lock["requirements"]["min_ram_gib"] * 1024 * 1024,
             "Insufficient memory for IAM and CP")
    execute(["docker", "compose", "version"], capture=True, timeout=20)
    execute(["docker", "info"], capture=True, timeout=20)

def materialise(lock):
    check_prerequisites(lock)
    must(not SESSION.exists(), "Existing INT-02 session; run down")
    project = "l4-" + secrets.token_hex(8)
    directory = STATE / ("int02-" + project)
    directory.mkdir(mode=0o700, parents=True)
    # Always allowlist exact GitHub org paths; no redirects or arbitrary URL.
    try:
        for name in ("baobab-iam", "baobab-cp"):
            dest = directory / name
            execute(["git", "clone", "--quiet", "--no-checkout", "--",
                     "https://github.com/baobab-platform/" + name + ".git",
                     str(dest)], timeout=300)
            execute(["git", "-C", str(dest), "checkout", "--quiet", "--detach",
                     lock["sources"][name]], timeout=60)
            sha = execute(["git", "-C", str(dest), "rev-parse", "HEAD"],
                          capture=True, timeout=15).strip()
            must(sha == lock["sources"][name], "Git source pin mismatch")
        runtime = {
            "L4_PROJECT": project, "L4_RUNTIME": str(directory),
            "L4_IAM_SOURCE": str(directory / "baobab-iam"),
            "L4_CP_SOURCE": str(directory / "baobab-cp"),
            "L4_CP_DOCKERFILE": str(BASE / "cp.Dockerfile"),
            "L4_PROBE_SOURCE": str(BASE),
            "L4_POSTGRES_IMAGE": lock["runtime_images"]["postgres"],
            "L4_PYTHON_IMAGE": lock["runtime_images"]["python_probe"],
            "L4_IAM_IMAGE": "l4-iam-" + project,
            "L4_CP_IMAGE": "l4-cp-" + project,
            "L4_IAM_DB_PASSWORD": secrets.token_hex(28),
            "L4_CP_DB_PASSWORD": secrets.token_hex(28),
            "L4_KC_ADMIN_PASSWORD": secrets.token_hex(28),
            "L4_WORKLOAD_SEED": secrets.token_hex(28),
            "L4_TEST_USER_PASSWORD": secrets.token_hex(28),
            "L4_TEST_ADMIN_CLIENT_SECRET": secrets.token_hex(28),
        }
        private(directory / "runtime.env",
                "".join(k + "=" + v + "\n" for k, v in runtime.items()))
        # Fixture clients are disposable IAM test records only. Their bounded
        # password grant is never added to the product IAM client inventory.
        admin_client = {
          "clientId":"l4-int02-admin", "enabled":True, "publicClient":False,
          "secret":runtime["L4_TEST_ADMIN_CLIENT_SECRET"],
          "serviceAccountsEnabled":False, "standardFlowEnabled":False,
          "directAccessGrantsEnabled":True, "implicitFlowEnabled":False,
          "protocol":"openid-connect", "defaultClientScopes":[
            "openid","actor-type-human","authority:self"
          ],"optionalClientScopes":[]
        }
        other_client = {
          "clientId":"l4-int02-other-audience","enabled":True,"publicClient":False,
          "secret":secrets.token_hex(32),
          "serviceAccountsEnabled":True,"standardFlowEnabled":False,
          "directAccessGrantsEnabled":False,"implicitFlowEnabled":False,
          "protocol":"openid-connect","defaultClientScopes":[
            "openid","actor-type-workload","intelligence:evidence:search"
          ],"optionalClientScopes":[]
        }
        private(directory / "test-client.json",json.dumps(admin_client)+"\n")
        private(directory / "other-client.json",json.dumps(other_client)+"\n")
        private(directory / "test-user.json",json.dumps({"username":"l4-int02-human",
          "enabled":True,"emailVerified":True,"firstName":"Synthetic",
          "lastName":"L4","email":"l4-int02@example.invalid"})+"\n")
        private(directory / "other-secret",other_client["secret"]+"\n")
        private(SESSION, json.dumps({"project": project, "directory": str(directory),
                "started": datetime.now(timezone.utc).isoformat()}) + "\n")
    except BaseException:
        if SESSION.exists():
            # Once session exists, let down retain its handles on failure.
            pass
        else:
            shutil.rmtree(directory, ignore_errors=True)
        raise
    print("INT-02 source materialised at audited IAM and CP commit IDs")

def up(lock):
    check_prerequisites(lock)
    p, directory, envfile = current()
    compose(p, envfile, "config", "--quiet", timeout=60)
    # Keycloak and CP may require significant build resources; never hide
    # build failure as a skip or replace the source binary with a mock.
    print("INT-02 build stage: Keycloak from pinned IAM source",flush=True)
    compose(p, envfile, "build", "keycloak", timeout=1800)
    print("INT-02 build stage: Control Plane + migrator from pinned source",flush=True)
    compose(p, envfile, "build", "cp-migrate", timeout=1800)
    print("INT-02 startup stage: disposable PostgreSQL databases and Keycloak",flush=True)
    print("INT-02 startup: Docker Compose private DB/IAM/probe services",flush=True)
    # The image-level Keycloak healthcheck was incorrectly implemented in
    # the IAM Dockerfile, and certain Compose versions make `--wait` fail
    # despite both databases healthy and Keycloak actually running. Start
    # processes, then rely on explicit real application-level checks below.
    compose(p, envfile, "up", "-d", "iam-db", "cp-db", "keycloak", "probe",
            timeout=180)
    # The database must be reachable from its own process, not just "up".
    for service, user in (("iam-db", "baobab_iam"), ("cp-db", "controlplane")):
        compose(p, envfile, "exec", "-T", service,
                "pg_isready", "-U", user, timeout=25)
    print("INT-02 startup: probing actual IAM management readiness",flush=True)
    # Probe the real Keycloak 26 management listener from inside the private
    # Compose network. No health commands or HTTP clients are needed in the
    # minimal Keycloak runtime image.
    compose(p, envfile, "exec", "-T", "probe", "python", "/app/probe.py",
            "wait-iam", timeout=190)
    # Diagnose a failed master-admin credential before the product bootstrap
    # enters its bounded five-minute login retry loop. This runs against the
    # real Keycloak master realm; token bytes stay inside the probe process.
    compose(p, envfile, "exec", "-T", "probe", "python", "/app/probe.py",
            "master-admin", timeout=35)
    # IAM's own product bootstrap, not a test-issued JWT signature.
    compose(p, envfile, "exec", "-T", "keycloak",
            "/opt/keycloak/bootstrap.sh", timeout=450)
    # A test-only Keycloak client/user is separately configured after product
    # config. Never turn on password grant on a committed production client.
    seed_keycloak(p, envfile)
    compose(p, envfile, "up", "-d", "cp-migrate", timeout=240)
    compose(p, envfile, "wait", "cp-migrate", timeout=360)
    compose(p, envfile, "up", "-d", "cp", "probe", timeout=180)
    compose(p, envfile, "exec", "-T", "probe", "python", "/app/probe.py",
            "wait", timeout=120)
    print("INT-02 genuine Keycloak issuer + CP binary started")

def seed_keycloak(p, envfile):
    # kcadm is the Keycloak project's own administration CLI, executes inside
    # the IAM image with a private session on tmpfs. No secrets in logs.
    script = (BASE / "keycloak-fixture.sh").read_text()
    compose(p, envfile, "exec", "-T", "keycloak",
            "/bin/bash", "-se", stdin=script, timeout=120)

def run_probe(p, envfile, mode):
    return compose(p, envfile, "exec", "-T", "probe", "python", "/app/probe.py",
                   mode, capture=True, timeout=180)

def seed_identities(p, envfile, ids):
    # CP migrations are authoritative. This is the explicit synthetic-only
    # fixture boundary: identity registration admin APIs are not available;
    # never replicate this method in production or staging.
    for name in ("workload", "human"):
        subject = ids[name + "_sub"]
        must(re.fullmatch("[0-9a-f-]{36}", subject) is not None,
             "Keycloak principal subject invalid")
        canonical = secrets.token_hex(16)
        import uuid
        identity = str(uuid.UUID(canonical))
        stmt = ("INSERT INTO identity.principal(principal_id,actor_type,status) "
                "VALUES ('" + identity + "','" + name + "','ACTIVE'); "
                "INSERT INTO identity.external_identity(principal_id,issuer,subject,status) "
                "VALUES ('" + identity + "','http://keycloak:8080/realms/baobab','"
                + subject + "','ACTIVE');")
        compose(p, envfile, "exec", "-T", "cp-db", "psql", "-X", "-v",
                "ON_ERROR_STOP=1", "-U", "controlplane", "-d", "controlplane",
                "-c", stmt, capture=True, timeout=25)

def seed_tenants(p, directory, envfile):
    # All objects remain explicitly SYNTHETIC and private to the disposable
    # PostgreSQL test database; no external registry, legal or onboarding
    # assertion is made by their presence. PRIMARY Organisation mappings
    # are real CP schema objects, not fabricated JSON claims.
    import uuid
    tenant_a, tenant_b = ("tn_l4" + secrets.token_hex(8) for _ in range(2))
    org_a, org_b = (str(uuid.uuid4()) for _ in range(2))
    for tenant, org, legal in ((tenant_a,org_a,"LE-L4-A"),
                                (tenant_b,org_b,"LE-L4-B")):
        statement = f"""
        BEGIN;
        INSERT INTO legal_entities(legal_entity_id) VALUES ('{legal}');
        INSERT INTO registry.canonical_entity
            (canonical_entity_id,tenant_id,entity_type,status)
            VALUES ('{org}','{tenant}','ORGANISATION','active');
        INSERT INTO registry.organisation_profile
            (canonical_entity_id,display_name,source_authority,status,effective_from)
            VALUES ('{org}','Disposable INT-02 fixture','l4-synthetic','ACTIVE',
                    now() - interval '1 hour');
        INSERT INTO registry.legal_entity_profile
            (legal_entity_id,organisation_id,legal_name,source_authority,
             effective_from,legal_status)
            VALUES ('{legal}','{org}','Synthetic fixture','l4-synthetic',
                    now() - interval '1 hour','ACTIVE');
        INSERT INTO tenants (tenant_id,legal_entity_id,display_name,
            isolation_strategy,residency_region,observed_state,
            primary_organisation_enforced)
            VALUES ('{tenant}','{legal}','INT-02 disposable test',
            'row_level_security','af-south-1','active',true);
        INSERT INTO registry.tenant_organisation_mapping
            (tenant_id,organisation_id,mapping_role,status,effective_from,provenance)
            VALUES ('{tenant}','{org}','PRIMARY_ORGANISATION','ACTIVE',
                    now() - interval '1 hour','int02-synthetic-fixture');
        INSERT INTO registry.tenant_legal_entity_mapping
            (tenant_id,legal_entity_id,mapping_role,status,effective_from,provenance)
            VALUES ('{tenant}','{legal}','DEFAULT','ACTIVE',
                    now() - interval '1 hour','int02-synthetic-fixture');
        COMMIT;
        """
        compose(p, envfile, "exec", "-T", "cp-db", "psql", "-X", "-v",
            "ON_ERROR_STOP=1", "-U", "controlplane", "-d", "controlplane",
            "-c", statement, capture=True, timeout=35)
    # A capability binding is NOT its own grant. One ACTIVE scoped grant is
    # intentionally given to A only, so sibling B receives a real CP denial.
    # This synthetic provider is a resolution fixture, not a published or
    # executable Baobab Pulse implementation and never satisfies INT-08.
    statement = f"""
    WITH c AS (
      INSERT INTO capability.capability(code,name,status,maturity)
      VALUES ('intelligence.evidence.search','INT-02 resolver fixture','ACTIVE','SUPPORTED')
      RETURNING capability_id
    ), e AS (
      INSERT INTO topology.engine(code,name)
      VALUES ('baobab-pulse','INT-02 synthetic pulse provider')
      RETURNING engine_id
    ), i AS (
      INSERT INTO topology.engine_instance(engine_id,region,environment,status)
      SELECT engine_id,'af-south-1','integration','ACTIVE' FROM e
      RETURNING engine_instance_id
    ), p AS (
      INSERT INTO capability.capability_provider
      (provider_key,name,provider_type,engine_id,status,
       service_reference,invocation_protocol)
      SELECT 'int02.synthetic-pulse','INT-02 provider-resolution only',
             'BAOBAB_ENGINE',engine_id,'ACTIVE',
             'service://baobab-pulse/evidence','http' FROM e
      RETURNING provider_id
    ), s AS (
      INSERT INTO capability.capability_scope(tenant_id)
      VALUES ('{tenant_a}') RETURNING scope_id
    ), b AS (
      INSERT INTO capability.capability_binding
      (capability_id,engine_instance_id,scope_id,
       binding_mode,status,contract_version,effective_from,provider_id)
      SELECT c.capability_id,i.engine_instance_id,s.scope_id,
             'PRIMARY','ACTIVE','1',now()-interval '1 hour',p.provider_id
      FROM c,i,s,p RETURNING id
    )
    INSERT INTO capability.capability_grant
      (tenant_id,capability_id,scope_id,source,status,effective_from)
    SELECT '{tenant_a}',c.capability_id,s.scope_id,
           'PLATFORM_BASELINE','ACTIVE',now()-interval '1 hour'
    FROM c,s;
    """
    compose(p, envfile, "exec", "-T", "cp-db", "psql", "-X", "-v",
            "ON_ERROR_STOP=1", "-U", "controlplane", "-d", "controlplane",
            "-c", statement, capture=True, timeout=30)
    private(directory / "fixtures.json",json.dumps({
        "tenant":tenant_a,"other_tenant":tenant_b,"organisation":org_a})+"\n")

def test(lock):
    check_prerequisites(lock)
    p, directory, envfile = current()
    ids = json.loads(run_probe(p, envfile, "identities"))
    must(ids.get("source") == "keycloak-issued" and
         ids.get("issuer") == "http://keycloak:8080/realms/baobab",
         "IAM evidence is not real issuer issued")
    seed_identities(p, envfile, ids)
    seed_tenants(p, directory, envfile)
    report = json.loads(run_probe(p, envfile, "test"))
    # An already-issued IAM token must lose CP authority when its canonical
    # (issuer,subject) link is revoked. Keycloak continues to verify that
    # JWT cryptographically; CP is responsible for enforcing current mapping.
    # This UPDATE is an *explicit synthetic-fixture operation* in a private
    # throwaway integration DB, not a production identity lifecycle API.
    subject = ids["workload_sub"]
    must(re.fullmatch(r"[0-9a-f-]{36}", subject) is not None,
         "Invalid workload subject for revocation")
    revoked = ("""
      UPDATE identity.external_identity SET status='REVOKED'
      WHERE issuer='http://keycloak:8080/realms/baobab'
      AND subject='""" + subject + """' AND status='ACTIVE'
      RETURNING external_identity_id;
    """)
    result = compose(p, envfile, "exec", "-T", "cp-db", "psql", "-X",
                     "-At", "-v", "ON_ERROR_STOP=1", "-U", "controlplane",
                     "-d", "controlplane", "-c", revoked, capture=True, timeout=35)
    must(result.strip() != "", "Expected canonical external identity not revoked")
    after = json.loads(run_probe(p, envfile, "revoked"))
    cases = report.get("scenarios", {})
    if cases.get("L4-CP-03") == "BLOCKED":
        cases["L4-CP-03"] = ("PASS" if after.get("revocation_denied") is True
                              else "FAIL")
    required = set(lock["mandatory"])
    must(set(cases) == required, "Mandatory IAM/CP scenarios missing")
    if any(cases[x] != "PASS" for x in required):
        # Preserve the sanitized report for triage, NEVER promote to PASS.
        write_evidence(p, lock, report, accepted=False)
        raise Blocked("Real IAM/CP scenario denied or unavailable; see scrubbed evidence")
    write_evidence(p, lock, report, accepted=True)
    print("INT-02 actual IAM↔CP profile PASS; not protected staging")

def write_evidence(p, lock, report, accepted):
    EVIDENCE.mkdir(exist_ok=True)
    receipt = {"profile":"iam-cp","classification":lock["evidence_class"],
       "scenario_ids":lock["mandatory"],"scenarios":report["scenarios"],
       "source_pins":lock["sources"],"run_id":p["project"],
       # Source pins are dependency baselines; this is the ACTUAL checked
       # out integration harness revision, including GitHub's PR merge ref.
       "harness_candidate_sha":os.environ.get("GITHUB_SHA") or
           execute(["git","rev-parse","HEAD"],capture=True,timeout=15).strip(),
       "manifest_sha256":hashlib.sha256(LOCK.read_bytes()).hexdigest(),
       "component_integrity":{"iam":"REAL_KEYCLOAK_PINNED_SOURCE","cp":"REAL_CP_PINNED_SOURCE"},
       "tested_at":datetime.now(timezone.utc).isoformat(),
       "synthetic_only":True,"passed":accepted,
       "protected_staging_accepted":False,"production_authorized":False}
    (EVIDENCE / (p["project"] + "-int02.json")).write_text(json.dumps(
        receipt,sort_keys=True,indent=2)+"\n")

def down():
    if not SESSION.exists():
        print("No INT-02 project")
        return
    p,d,env=current()
    # Do NOT erase recovery credentials when Docker cleanup fails.
    compose(p,env,"down","--volumes","--remove-orphans",timeout=240)
    env.unlink()
    SESSION.unlink()
    shutil.rmtree(d)
    print("INT-02 IAM, CP, DBs, network and test credentials destroyed")

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["preflight","materialise","up","test","evidence","down"])
    parser.add_argument("profile",nargs="?",default="iam-cp",choices=["iam-cp"])
    parser.add_argument("--static",action="store_true")
    args=parser.parse_args(argv)
    try:
        if args.action=="down":
            down()
            return 0
        lock=load()
        if args.action=="preflight":
            check_prerequisites(lock,static=args.static)
            print("INT-02","static-only" if args.static else "runtime","preflight PASS")
        elif args.action=="materialise":
            materialise(lock)
        elif args.action=="up":
            up(lock)
        elif args.action=="test":
            test(lock)
        else:
            p,_,_=current()
            f=EVIDENCE/(p["project"]+"-int02.json")
            must(f.is_file(),"No actual INT-02 receipt")
            print(f.read_text())
        return 0
    except (Blocked, OSError, KeyError, TypeError, ValueError,
            subprocess.SubprocessError) as exc:
        print("INT-02 BLOCKED:",str(exc) if isinstance(exc,Blocked) else
              type(exc).__name__,file=sys.stderr)
        return 2

if __name__=="__main__":
    sys.exit(main())
