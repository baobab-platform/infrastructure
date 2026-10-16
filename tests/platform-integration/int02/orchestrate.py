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
# EA v2.2 INT-02 runs "over verified local TLS": every hop that crosses the
# Compose network reaches IAM and CP through the TLS edge, under these names,
# with a certificate from a throwaway CA generated for this run only.
IAM_HOST = "iam.int02.test"
CP_HOST = "cp.int02.test"
ISSUER = "https://" + IAM_HOST + "/realms/baobab"
SERVICES = {"keycloak", "iam-db", "cp", "cp-db", "edge", "probe"}

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
    must(set(data["services"]) == SERVICES, "Unexpected services")
    must(data["requirements"]["public_ports"] == 0 and
         not re.search(r"(?m)^\s+ports\s*:", COMPOSE.read_text()), "Host ports forbidden")
    must(IMAGE.fullmatch(data["runtime_images"]["postgres"]) is not None and
         IMAGE.fullmatch(data["runtime_images"]["tls_edge"]) is not None,
         "Postgres and the TLS edge must be digest pinned")
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
        # Only the probe's fixed INT02_DIAG lines (key=token pairs, tokens of
        # at most 40 safe characters) leave this process.
        diags = [line[len("INT02_DIAG "):] for line in p.stderr.splitlines()
                 if re.fullmatch(r"INT02_DIAG( [a-z_]{1,24}=[A-Za-z0-9_.-]{1,40}){1,6}", line)]
        raise Blocked("External command failed: " + Path(args[0]).name +
                      (f"; IAM diagnostics: {' | '.join(diags[-3:])}" if diags else "") +
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
                    if service in SERVICES | {"cp-migrate"}:
                        snapshot.append(f"{service}={entry.get('State','unknown')}/{entry.get('Health','none')}")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            # Best-effort status only: the original Blocked error below is
            # what the run reports; a failed snapshot must never replace it
            # or surface Docker's raw output.
            pass
        stage = args[0] if args and args[0] in {"up", "build", "wait", "exec", "config", "down"} else "unknown"
        target = (args[2] if len(args)>2 and args[0]=="exec" and args[1]=="-T"
                  and args[2] in {"keycloak","probe","cp-db"} else "service")
        # Only forward our own allowlisted class/checkpoint strings from
        # execute(), never the underlying command output or raw credentials.
        safe_cause = str(cause) if any(
            marker in str(cause) for marker in
            ("IAM bootstrap class:", "INT-02 fixture class:",
             "INT-02 fixture HTTP class:", "IAM diagnostics:")) else ""
        raise Blocked(f"Compose {stage}/{target} failed; service states: "
                      + (", ".join(sorted(snapshot)) if snapshot else "unavailable")
                      + (f"; {safe_cause}" if safe_cause else "")) from cause

def check_prerequisites(lock, static=False):
    must((BASE / "cp.Dockerfile").is_file() and (BASE / "probe.py").is_file()
         and (BASE / "edge.conf").is_file(), "INT-02 source incomplete")
    if static:
        return
    must(IMAGE.fullmatch(lock["runtime_images"]["python_probe"]) is not None,
         "Probe OCI digest not reviewed")
    must(all(shutil.which(x) is not None for x in ("git", "docker", "openssl")),
         "Git, Docker and OpenSSL required")
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
            "L4_EDGE_IMAGE": lock["runtime_images"]["tls_edge"],
            "L4_EDGE_CONFIG": str(BASE / "edge.conf"),
            "L4_TLS": str(directory / "tls"),
            "L4_IAM_IMAGE": "l4-iam-" + project,
            "L4_CP_IMAGE": "l4-cp-" + project,
            "L4_IAM_DB_PASSWORD": secrets.token_hex(28),
            "L4_CP_DB_PASSWORD": secrets.token_hex(28),
            "L4_KC_ADMIN_PASSWORD": secrets.token_hex(28),
            "L4_WORKLOAD_SEED": secrets.token_hex(28),
            "L4_TEST_USER_PASSWORD": secrets.token_hex(28),
            "L4_TEST_ADMIN_CLIENT_SECRET": secrets.token_hex(28),
        }
        throwaway_tls(directory / "tls")
        private(directory / "runtime.env",
                "".join(k + "=" + v + "\n" for k, v in runtime.items()))
        # Fixture clients are disposable IAM test records only. Their bounded
        # password grant is never added to the product IAM client inventory.
        admin_client = {
          "clientId":"l4-int02-admin", "enabled":True, "publicClient":False,
          "secret":runtime["L4_TEST_ADMIN_CLIENT_SECRET"],
          "serviceAccountsEnabled":False, "standardFlowEnabled":False,
          "directAccessGrantsEnabled":True, "implicitFlowEnabled":False,
          # Keycloak 26 issues `sub` only through its built-in "basic" client
          # scope; an explicit scope list without it yields tokens CP cannot
          # map to a principal (observed live: has_sub=false).
          "protocol":"openid-connect", "defaultClientScopes":[
            "basic","openid","actor-type-human","authority:self"
          ],"optionalClientScopes":[]
        }
        other_client = {
          "clientId":"l4-int02-other-audience","enabled":True,"publicClient":False,
          "secret":secrets.token_hex(32),
          "serviceAccountsEnabled":True,"standardFlowEnabled":False,
          "directAccessGrantsEnabled":False,"implicitFlowEnabled":False,
          "protocol":"openid-connect","defaultClientScopes":[
            "basic","openid","actor-type-workload","intelligence:evidence:search"
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

def throwaway_tls(tls):
    """A CA and edge certificate that exist only for this run (one day).

    The tls directory is the only TLS state the edge and CP mount. The CA key
    is created outside it and destroyed as soon as the edge certificate is
    signed, so no container can ever read it and nothing else can be issued
    under this CA. The edge key is a disposable key for synthetic data only.
    """
    tls.mkdir(mode=0o755)
    ca_key, ca, key, csr, ext = (tls.parent / "ca.key", tls / "ca.pem", tls / "edge.key",
                                 tls.parent / "edge.csr", tls.parent / "edge.ext")
    execute(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
             "-subj", "/CN=Baobab INT-02 throwaway CA", "-addext",
             "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign",
             "-keyout", str(ca_key), "-out", str(ca)], timeout=60)
    execute(["openssl", "req", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=int02.test",
             "-keyout", str(key), "-out", str(csr)], timeout=60)
    ext.write_text(f"subjectAltName=DNS:{IAM_HOST},DNS:{CP_HOST}\n"
                   "extendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\n")
    execute(["openssl", "x509", "-req", "-in", str(csr), "-CA", str(ca), "-CAkey", str(ca_key),
             "-CAserial", str(tls.parent / "ca.srl"), "-CAcreateserial", "-days", "1",
             "-extfile", str(ext), "-out", str(tls / "edge.pem")], timeout=60)
    for leftover in (ca_key, csr, ext, tls.parent / "ca.srl"):
        leftover.unlink()
    # The edge (nginx, non-root workers) and CP (distroless nonroot) read these.
    for name in ("ca.pem", "edge.pem", "edge.key"):
        os.chmod(tls / name, 0o644)

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
    compose(p, envfile, "up", "-d", "iam-db", "cp-db", "keycloak", "edge", "probe",
            timeout=180)
    # The database must be reachable from its own process, not just "up".
    for service, user in (("iam-db", "baobab_iam"), ("cp-db", "controlplane")):
        compose(p, envfile, "exec", "-T", service,
                "pg_isready", "-U", user, timeout=25)
    print("INT-02 startup: probing actual IAM management readiness",flush=True)
    # Probe the real Keycloak 26 management listener from inside the private
    # Compose network. No health commands or HTTP clients are needed in the
    # minimal Keycloak runtime image.
    try:
        startup_with_iam(p, envfile)
    except Blocked as cause:
        # Any failure while IAM is involved also reports Keycloak's startup
        # log CLASSES (fixed codes only).
        raise Blocked(f"{cause}; Keycloak log classes: {keycloak_log_classes(p, envfile)}") from cause
    compose(p, envfile, "up", "-d", "cp-migrate", timeout=240)
    compose(p, envfile, "wait", "cp-migrate", timeout=360)
    compose(p, envfile, "up", "-d", "cp", "probe", timeout=180)
    compose(p, envfile, "exec", "-T", "probe", "python", "/app/probe.py",
            "wait", timeout=120)
    print("INT-02 genuine Keycloak issuer + CP binary started")

def startup_with_iam(p, envfile):
    compose(p, envfile, "exec", "-T", "probe", "python", "/app/probe.py",
            "wait-iam", timeout=190)
    print("INT-02 startup: IAM ready; verifying master administrator",flush=True)
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
    print("INT-02 startup: IAM product bootstrap complete; seeding synthetic fixtures",flush=True)
    seed_keycloak(p, envfile)

# Fixed Keycloak startup log markers, mapped to codes. Only the CODES leave
# this process: never a log line, URL, credential or JDBC message.
KEYCLOAK_LOG_CLASSES = (
    ("password authentication failed", "DB_AUTH_FAILED"),
    ("Connection refused", "DB_OR_PEER_REFUSED"),
    ("does not exist", "DB_OBJECT_MISSING"),
    ("Failed to start server", "SERVER_START_FAILED"),
    ("ERROR [org.keycloak.quarkus.runtime.cli.ExecutionExceptionHandler]", "CLI_EXECUTION_ERROR"),
    ("Listening on: http://", "HTTP_LISTENING"),
    ("Management interface listening on http://", "MANAGEMENT_LISTENING"),
    (" started in ", "SERVER_STARTED"),
    ("Created temporary admin user", "TEMP_ADMIN_CREATED"),
    ("error=user_not_found", "LOGIN_USER_NOT_FOUND"),
    ("error=invalid_user_credentials", "LOGIN_INVALID_USER_CREDENTIALS"),
    ("error=invalid_client_credentials", "LOGIN_INVALID_CLIENT_CREDENTIALS"),
    ("error=resolve_required_actions", "LOGIN_REQUIRED_ACTIONS"),
    ("error=not_allowed", "LOGIN_NOT_ALLOWED"),
)

def keycloak_log_classes(p, envfile):
    base = ["docker", "compose", "--env-file", str(envfile), "-f", str(COMPOSE), "-p", p["project"]]
    try:
        raw = subprocess.run([*base, "logs", "--no-color", "keycloak"], capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    found = [code for marker, code in KEYCLOAK_LOG_CLASSES if marker in raw.stdout + raw.stderr]
    return ",".join(found) if found else "none"

def seed_keycloak(p, envfile):
    # A Docker bind mount preserves HOST permissions, not the container's
    # UID. Our host fixture directory is rightly 0700 and files are 0600,
    # whereas the real Keycloak image runs as UID 1000; reading /run/l4
    # directly fails before any Keycloak HTTP request. Never relax the host
    # permissions or run IAM as root merely to satisfy a test harness.
    #
    # Stream these three synthetic-only JSON documents over Docker exec's
    # stdin (NOT command arguments or environment variables). Bash creates
    # them under its own UID with umask 077; keycloak-fixture.sh removes the
    # directory in its EXIT trap. execute() suppresses raw stdout/stderr.
    _, directory, _ = current()
    prelude = [
        "set -euo pipefail",
        "set +x",
        "umask 077",
        'L4_FIXTURE_DIR=$(mktemp -d)',
        'trap \'rm -rf -- "$L4_FIXTURE_DIR"\' EXIT',
    ]
    for name in ("test-client.json", "other-client.json", "test-user.json"):
        content = (directory / name).read_text()
        must(len(content) < 16384 and isinstance(json.loads(content), dict),
             "Untrusted or oversized Keycloak test fixture")
        delimiter = "INT02_" + secrets.token_hex(20)
        must(delimiter not in content, "Invalid fixture delimiter collision")
        prelude.append(f'cat > "$L4_FIXTURE_DIR/{name}" <<\'{delimiter}\'')
        prelude.append(content.rstrip("\n"))
        prelude.append(delimiter)
    script = "\n".join(prelude) + "\n" + (BASE / "keycloak-fixture.sh").read_text()
    compose(p, envfile, "exec", "-T", "keycloak",
            "/bin/bash", "-se", stdin=script, timeout=180)

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
                "VALUES ('" + identity + "','" + ISSUER + "','"
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
        "tenant":tenant_a,"other_tenant":tenant_b,"organisation":org_a,
        "other_organisation":org_b})+"\n")

def test(lock):
    check_prerequisites(lock)
    p, directory, envfile = current()
    ids = json.loads(run_probe(p, envfile, "identities"))
    must(ids.get("source") == "keycloak-issued" and
         ids.get("issuer") == ISSUER,
         "IAM evidence is not real issuer issued")
    # Tenants first: the unmapped-principal negative (L4-CP-01) needs a real
    # tenant and Organisation, and must run BEFORE the Keycloak subject is
    # linked to a CP Principal.
    seed_tenants(p, directory, envfile)
    unmapped = json.loads(run_probe(p, envfile, "unmapped"))
    seed_identities(p, envfile, ids)
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
      WHERE issuer='""" + ISSUER + """'
      AND subject='""" + subject + """' AND status='ACTIVE'
      RETURNING external_identity_id;
    """)
    result = compose(p, envfile, "exec", "-T", "cp-db", "psql", "-X",
                     "-At", "-v", "ON_ERROR_STOP=1", "-U", "controlplane",
                     "-d", "controlplane", "-c", revoked, capture=True, timeout=35)
    must(result.strip() != "", "Expected canonical external identity not revoked")
    after = json.loads(run_probe(p, envfile, "revoked"))
    cases = report.get("scenarios", {})
    checks = report.setdefault("checks", {})
    checks["cp01_unmapped_principal_denied"] = unmapped.get("unmapped_denied") is True
    checks["cp01_revoked_identity_denied"] = after.get("revocation_denied") is True
    # Verified local TLS (EA v2.2 INT-02) is observed in this run, never assumed.
    transport = json.loads(run_probe(p, envfile, "tls"))
    for name in TLS_CHECKS:
        checks[name] = transport.get(name) is True
    # L4-CP-01 is PASS only with its positive AND every matrix negative
    # (swapped Organisation, fabricated tenant, unmapped principal, revoked
    # identity), all observed in this run. Revocation never promotes L4-CP-03.
    if cases.get("L4-CP-01") == "BLOCKED":
        cases["L4-CP-01"] = ("PASS" if checks["cp01_unmapped_principal_denied"]
                             and checks["cp01_revoked_identity_denied"] else "FAIL")
    required = set(lock["mandatory"])
    must(set(cases) == required, "Mandatory IAM/CP scenarios missing")
    if any(cases[x] != "PASS" for x in required) or not tls_verified(checks):
        # Preserve the sanitized report for triage, NEVER promote to PASS.
        write_evidence(p, lock, report, accepted=False)
        raise Blocked("Real IAM/CP scenario denied or unavailable, or local TLS "
                      "not verified (EA v2.2 INT-02); see scrubbed evidence")
    write_evidence(p, lock, report, accepted=True)
    print("INT-02 actual IAM↔CP profile PASS; not protected staging")

# EA v2.2 matrix (INT-02 backlog): the real IAM/CP process test runs "over
# verified local TLS". All three must be observed by the probe in this run:
# IAM and CP each answer over TLS verified against this run's CA and edge
# hostname, and the same endpoint is refused without that CA.
TLS_CHECKS = ("tls_iam_verified", "tls_cp_verified", "tls_untrusted_refused")

def tls_verified(checks):
    return all(checks.get(name) is True for name in TLS_CHECKS)

def image_id(envfile, variable):
    """The locally built image's content ID (build provenance, EA v2.2 §4.4)."""
    for line in envfile.read_text().splitlines():
        name, _, value = line.partition("=")
        if name == variable and re.fullmatch(r"l4-(iam|cp)-l4-[0-9a-f]{16}", value):
            try:
                return execute(["docker", "image", "inspect", "--format", "{{.Id}}", value],
                               capture=True, timeout=20).strip()
            except Blocked:
                return "unavailable"
    return "unavailable"

def write_evidence(p, lock, report, accepted):
    EVIDENCE.mkdir(exist_ok=True)
    envfile = Path(p.get("directory", "")) / "runtime.env"
    built = {"iam": image_id(envfile, "L4_IAM_IMAGE"), "cp": image_id(envfile, "L4_CP_IMAGE")} \
        if envfile.is_file() else {"iam": "unavailable", "cp": "unavailable"}
    receipt = {"profile":"iam-cp","classification":lock["evidence_class"],
       "scenario_ids":lock["mandatory"],"scenarios":report["scenarios"],
       # Named positive/negative sub-checks (booleans only; no responses).
       "checks":report.get("checks", {}),
       # EA v2.2 §4.4 (iv)-(vi): build provenance, executing profile and
       # limits, and actual vs simulated components.
       "images":{"built_from_pinned_source":built,
                 "runtime_pins":lock["runtime_images"]},
       "executing_profile":{"name":"iam-cp","requirements":lock["requirements"],
                            "runner":"github-actions" if os.environ.get("GITHUB_ACTIONS") else "local"},
       "components":{"real":["keycloak (pinned baobab-iam source)","control plane (pinned baobab-cp source)",
                             "postgresql"],
                     "simulated":["synthetic tenants, organisations, grants and provider binding"],
                     "provider":"synthetic resolution fixture only; no live certified provider"},
       "transport":{"tls_verified":tls_verified(report.get("checks", {})),
                    "mode":"tls1.3-edge-verified-per-run-ca",
                    "edge_to_upstream":"http-on-internal-compose-network",
                    "issuer":ISSUER},
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
    body = json.dumps(receipt, sort_keys=True, indent=2)
    # (ix) scrubbed evidence digest, computed over the receipt without it.
    receipt["evidence_sha256"] = hashlib.sha256(body.encode()).hexdigest()
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
