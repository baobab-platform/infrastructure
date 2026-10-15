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
        raise Blocked("External command failed: " + Path(args[0]).name +
                      " (details confined to protected ephemeral runner)")
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
    return execute(["docker", "compose", "--env-file", str(envfile), "-f",
                    str(COMPOSE), "-p", p["project"], *args], capture=capture,
                   input_text=stdin, timeout=timeout)

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
    compose(p, envfile, "build", "keycloak", "cp-migrate", timeout=1800)
    compose(p, envfile, "up", "-d", "--wait", "--wait-timeout", "300",
            "iam-db", "cp-db", "keycloak", timeout=450)
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

def test(lock):
    check_prerequisites(lock)
    p, directory, envfile = current()
    ids = json.loads(run_probe(p, envfile, "identities"))
    must(ids.get("source") == "keycloak-issued" and
         ids.get("issuer") == "http://keycloak:8080/realms/baobab",
         "IAM evidence is not real issuer issued")
    seed_identities(p, envfile, ids)
    report = json.loads(run_probe(p, envfile, "test"))
    cases = report.get("scenarios", {})
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
