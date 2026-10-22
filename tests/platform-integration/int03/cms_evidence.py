#!/usr/bin/env python3
"""Content-addressed, fail-closed custody for disposable INT-03 runtime evidence.

This creates no evidence, credentials or CP approval. The producing executor
must supply actual sanitized observations; sealing them never grants a PASS.
An independently downloaded retained artifact must be verified a second time
by a separate reviewer. Local SHA-256 alone is NOT external immutable storage.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = "infrastructure.int03.evidence-custody.v1"
RUN = re.compile(r"[0-9a-f]{16,32}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[a-z0-9][a-z0-9_.-]{0,80}\.json\Z")
MAX_FILE = 1_048_576
MAX_TOTAL = 10 * MAX_FILE
FORBIDDEN = {"secret", "password", "private_key", "access_token", "refresh_token",
             "client_secret", "authorization", "cookie", "api_key", "bearer",
             "id_token", "session_token"}


class Refused(RuntimeError):
    """Evidence missing, altered, secret-bearing, or outside private custody."""


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def root_dir(root):
    root = Path(root)
    state = root.lstat()
    if (root.is_symlink() or not stat.S_ISDIR(state.st_mode) or
        state.st_uid != os.getuid() or state.st_mode & 0o077):
        raise Refused("private owner-controlled evidence directory required")
    return root


def safe_file(root, name):
    if not isinstance(name, str) or not NAME.fullmatch(name) or name in (
            "manifest.json", "manifest.sha256.json"):
        raise Refused("evidence filename outside reviewed allowlist")
    file = root / name
    info = file.lstat()
    if (file.is_symlink() or not stat.S_ISREG(info.st_mode) or
        info.st_uid != os.getuid() or info.st_mode & 0o077 or
        not 1 <= info.st_size <= MAX_FILE):
        raise Refused("owner-private bounded evidence file required")
    return file


def sanitised(raw):
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError):
        raise Refused("evidence must be JSON") from None
    if not isinstance(value, dict):
        raise Refused("evidence document must be an object")
    def walk(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if not isinstance(key, str) or key.lower() in FORBIDDEN:
                    raise Refused("credential field is forbidden in retained evidence")
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif node is None or type(node) in (str, bool, int, float):
            if type(node) is str and len(node) > 4096:
                raise Refused("unbounded retained field")
        else:
            raise Refused("unsupported evidence field")
    walk(value)
    if value.get("qualified") is True or value.get("full_int03_acceptance") is True:
        raise Refused("unattested evidence cannot claim qualification")
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def existing(path):
    info = path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(info.st_mode) or
        info.st_uid != os.getuid() or info.st_mode & 0o077 or
        not 1 <= info.st_size <= MAX_FILE):
        raise Refused("sealed manifest custody differs")
    return path.read_bytes()


def exclusive(path, payload):
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    success = False
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        success = True
    finally:
        if not success:
            path.unlink(missing_ok=True)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def seal(root, names, *, run_id, sources, workflow_run=None):
    """Record actual evidence bytes without copying or interpreting results."""
    root = root_dir(root)
    if (not RUN.fullmatch(run_id) or not isinstance(sources, dict) or
        set(sources) != {"shared", "baobab-cms", "baobab-iam", "baobab-cp",
                         "nabhold", "infrastructure"} or
        not all(isinstance(v, str) and SHA.fullmatch(v) for v in sources.values()) or
        not isinstance(names, list) or not names or len(names) > 16 or
        len(set(names)) != len(names)):
        raise Refused("immutable runtime/source provenance missing")
    if workflow_run is not None and (type(workflow_run) is not int or workflow_run <= 0):
        raise Refused("invalid workflow run reference")
    if (root / "manifest.json").exists() or (root / "manifest.sha256.json").exists():
        raise Refused("evidence bundle already sealed")
    files = []
    total = 0
    for name in sorted(names):
        path = safe_file(root, name)
        raw = path.read_bytes()
        sanitised(raw)
        total += len(raw)
        if total > MAX_TOTAL:
            raise Refused("retained evidence volume exceeded")
        files.append({"name": name, "sha256": digest(raw), "bytes": len(raw)})
    manifest = {
        "schema": SCHEMA, "run_id": run_id, "source_pins": sources,
        "workflow_run_id": workflow_run, "files": files,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "custody": "LOCAL_CONTENT_HASHED_REVIEW_PENDING",
        "qualified": False, "independent_acceptance": False,
        "storage_immutability": "NOT_PROVEN_BY_LOCAL_SEAL",
    }
    body = canonical(manifest)
    exclusive(root / "manifest.json", body)
    exclusive(root / "manifest.sha256.json",
              canonical({"schema": SCHEMA, "sha256": digest(body)}))
    return manifest


def verify(root):
    """Re-read the original bytes, require exact inventory and two digests."""
    root = root_dir(root)
    raw = existing(root / "manifest.json")
    check = json.loads(existing(root / "manifest.sha256.json"))
    if (not isinstance(check, dict) or set(check) != {"schema", "sha256"} or
        check["schema"] != SCHEMA or not HEX.fullmatch(check["sha256"]) or
        digest(raw) != check["sha256"]):
        raise Refused("manifest digest mismatch")
    manifest = json.loads(raw)
    if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or
        not RUN.fullmatch(manifest.get("run_id", "")) or
        manifest.get("custody") != "LOCAL_CONTENT_HASHED_REVIEW_PENDING" or
        manifest.get("independent_acceptance") is not False or
        manifest.get("qualified") is not False or
        manifest.get("storage_immutability") != "NOT_PROVEN_BY_LOCAL_SEAL"):
        raise Refused("evidence bundle attempted to claim unsupported acceptance")
    pins = manifest.get("source_pins")
    if (not isinstance(pins, dict) or set(pins) !=
        {"shared", "baobab-cms", "baobab-iam", "baobab-cp", "nabhold", "infrastructure"} or
        not all(isinstance(v, str) and SHA.fullmatch(v) for v in pins.values())):
        raise Refused("source provenance corrupted")
    listed = manifest.get("files")
    if not isinstance(listed, list) or not 1 <= len(listed) <= 16:
        raise Refused("no complete evidence inventory")
    seen = set()
    for entry in listed:
        if (not isinstance(entry, dict) or set(entry) != {"name", "sha256", "bytes"} or
            entry["name"] in seen or not isinstance(entry["sha256"], str) or
            not HEX.fullmatch(entry["sha256"]) or
            type(entry["bytes"]) is not int):
            raise Refused("invalid evidence inventory")
        seen.add(entry["name"])
        data = safe_file(root, entry["name"]).read_bytes()
        sanitised(data)
        if len(data) != entry["bytes"] or digest(data) != entry["sha256"]:
            raise Refused("retained runtime bytes changed")
    actual = {p.name for p in root.iterdir() if p.is_file()}
    if actual != seen | {"manifest.json", "manifest.sha256.json"}:
        raise Refused("extra or missing retained files")
    return manifest


def main(argv=None):
    cli = argparse.ArgumentParser()
    sub = cli.add_subparsers(dest="command", required=True)
    create = sub.add_parser("seal")
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--source-pins", type=Path, required=True)
    create.add_argument("--file", action="append", required=True)
    create.add_argument("--workflow-run-id", type=int)
    inspect = sub.add_parser("verify")
    inspect.add_argument("--root", type=Path, required=True)
    args = cli.parse_args(argv)
    try:
        if args.command == "seal":
            pins = json.loads(args.source_pins.read_text())
            seal(args.root, args.file, run_id=args.run_id, sources=pins,
                 workflow_run=args.workflow_run_id)
        else:
            verify(args.root)
        print("INT03_CONTENT_DIGEST_VERIFIED_UNATTESTED; qualified=false")
        return 0
    except (Refused, ValueError, OSError, TypeError, KeyError):
        print("INT03_EVIDENCE_CUSTODY_REFUSED; qualified=false", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
