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
SERVICES = {"keycloak", "iam-db", "cp", "cp-db", "edge", "probe", "human"}
# ADR-SHARED-036 s6.8/s6.10: a CP or IAM pull request runs this profile
# against its own head through the reusable workflow; only these two pins
# may be replaced, and only by a full commit SHA.
CANDIDATE_REPOSITORIES = {"baobab-iam", "baobab-cp"}

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
                        "human-user-lookup", "human-user-create", "human-read-scope-create",
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
        # psql runs with VERBOSITY=sqlstate: its error is then only a
        # five-character SQLSTATE code, never a row, value or statement.
        sqlstate = ""
        if "psql" in args:
            for line in p.stderr.splitlines():
                code = re.fullmatch(r"(?:psql:[^ ]* )?ERROR:  ([0-9A-Z]{5})", line.strip())
                if code:
                    sqlstate = code.group(1)
        raise Blocked("External command failed: " + Path(args[0]).name +
                      (f"; CP SQL state: {sqlstate}" if sqlstate else "") +
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
             "INT-02 fixture HTTP class:", "IAM diagnostics:", "CP SQL state:")) else ""
        raise Blocked(f"Compose {stage}/{target} failed; service states: "
                      + (", ".join(sorted(snapshot)) if snapshot else "unavailable")
                      + (f"; {safe_cause}" if safe_cause else "")) from cause

def host_path(path):
    """A bind-mount source as the Docker daemon sees it (ADR-SHARED-036 s6.3).

    The integration Codespace and the devcontainer CI job use
    docker-outside-of-docker: the daemon runs on the host and resolves mount
    sources against the HOST filesystem, where the workspace lives at a
    different path. The devcontainer passes both folders through remoteEnv.
    On a plain runner neither is set and paths are unchanged. Build contexts
    are read by the Compose client and are never translated.
    """
    local = os.environ.get("LOCAL_WORKSPACE_FOLDER", "")
    inside = os.environ.get("CONTAINER_WORKSPACE_FOLDER", "")
    if not local and not inside:
        return str(path)
    must(bool(local) and bool(inside) and local.startswith("/") and inside.startswith("/")
         and not re.search(r"[\x00-\x1f]", local + inside),
         "LOCAL_WORKSPACE_FOLDER and CONTAINER_WORKSPACE_FOLDER must both be absolute paths")
    source = Path(path).resolve()
    root = Path(inside).resolve()
    must(source.is_relative_to(root), "Bind-mount source is outside the devcontainer workspace")
    return str(Path(local) / source.relative_to(root))

def candidate_pins(lock):
    """The source pins to materialise: the lock, or one validated candidate."""
    pins = dict(lock["sources"])
    name = os.environ.get("INT02_CANDIDATE_REPOSITORY", "").strip()
    sha = os.environ.get("INT02_CANDIDATE_SHA", "").strip()
    if not name and not sha:
        return pins, None
    must(name in CANDIDATE_REPOSITORIES and SHA40.fullmatch(sha) is not None,
         "A candidate must name baobab-iam or baobab-cp and a full 40-character commit SHA")
    candidate = {"repository": name, "sha": sha, "lock_pin": pins[name]}
    pins[name] = sha
    return pins, candidate

def verify_bind_mounts(p, directory, envfile, lock):
    """Fail fast, and say why, if the daemon cannot see the harness files."""
    expected = (directory / ".mount-sentinel").read_text().strip()
    source = next((line.partition("=")[2] for line in envfile.read_text().splitlines()
                   if line.startswith("L4_RUNTIME=")), "")
    try:
        seen = execute(["docker", "run", "--rm", "--network", "none", "-v", source + ":/m:ro",
                        lock["runtime_images"]["python_probe"], "cat", "/m/.mount-sentinel"],
                       capture=True, timeout=180).strip()
    except Blocked:
        # A missing source is created EMPTY by the daemon, so cat fails.
        seen = ""
    must(seen == expected, "The Docker daemon cannot see the harness bind mounts. Under "
         "docker-outside-of-docker set LOCAL_WORKSPACE_FOLDER and CONTAINER_WORKSPACE_FOLDER "
         "(the integration devcontainer does this through remoteEnv)")

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
    pins, candidate = candidate_pins(lock)
    directory.mkdir(mode=0o700, parents=True)
    # Always allowlist exact GitHub org paths; no redirects or arbitrary URL.
    try:
        for name in ("baobab-iam", "baobab-cp", "shared"):
            dest = directory / name
            execute(["git", "clone", "--quiet", "--no-checkout", "--",
                     "https://github.com/baobab-platform/" + name + ".git",
                     str(dest)], timeout=300)
            if candidate and candidate["repository"] == name:
                # A pull-request head need not be on any branch; fetch it by SHA.
                execute(["git", "-C", str(dest), "fetch", "--quiet", "origin", pins[name]],
                        timeout=300)
            execute(["git", "-C", str(dest), "checkout", "--quiet", "--detach",
                     pins[name]], timeout=60)
            sha = execute(["git", "-C", str(dest), "rev-parse", "HEAD"],
                          capture=True, timeout=15).strip()
            must(sha == pins[name], "Git source pin mismatch")
        runtime = {
            # Bind-mount sources are daemon (host) paths; see host_path().
            "L4_PROJECT": project, "L4_RUNTIME": host_path(directory),
            "L4_IAM_SOURCE": str(directory / "baobab-iam"),
            "L4_CP_SOURCE": str(directory / "baobab-cp"),
            "L4_CP_DOCKERFILE": str(BASE / "cp.Dockerfile"),
            "L4_HUMAN_SOURCE": str(BASE / "human"),
            "L4_HUMAN_IMAGE": "l4-human-" + project,
            "L4_WORKLOAD_REGISTRY": host_path(directory / "shared/contracts/identity/v1/workload-registry.yaml"),
            "L4_PROBE_SOURCE": host_path(BASE),
            "L4_POSTGRES_IMAGE": lock["runtime_images"]["postgres"],
            "L4_PYTHON_IMAGE": lock["runtime_images"]["python_probe"],
            "L4_EDGE_IMAGE": lock["runtime_images"]["tls_edge"],
            "L4_EDGE_CONFIG": host_path(BASE / "edge.conf"),
            "L4_TLS": host_path(directory / "tls"),
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
        # Not a secret: up() reads it back through a real bind mount.
        (directory / ".mount-sentinel").write_text(secrets.token_hex(16) + "\n")
        os.chmod(directory / ".mount-sentinel", 0o644)
        private(directory / "runtime.env",
                "".join(k + "=" + v + "\n" for k, v in runtime.items()))
        # Fixture clients are disposable IAM test records only. Human login
        # requires code/S256 and an exact callback; password grant is disabled.
        admin_client = {
          "clientId":"l4-int02-admin", "enabled":True, "publicClient":False,
          "secret":runtime["L4_TEST_ADMIN_CLIENT_SECRET"],
          "serviceAccountsEnabled":False, "standardFlowEnabled":True,
          "redirectUris":["https://human.int02.test/callback"],
          "attributes":{"pkce.code.challenge.method":"S256"},
          "directAccessGrantsEnabled":False, "implicitFlowEnabled":False,
          # Keycloak 26 issues `sub` only through its built-in "basic" client
          # scope; an explicit scope list without it yields tokens CP cannot
          # map to a principal (observed live: has_sub=false).
          "protocol":"openid-connect", "defaultClientScopes":[
            "basic","openid","actor-type-human","authority:self","canonical:read"
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
                "sources": pins, "candidate": candidate,
                "started": datetime.now(timezone.utc).isoformat()}) + "\n")
    except BaseException:
        if SESSION.exists():
            # Once session exists, let down retain its handles on failure.
            pass
        else:
            shutil.rmtree(directory, ignore_errors=True)
        raise
    print("INT-02 source materialised at audited IAM and CP commit IDs" +
          (f" (candidate {candidate['repository']} {candidate['sha']})" if candidate else ""))

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
    ext.write_text(f"subjectAltName=DNS:{IAM_HOST},DNS:{CP_HOST},DNS:human.int02.test\n"
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
    verify_bind_mounts(p, directory, envfile, lock)
    # Keycloak and CP may require significant build resources; never hide
    # build failure as a skip or replace the source binary with a mock.
    print("INT-02 build stage: Keycloak from pinned IAM source",flush=True)
    compose(p, envfile, "build", "keycloak", timeout=1800)
    print("INT-02 build stage: Control Plane + migrator from pinned source",flush=True)
    compose(p, envfile, "build", "cp-migrate", timeout=1800)
    print("INT-02 build stage: real browser and confidential OIDC RP",flush=True)
    compose(p, envfile, "build", "human", timeout=900)
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
    compose(p, envfile, "up", "-d", "cp", "probe", "human", timeout=180)
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
                   mode, capture=True, timeout=260 if mode == "human-proof" else 180)

CP_FIXTURE_STEPS = {"tenant_a", "tenant_b", "tenant_no_primary", "market_participation",
                    "capability_binding",
                    "identity_workload", "identity_human", "revoke_grant", "revoke_workload"}

def cp_sql(p, envfile, step, statement, timeout=30):
    """Run one synthetic-fixture statement in the disposable CP database.

    On failure only the fixed step name and psql's SQLSTATE leave this
    process, never the statement, its values or a server message.
    """
    must(step in CP_FIXTURE_STEPS, "Unknown CP fixture step")
    try:
        return compose(p, envfile, "exec", "-T", "cp-db", "psql", "-X", "-v", "VERBOSITY=sqlstate",
                       "-At", "-v", "ON_ERROR_STOP=1", "-U", "controlplane", "-d", "controlplane",
                       "-c", statement, capture=True, timeout=timeout)
    except Blocked as cause:
        raise Blocked(f"{cause}; CP fixture step: {step}") from cause

def seed_identities(p, envfile, ids):
    """Link each real Keycloak subject to a CP Principal; returns what CP held.

    CP auto-provisions WORKLOAD principals on first authenticated context
    resolution (ADR-0004 s13, ADR-0007 s46: WorkloadOnlyProvisioningPolicy),
    so the earlier unmapped-principal probe may already have materialised the
    workload. Respect that: reuse an ACTIVE (issuer, subject) link, never
    duplicate it. Humans are never auto-provisioned on these routes, so the
    human link must be created here. This is the explicit synthetic-only
    fixture boundary; never replicate it in production or staging.
    """
    import uuid
    held = {}
    for name in ("workload", "human", "parent", "subsidiary", "sibling", "external"):
        subject = ids[name + "_sub"]
        must(re.fullmatch("[0-9a-f-]{36}", subject) is not None,
             "Keycloak principal subject invalid")
        actor_type = "workload" if name == "workload" else "human"
        identity = str(uuid.uuid4())
        link = "issuer='" + ISSUER + "' AND subject='" + subject + "' AND status='ACTIVE'"
        stmt = ("WITH found AS (SELECT principal_id FROM identity.external_identity WHERE " + link + "), "
                "np AS (INSERT INTO identity.principal(principal_id,actor_type,status) "
                "SELECT '" + identity + "','" + actor_type + "','ACTIVE' "
                "WHERE NOT EXISTS (SELECT 1 FROM found) RETURNING principal_id), "
                "ne AS (INSERT INTO identity.external_identity(principal_id,issuer,subject,status) "
                "SELECT principal_id,'" + ISSUER + "','" + subject + "','ACTIVE' FROM np RETURNING 1) "
                "SELECT COALESCE((SELECT 'existing:' || p.actor_type FROM found f "
                "JOIN identity.principal p USING (principal_id)), 'created');")
        state = cp_sql(p, envfile, "identity_" + ("workload" if name == "workload" else "human"), stmt, timeout=25).strip()
        must(state in ("created", "existing:" + actor_type), "CP principal for " + name + " has the wrong actor type")
        must(name == "workload" or state == "created", "CP provisioned a human principal unexpectedly")
        held[name] = state
    return held

def seed_tenants(p, directory, envfile):
    # All objects remain explicitly SYNTHETIC and private to the disposable
    # PostgreSQL test database; no external registry, legal or onboarding
    # assertion is made by their presence. PRIMARY Organisation mappings
    # are real CP schema objects, not fabricated JSON claims.
    import uuid
    tenant_a, tenant_b, tenant_parent, tenant_external = ("tn_l4" + secrets.token_hex(8) for _ in range(4))
    org_a, org_b, org_parent, org_external = (str(uuid.uuid4()) for _ in range(4))
    tenant_c, org_c = "tn_l4" + secrets.token_hex(8), str(uuid.uuid4())
    for step, tenant, org, legal in (("tenant_a",tenant_a,org_a,"LE-L4-A"),
                                      ("tenant_b",tenant_b,org_b,"LE-L4-B"),
                                      ("tenant_b",tenant_parent,org_parent,"LE-L4-P"),
                                      ("tenant_b",tenant_external,org_external,"LE-L4-E"),
                                      ("tenant_b",tenant_c,org_c,"LE-L4-C")):
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
        -- CP requires a registration basis. A fixture is registered outside
        -- admission, so it is BOOTSTRAP with its reason and evidence, as in
        -- CP's own repository fixtures; never ONBOARDING.
        INSERT INTO tenants (tenant_id,legal_entity_id,display_name,
            isolation_strategy,residency_region,observed_state,
            primary_organisation_enforced,registration_basis,
            bootstrap_reason,bootstrap_evidence_reference)
            VALUES ('{tenant}','{legal}','INT-02 disposable test',
            'row_level_security','af-south-1','active',true,'BOOTSTRAP',
            'INT-02 synthetic fixture registered outside admission',
            'int02-synthetic-fixture');
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
        cp_sql(p, envfile, step, statement, timeout=35)
    # L4-CP-01's positive is a "Principal / PRIMARY Organisation / Tenant /
    # market context read", and capability resolution denies a context that
    # names no market (RESIDENCY_POLICY_MISMATCH). CP fills the market from
    # the tenant's ACTIVE market participation (resolveMarket), so tenant A
    # participates in one synthetic ACTIVE market: a registry entry activated
    # by a checker other than its maker (CP's own constraint), its projected
    # market row, and an ACTIVE assignment. Tenant B stays market-less; its
    # refusal happens earlier, at the grant boundary.
    market = "mkt_l4" + secrets.token_hex(6)
    cp_sql(p, envfile, "market_participation", f"""
        BEGIN;
        INSERT INTO market.registry (market_id, canonical_key, owner_tenant_id, configuration,
            status, created_at, created_by, activated_at, activated_by)
            VALUES ('{market}','{market}','{tenant_a}','{{"default_country":"ZA"}}'::jsonb,
            'ACTIVE', now() - interval '72 hours', 'int02-synthetic-maker',
            now() - interval '48 hours', 'int02-synthetic-checker');
        INSERT INTO market.market (code, name, currency, region, is_active, registry_market_id)
            VALUES ('ZA', 'INT-02 synthetic market', 'ZAR', 'af-south-1', true, '{market}');
        INSERT INTO market.market_assignment (tenant_id, market_id, status, source, effective_from)
            SELECT '{tenant_a}', market_id, 'ACTIVE', 'MIGRATION', now() - interval '1 hour'
            FROM market.market WHERE code = 'ZA';
        COMMIT;
        """, timeout=35)
    # A governed tenant's initially valid PRIMARY naturally expires. The
    # old fixture used a grandfathered non-enforcing BOOTSTRAP row, which
    # legitimately exercises v1 migration compatibility instead of LA-T02.
    # Do not disable DB constraints to manufacture an impossible tenant.
    cp_sql(p, envfile, "tenant_no_primary", f"""
      UPDATE registry.tenant_organisation_mapping SET effective_to=now()+interval '2 seconds'
      WHERE tenant_id='{tenant_c}' AND mapping_role='PRIMARY_ORGANISATION';
    """, timeout=35)
    # A capability binding is NOT its own grant. One ACTIVE scoped grant is
    # intentionally given to A only, so sibling B receives a real CP denial.
    # This synthetic provider is a resolution fixture, not a published or
    # executable Baobab Pulse implementation and never satisfies INT-08.
    statement = f"""
    WITH c AS (
      -- CP syncs Shared's canonical capability catalogue at startup
      -- (catalogue.SyncEmbedded, ADR-SHARED-017 G-CP-2): the capability
      -- already exists and its meaning comes from Shared. Bind to it; never
      -- fabricate a competing capability row.
      SELECT capability_id FROM capability.capability
      WHERE code='intelligence.evidence.search' AND status='ACTIVE'
    ), e0 AS (
      -- CP registers its engine providers at startup (main.go: "engine
      -- providers registered"), which creates the canonical baobab-pulse
      -- engine with a DRAFT baobab-pulse.core provider. Share that engine row
      -- (CP's own ON CONFLICT pattern); never activate CP's DRAFT provider.
      -- The provider below stays the explicitly synthetic fixture.
      INSERT INTO topology.engine(code,name) VALUES ('baobab-pulse','baobab-pulse')
      ON CONFLICT (code) DO NOTHING RETURNING engine_id
    ), e AS (
      SELECT engine_id FROM e0
      UNION ALL
      SELECT engine_id FROM topology.engine
      WHERE code='baobab-pulse' AND NOT EXISTS (SELECT 1 FROM e0)
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
    ), g AS (
      INSERT INTO capability.capability_grant
        (tenant_id,capability_id,scope_id,source,status,effective_from)
      SELECT '{tenant_a}',c.capability_id,s.scope_id,
             'PLATFORM_BASELINE','ACTIVE',now()-interval '1 hour'
      FROM c,s RETURNING 1
    )
    SELECT (SELECT count(*) FROM b) || ':' || (SELECT count(*) FROM g);
    """
    written = cp_sql(p, envfile, "capability_binding", statement, timeout=30).strip()
    # Exactly one binding and one grant, or the canonical capability is absent.
    must(written == "1:1", "CP's synced catalogue has no ACTIVE intelligence.evidence.search")
    # Bounded fixture clock advance, never a prerequisite or CI polling sleep.
    __import__("time").sleep(3)
    private(directory / "fixtures.json",json.dumps({
        "tenant":tenant_a,"other_tenant":tenant_b,"organisation":org_a,
        "no_primary_tenant":tenant_c,"market":market,"market_country":"ZA",
        "other_organisation":org_b,
        "isolation":{"parent":{"tenant":tenant_parent,"organisation":org_parent},
                     "subsidiary":{"tenant":tenant_a,"organisation":org_a},
                     "sibling":{"tenant":tenant_b,"organisation":org_b},
                     "external":{"tenant":tenant_external,"organisation":org_external}}})+"\n")

def seed_isolation_authority(p, directory, envfile, ids):
    """Real CP records on synthetic data, not production grants or legal proof.

    Each human receives EXACT organisation.view only for its own Organisation.
    Shared corporate ownership and PlatformAccount membership are deliberately
    present, so their failure to confer neighbour access is actually tested.
    """
    import uuid
    fixture = json.loads((directory / "fixtures.json").read_text())["isolation"]
    for label, target in fixture.items():
        subject = ids[label + "_sub"]
        must(re.fullmatch(r"[0-9a-f-]{36}", subject) is not None, "Invalid isolation subject")
        org = target["organisation"]
        scope = json.dumps({"level":"ORGANISATION","organisation_id":org,"mode":"EXACT","environment":"integration"})
        cp_sql(p, envfile, "identity_human", f"""
          INSERT INTO policy.administrative_grant
          (grant_id,principal_id,permission,scope_level,scope,grant_type,source,
           risk_class,valid_from,valid_until,status,granted_by,reason)
          -- Canonical identity uses UUIDs; administrative grants deliberately
          -- accept a textual principal reference. Keep the conversion explicit.
          SELECT '{uuid.uuid4()}',principal_id::text,'organisation.view','ORGANISATION',
                 '{scope}'::jsonb,'TIME_BOUND','DIRECT','LOW',now()-interval '1 minute',
                 now()+interval '30 minutes','ACTIVE','int02-independent-fixture-authoriser',
                 'INT-02 synthetic exact Organisation read; no group-derived access'
          FROM identity.external_identity WHERE issuer='{ISSUER}' AND subject='{subject}' AND status='ACTIVE';
        """)
    parent = fixture["parent"]["organisation"]
    for child in (fixture["subsidiary"]["organisation"],fixture["sibling"]["organisation"]):
        cp_sql(p, envfile, "identity_human", f"""
          INSERT INTO registry.corporate_relationship
          (source_organisation_id,target_organisation_id,relationship_type,ownership_percentage,
           verification_state,status,effective_from,source_authority,evidence_references,verified_by,verified_at)
          VALUES ('{parent}','{child}','OWNS',100,'VERIFIED','ACTIVE',now()-interval '1 hour',
            'INT-02 synthetic relationship only','["int02-synthetic-not-legal-evidence"]'::jsonb,
            'int02-fixture-checker',now()-interval '1 hour');
        """)
    account = str(uuid.uuid4())
    cp_sql(p, envfile, "identity_human", f"""
      INSERT INTO registry.platform_account(platform_account_id,display_name,primary_organisation_id,status,effective_from)
      VALUES ('{account}','INT-02 synthetic shared account','{parent}','ACTIVE',now()-interval '1 hour');
    """)
    for target in fixture.values():
        org = target["organisation"]
        cp_sql(p, envfile, "identity_human", f"""
          INSERT INTO registry.platform_account_membership
          (platform_account_id,organisation_id,account_role,status,effective_from,evidence_reference)
          VALUES ('{account}','{org}','ACCOUNT_MEMBER','ACTIVE',now()-interval '1 hour','int02-synthetic');
        """)


ISOLATION_REQUIRED = tuple("cp03_" + label + "_" + check
    for label in ("parent","subsidiary","sibling","external")
    for check in ("own_record","directory_exact","neighbours_denied","tenant_spoof_denied"))


def apply_isolation_proof(report, proof):
    checks = report.setdefault("checks", {})
    for name in ISOLATION_REQUIRED:
        checks[name] = proof.get("checks", {}).get(name) is True
    report["scenarios"]["L4-CP-03"] = "PASS" if all(checks[n] for n in ISOLATION_REQUIRED) else "FAIL"


def test(lock):
    check_prerequisites(lock)
    p, directory, envfile = current()
    try:
        human_report = json.loads(run_probe(p, envfile, "human-proof"))
    except Blocked:
        # A failed browser ceremony must still leave a scrubbed receipt.
        # No downstream scenario ran, so they remain BLOCKED, never PASS.
        failed = {"scenarios":{name:"FAIL" if name == "L4-IAM-01" else "BLOCKED"
                               for name in lock["mandatory"]},
                  "checks":{"iam01_browser_ceremony_completed":False}}
        write_evidence(p, lock, failed, accepted=False)
        raise
    ids = json.loads(run_probe(p, envfile, "identities"))
    must(ids.get("source") == "keycloak-issued" and
         ids.get("issuer") == ISSUER,
         "IAM evidence is not real issuer issued")
    # Tenants first: the unmapped-principal negative (L4-CP-01) needs a real
    # tenant and Organisation, and must run BEFORE the Keycloak subject is
    # linked to a CP Principal.
    seed_tenants(p, directory, envfile)
    unmapped = json.loads(run_probe(p, envfile, "unmapped"))
    held = seed_identities(p, envfile, ids)
    seed_isolation_authority(p, directory, envfile, ids)
    # Independently isolate workload audience and client lifecycle while the
    # real issuer and CP are alive. The probe restores both fixture changes
    # before returning; a failed restore aborts rather than tainting evidence.
    workload_report = json.loads(run_probe(p, envfile, "workload-proof"))
    report = json.loads(run_probe(p, envfile, "test"))
    apply_workload_proof(report, workload_report)
    apply_human_proof(report, human_report)
    apply_isolation_proof(report, json.loads(run_probe(p, envfile, "isolation-proof")))
    # L4-CP-01 "revoked grant": revoke tenant A's grant (synthetic-fixture
    # operation in the throwaway DB) and require CP to refuse the same
    # entitled context for GRANT_REVOKED, while the identity is still valid.
    tenant_a = json.loads((directory / "fixtures.json").read_text())["tenant"]
    must(re.fullmatch(r"tn_l4[0-9a-f]{16}", tenant_a) is not None, "Invalid fixture tenant")
    revoked_grants = cp_sql(p, envfile, "revoke_grant",
        "UPDATE capability.capability_grant SET status='REVOKED' WHERE tenant_id='" + tenant_a +
        "' AND status='ACTIVE' RETURNING grant_id;", timeout=35)
    must(revoked_grants.strip() != "", "Expected fixture grant not revoked")
    grant_after = json.loads(run_probe(p, envfile, "grant-revoked"))
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
    result = cp_sql(p, envfile, "revoke_workload", revoked, timeout=35)
    must(result.strip() != "", "Expected canonical external identity not revoked")
    after = json.loads(run_probe(p, envfile, "revoked"))
    cases = report.get("scenarios", {})
    checks = report.setdefault("checks", {})
    checks["cp01_unmapped_principal_denied"] = unmapped.get("unmapped_human_denied") is True
    checks["cp01_revoked_grant_denied"] = grant_after.get("revoked_grant_denied") is True
    observations = report.setdefault("observations", {})
    for source in (unmapped, grant_after):
        observations.update(source.get("observations", {}))
    checks["cp01_revoked_identity_denied"] = after.get("revocation_denied") is True
    # Observed CP behaviour, recorded rather than assumed: whether CP had
    # already provisioned the workload principal when the harness linked it.
    checks["cp_workload_principal_auto_provisioned"] = held["workload"] == "existing:workload"
    # Verified local TLS (EA v2.2 INT-02) is observed in this run, never assumed.
    transport = json.loads(run_probe(p, envfile, "tls"))
    for name in TLS_CHECKS:
        checks[name] = transport.get(name) is True
    # L4-CP-01 is PASS only with its positive AND every matrix negative,
    # all observed in this run: missing and fabricated Organisation, swapped
    # Organisation/Tenant, unmapped principal and revoked grant (plus the
    # fabricated tenant and revoked identity). Never promotes L4-CP-03.
    # "Missing Organisation" must be DENIED for PASS. CP issuing an
    # Organisation-less context follows the Shared control-plane/v1 contract
    # (Organisation optional) but not the matrix wording: that conflict is
    # for the owners to resolve, so CP-01 then stays BLOCKED, never PASS.
    if cases.get("L4-CP-01") == "BLOCKED":
        if not all(checks.get(name) is True for name in CP01_REQUIRED):
            cases["L4-CP-01"] = "FAIL"
        elif report.get("observations", {}).get("cp01_missing_organisation_outcome") == "DENIED":
            cases["L4-CP-01"] = "PASS"
    required = set(lock["mandatory"])
    must(set(cases) == required, "Mandatory IAM/CP scenarios missing")
    if any(cases[x] != "PASS" for x in required) or not tls_verified(checks):
        # Preserve the sanitized report for triage, NEVER promote to PASS.
        write_evidence(p, lock, report, accepted=False)
        print(outcome_summary(cases, checks, observations), flush=True)
        raise Blocked("Real IAM/CP scenario denied or unavailable, or local TLS "
                      "not verified (EA v2.2 INT-02); see scrubbed evidence")
    write_evidence(p, lock, report, accepted=True)
    print(outcome_summary(cases, checks, observations), flush=True)
    print("INT-02 actual IAM↔CP profile PASS; not protected staging")

# Every human check is independently observed; truthy values or missing
# negatives cannot promote acceptance. CP authenticates the resulting HUMAN
# token separately after its canonical identity is explicitly linked.
IAM01_REQUIRED = (
    "iam01_code_pkce_positive", "iam01_privileged_mfa_completed", "iam01_signed_id_token", "iam01_code_replay_denied",
    "iam01_state_replay_denied", "iam01_wrong_state_denied", "iam01_wrong_nonce_denied",
    "iam01_wrong_pkce_denied", "iam01_forged_signature_denied", "iam01_wrong_issuer_denied",
    "iam01_wrong_audience_denied", "iam01_expired_token_denied",
    "iam01_unregistered_callback_denied", "iam01_callback_path_denied")


def apply_human_proof(report, proof):
    checks = report.setdefault("checks", {})
    for name in IAM01_REQUIRED:
        checks[name] = proof.get("checks", {}).get(name) is True
    # The existing real CP effective-authority positive is also mandatory.
    checks["iam01_cp_human_accepted"] = report["scenarios"].get("L4-IAM-01") == "BLOCKED"
    report["scenarios"]["L4-IAM-01"] = ("PASS" if checks["iam01_cp_human_accepted"] and
        all(checks[name] for name in IAM01_REQUIRED) else "FAIL")


# Exact requirements for this workload-only slice. A missing check or a
# truthy string is a failure, never a pass. Other matrix scenarios retain
# their own classification and keep the complete profile blocked as needed.
IAM02_REQUIRED = ("iam02_registered_workload_positive", "iam02_same_client_audience_only",
                  "iam02_wrong_audience_denied", "iam02_disabled_client_issuance_denied",
                  "iam02_fixture_restored")


def apply_workload_proof(report, proof):
    checks = report.setdefault("checks", {})
    for name in (*IAM02_REQUIRED, "iam02_claims_isolated", "iam02_introspection_active",
                 "iam02_introspection_subject_matches"):
        checks[name] = proof.get("checks", {}).get(name) is True
    for name in ("iam02_wrong_audience_status", "iam02_disabled_client_status", "iam02_introspection_status"):
        value = proof.get("observations", {}).get(name)
        if type(value) is int and 100 <= value <= 599:
            report.setdefault("observations", {})[name] = value
    report["scenarios"]["L4-IAM-02"] = ("PASS" if all(checks[name] for name in IAM02_REQUIRED) else "FAIL")


# EA v2.2 matrix (INT-02 backlog): the real IAM/CP process test runs "over
# verified local TLS". All three must be observed by the probe in this run:
# IAM and CP each answer over TLS verified against this run's CA and edge
# hostname, and the same endpoint is refused without that CA.
TLS_CHECKS = ("tls_iam_verified", "tls_cp_verified", "tls_untrusted_refused")
# EA v2.2 matrix L4-CP-01, every check observed in the same run.
CP01_REQUIRED = ("cp01_positive", "cp01_missing_organisation_not_fabricated",
                 "cp01_fabricated_organisation_denied", "cp01_swapped_organisation_denied",
                 "cp01_fabricated_tenant_denied", "cp01_unmapped_principal_denied",
                 "cp01_revoked_grant_denied", "cp01_revoked_identity_denied")

def outcome_summary(cases, checks, observations=None):
    """The run's outcome for the job log: fixed vocabulary only.

    Scenario states are PASS/FAIL/BLOCKED and checks are booleans, so this
    carries no credential, token, identifier or response.
    """
    states = " ".join(f"{k}={cases.get(k) if cases.get(k) in ('PASS', 'FAIL', 'BLOCKED') else 'UNKNOWN'}"
                      for k in sorted(REQUIRED))
    named = " ".join(f"{k}={'true' if v is True else 'false'}"
                     for k, v in sorted(checks.items()) if re.fullmatch(r"[a-z0-9_]{1,48}", k))
    seen = " ".join(f"{k}={v}" for k, v in sorted((observations or {}).items())
                    if re.fullmatch(r"[a-z0-9_]{1,48}", k) and
                    (isinstance(v, int) and not isinstance(v, bool) or
                     isinstance(v, str) and re.fullmatch(r"[A-Z0-9_]{1,48}", v)))
    return f"INT-02 scenarios: {states}\nINT-02 checks: {named}\nINT-02 observations: {seen}"

def tls_verified(checks):
    return all(checks.get(name) is True for name in TLS_CHECKS)

def image_id(envfile, variable):
    """The locally built image's content ID (build provenance, EA v2.2 §4.4)."""
    for line in envfile.read_text().splitlines():
        name, _, value = line.partition("=")
        if name == variable and re.fullmatch(r"l4-(iam|cp|human)-l4-[0-9a-f]{16}", value):
            try:
                return execute(["docker", "image", "inspect", "--format", "{{.Id}}", value],
                               capture=True, timeout=20).strip()
            except Blocked:
                return "unavailable"
    return "unavailable"

def harness_sha():
    """The checked-out harness commit; a receipt is never lost for want of it."""
    try:
        sha = execute(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture=True, timeout=15).strip()
    except Blocked:
        sha = ""
    return sha if SHA40.fullmatch(sha) else "unavailable"

def write_evidence(p, lock, report, accepted):
    EVIDENCE.mkdir(exist_ok=True)
    envfile = Path(p.get("directory", "")) / "runtime.env"
    built = {"iam": image_id(envfile, "L4_IAM_IMAGE"), "cp": image_id(envfile, "L4_CP_IMAGE"),
             "human": image_id(envfile, "L4_HUMAN_IMAGE")} \
        if envfile.is_file() else {"iam": "unavailable", "cp": "unavailable"}
    receipt = {"profile":"iam-cp","classification":lock["evidence_class"],
       "scenario_ids":lock["mandatory"],"scenarios":report["scenarios"],
       # Named positive/negative sub-checks (booleans only; no responses).
       "checks":report.get("checks", {}),
       # CP's fixed-vocabulary decisions and HTTP statuses behind the checks.
       "observations":report.get("observations", {}),
       # EA v2.2 §4.4 (iv)-(vi): build provenance, executing profile and
       # limits, and actual vs simulated components.
       "images":{"built_from_pinned_source":built,
                 "runtime_pins":lock["runtime_images"]},
       "executing_profile":{"name":"iam-cp","requirements":lock["requirements"],
                            "runner":"github-actions" if os.environ.get("GITHUB_ACTIONS") else "local"},
       "components":{"real":["keycloak (pinned baobab-iam source)","control plane (pinned baobab-cp source)",
                             "postgresql", "Chromium + confidential OIDC RP (synthetic login)"],
                     "simulated":["synthetic tenants, organisations, grants and provider binding"],
                     "provider":"synthetic resolution fixture only; no live certified provider"},
       "transport":{"tls_verified":tls_verified(report.get("checks", {})),
                    "mode":"tls1.3-edge-verified-per-run-ca",
                    "edge_to_upstream":"http-on-internal-compose-network",
                    "issuer":ISSUER},
       "source_pins":p.get("sources") or lock["sources"],"lock_pins":lock["sources"],
       "candidate":p.get("candidate"),"run_id":p["project"],
       # Source pins are dependency baselines; this is the ACTUAL checked
       # out integration harness revision, including GitHub's PR merge ref.
       # The checked-out harness itself, never the caller's SHA when this is
       # a reusable-workflow call from a CP or IAM pull request.
       "harness_candidate_sha":harness_sha(),
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
