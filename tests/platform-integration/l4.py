#!/usr/bin/env python3
"""ADR-SHARED-036 INT-01: isolated L4-00 dependency integration (NOT staging).
Run the same Python standard-library entrypoints in Codespaces and Actions.
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

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
LOCK = BASE / "manifest.lock.json"
SCHEMA = BASE / "schema/manifest.schema.json"
COMPOSE = BASE / "compose.yaml"
STATE = BASE / ".runtime"
SESSION = STATE / "session.json"
EVIDENCE = BASE / "evidence"
SERVICES = ("postgres", "redis", "rabbitmq")
REQUIRED = ("L4-MAN-01", "L4-MAN-02", "L4-MAN-03", "L4-MAN-04")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")

class Blocked(Exception):
    """No secrets or provider response bodies are displayed."""

def require(condition, explanation):
    if not condition:
        raise Blocked(explanation)

def load():
    m = json.loads(LOCK.read_text())
    require(m.get("schema_version") == 1 and m.get("adr") == "ADR-SHARED-036"
            and m.get("ea_plan") == "EA-v2.2" and m.get("harness") == "L4-00",
            "Wrong architecture/plan/profile")
    require(m.get("classification") == "REAL_COMPONENT_SYNTHETIC_DATA"
            and m.get("simulators") == [] and m.get("contains_real_legal_actors") is False
            and m.get("contains_production_credentials") is False,
            "Unsafe classification or production credential assertion")
    pins = m.get("provenance", {})
    require(isinstance(pins, dict) and
            {"shared", "infrastructure", "baobab-cp", "baobab-iam", "nabhold"} <= set(pins)
            and all(isinstance(v, str) and HEX40.fullmatch(v) for v in pins.values()),
            "Full source SHAs required")
    images = m.get("foundation_images", {})
    require(isinstance(images, dict) and set(images) == set(SERVICES),
            "Missing/extra foundation image")
    for value in images.values():
        require(set(value) == {"tag", "digest"} and
                isinstance(value["tag"], str) and
                re.fullmatch(r"[a-zA-Z0-9_./:-]+", value["tag"]),
                "Unsafe image reference")
    profile = m.get("profiles", {}).get("foundation", {})
    require(set(profile.get("services", [])) == set(SERVICES) and
            set(profile.get("mandatory", [])) == set(REQUIRED),
            "Mandatory profile scenario omitted")
    require(json.loads(SCHEMA.read_text())["title"] ==
            "Baobab INT-01 immutable integration manifest", "Invalid schema")
    # Composition only permits private networks and omits host ports entirely.
    require(not re.search(r"(?m)^\s+ports\s*:", COMPOSE.read_text()),
            "Host port exposure in composition")
    return m

def images(m):
    for val in m["foundation_images"].values():
        require(bool(SHA256.fullmatch(val["digest"])),
                "Unverified image digest: only static preflight allowed")
    return {k: v["tag"].rsplit(":", 1)[0] + "@" + v["digest"]
            for k, v in m["foundation_images"].items()}

def invoke(args, timeout=180, output=False):
    return subprocess.run(args, timeout=timeout, check=True, text=True,
                          cwd=ROOT, capture_output=output)

def preflight(m, static=False):
    require((BASE / "README.md").is_file() and (BASE / "l4.py").is_file(),
            "L4 source incomplete")
    if static:
        return
    images(m)
    require((os.cpu_count() or 0) >= 2, "At least two CPUs required")
    if sys.platform == "linux":
        mem = next(int(s.split()[1]) for s in
                   Path("/proc/meminfo").read_text().splitlines()
                   if s.startswith("MemTotal:"))
        require(mem >= 4 * 1024 * 1024, "At least four GiB RAM required")
    require(shutil.which("docker") is not None, "Docker unavailable")
    invoke(["docker", "info"], timeout=20, output=True)
    invoke(["docker", "compose", "version"], timeout=20, output=True)

def private_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fp:
        fp.write(data)

def current():
    require(SESSION.is_file(), "No active L4 session")
    obj = json.loads(SESSION.read_text())
    project = obj.get("project", "")
    require(re.fullmatch(r"l4-[a-f0-9]{16}", project) is not None,
            "Invalid project state")
    env = STATE / (project + ".env")
    require(env.is_file() and env.stat().st_mode & 0o077 == 0,
            "Invalid private environment state")
    return obj, env

def compose(obj, env, *parts, output=False, timeout=200):
    return invoke(["docker", "compose", "--env-file", str(env), "-f",
                   str(COMPOSE), "-p", obj["project"], *parts],
                  output=output, timeout=timeout)

def up(m):
    preflight(m)
    require(not SESSION.exists(), "Existing L4 session; run down first")
    project = "l4-" + secrets.token_hex(8)
    values = {"L4_PROJECT": project}
    for name, image in images(m).items():
        values["L4_" + name.upper() + "_IMAGE"] = image
        values["L4_" + name.upper() + "_PASSWORD"] = secrets.token_urlsafe(32)
    env = STATE / (project + ".env")
    private_file(env, "".join(k + "=" + v + "\n" for k, v in values.items()))
    private_file(SESSION, json.dumps({"project": project,
                                       "started": datetime.now(timezone.utc).isoformat()}) + "\n")
    try:
        obj, env = current()
        compose(obj, env, "config", "--quiet", timeout=20)
        compose(obj, env, "up", "-d", "--wait", "--wait-timeout", "180", timeout=260)
    except BaseException:
        down()
        raise
    print("L4-00 isolated foundation running:", project)

def test(m):
    preflight(m)
    obj, env = current()
    cfg = json.loads(compose(obj, env, "config", "--format", "json",
                             output=True, timeout=20).stdout)
    require(set(cfg["services"]) == set(SERVICES)
            and all("ports" not in s for s in cfg["services"].values()),
            "Wrong service or exposed host port")
    for service in cfg["services"].values():
        require("foundation" in service.get("networks", []),
                "Cross-network service not permitted")
    compose(obj, env, "exec", "-T", "postgres", "psql", "-U", "l4_test",
            "-d", "l4_test", "-c", "SELECT 1", output=True, timeout=30)
    compose(obj, env, "exec", "-T", "rabbitmq", "rabbitmq-diagnostics",
            "-q", "ping", output=True, timeout=30)
    out = compose(obj, env, "exec", "-T", "redis", "sh", "-ec",
                  'REDISCLI_AUTH="$L4_REDIS_PASSWORD" redis-cli ping',
                  output=True, timeout=30).stdout
    require("PONG" in out, "Redis process did not respond")
    receipt = {"suite": "L4-00", "profile": "foundation",
               "classification": m["classification"], "run_id": obj["project"],
               "time_utc": datetime.now(timezone.utc).isoformat(),
               "manifest_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
               "source_pins": m["provenance"],
               # The accepted baseline remains pinned in the manifest; an
               # actual PR candidate SHA is additionally recorded for review.
               "candidate_source_sha": os.environ.get("GITHUB_SHA") or
                   invoke(["git", "rev-parse", "HEAD"], output=True, timeout=10).stdout.strip(),
               "image_digests": {k: v["digest"] for k,v in m["foundation_images"].items()},
               "scenarios": [{"id": k, "outcome": "PASS"} for k in REQUIRED],
               "protected_staging_accepted": False, "production_authorized": False}
    EVIDENCE.mkdir(exist_ok=True)
    name = EVIDENCE / (obj["project"] + ".json")
    name.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print("L4-00 real dependency probes passed; sanitized receipt:", name.relative_to(ROOT))

def down():
    if not SESSION.exists():
        print("No active L4 session")
        return
    obj, env = current()
    # Preserve recovery metadata and owner-private passwords if Docker fails.
    # A subsequent "down" must be able to retry deletion of any orphaned
    # containers, networks and volumes; never erase the only cleanup handle.
    compose(obj, env, "down", "--volumes", "--remove-orphans",
            "--timeout", "15", timeout=140)
    env.unlink()
    SESSION.unlink()
    print("Isolated L4 project/volumes removed")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["preflight", "up", "test", "evidence", "down"])
    p.add_argument("profile", nargs="?", default="foundation",
                   choices=["foundation"])
    p.add_argument("--static", action="store_true")
    a = p.parse_args()
    try:
        if a.action == "down":
            down()
        else:
            m = load()
            if a.action == "preflight":
                preflight(m, a.static)
                print("L4 preflight passed:", "SOURCE ONLY" if a.static else "runtime")
            elif a.action == "up":
                require(not a.static, "Static check cannot start L4")
                up(m)
            elif a.action == "test":
                require(not a.static, "Static check cannot run integration")
                test(m)
            else:
                obj, _ = current()
                path = EVIDENCE / (obj["project"] + ".json")
                require(path.is_file(), "No actual test evidence")
                print(path.read_text())
        return 0
    except (Blocked, ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        # Never print Docker stderr or secrets to untrusted CI logs.
        print("L4 BLOCKED:", str(exc) if isinstance(exc, Blocked) else type(exc).__name__,
              file=sys.stderr)
        return 2

if __name__ == "__main__":
    # INT-02 is a selectable heavier real-process profile; the proven
    # INT-01 foundation implementation and its default CLI remain unchanged.
    if len(sys.argv) >= 3 and sys.argv[2] == "iam-cp":
        from int02.orchestrate import main as int02_main
        sys.exit(int02_main(sys.argv[1:]))
    sys.exit(main())
