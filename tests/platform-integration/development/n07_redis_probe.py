#!/usr/bin/env python3
"""Actual run-owned TLS Redis ACL/GETDEL observation for IAM-N07 development.

Runs ONLY within the existing private DEV-01 probe container on the same
internal Docker network. No monkeypatch, local TCP fallback, logging of
password, test ciphertext, token, subject or provider body is permitted.
It proves Redis transport/custody primitives, NOT a genuine Thamani session.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import stat
import sys

RUN = "/run/dev01"
REDIS = "redis.baobab-dev.test"
CA = "/tls/ca.pem"


class Blocked(Exception):
    pass


def require(ok):
    if not ok:
        raise Blocked()


def read_state():
    run_id = os.environ.get("DEV01_RUN_ID", "")
    require(len(run_id) == 32 and all(c in "0123456789abcdef" for c in run_id))
    path = Path(RUN) / "state.json"
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o077 and info.st_nlink == 1)
    state = json.loads(path.read_bytes())
    require(state.get("run_id") == run_id
            and state.get("environment") == "development"
            and state.get("n07_profile") is True
            and state.get("lock_file") == "n07-base-lock.json"
            and state.get("phase") in {"RUNNING", "TESTED"}
            and len(state.get("secrets", {}).get("redis", "")) == 64)
    return state


def wire(*args: bytes) -> bytes:
    return (b"*" + str(len(args)).encode() + b"\r\n" +
            b"".join(b"$" + str(len(x)).encode() + b"\r\n" + x + b"\r\n"
                     for x in args))


class Redis:
    def __init__(self, *, trusted=True):
        context = ssl.create_default_context(cafile=CA if trusted else None)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        connection = socket.create_connection((REDIS, 6380), timeout=5)
        connection.settimeout(5)
        self.socket = context.wrap_socket(connection, server_hostname=REDIS)
        self.stream = self.socket.makefile("rb")

    def command(self, *args):
        self.socket.sendall(wire(*(x.encode() if isinstance(x, str) else x
                                   for x in args)))
        header = self.stream.readline(8192)
        require(header.endswith(b"\r\n") and len(header) <= 8192)
        tag, rest = header[:1], header[1:-2]
        if tag == b"+":
            return ("simple", rest)
        if tag == b"-":
            return ("error", rest)
        if tag == b"$":
            size = int(rest)
            require(-1 <= size <= 4096)
            if size == -1:
                return ("nil", None)
            raw = self.stream.read(size + 2)
            require(len(raw) == size + 2 and raw.endswith(b"\r\n"))
            return ("bulk", raw[:-2])
        if tag == b":":
            return ("integer", int(rest))
        raise Blocked()

    def close(self):
        self.stream.close()
        self.socket.close()


def live(state):
    run_id = state["run_id"]
    account = "n07"
    secret = state["secrets"]["redis"]
    probe = secrets.token_hex(16)
    key = f"thamani:bff:v1:{run_id}:n07-probe:{probe}"
    value = secrets.token_hex(32)
    conn = Redis()
    try:
        require(conn.command("AUTH", account, secret) == ("simple", b"OK"))
        require(conn.command("PING") == ("simple", b"PONG"))
        require(conn.command("SET", key, value, "NX", "EX", "20") == ("simple", b"OK"))
        require(conn.command("GET", key) == ("bulk", value.encode()))
        require(conn.command("GETDEL", key) == ("bulk", value.encode()))
        require(conn.command("GET", key) == ("nil", None))
        kind, body = conn.command("GET", "foreign:tenant:session")
        require(kind == "error" and body.startswith(b"NOPERM"))
        kind, body = conn.command("SET", f"other:bff:v1:{run_id}:foreign", "blocked")
        require(kind == "error" and body.startswith(b"NOPERM"))
    finally:
        conn.close()

    other = Redis()
    try:
        kind, body = other.command("PING")
        require(kind == "error" and body.startswith(b"NOAUTH"))
        kind, body = other.command("AUTH", account, "not-the-owner-key")
        require(kind == "error" and body.startswith(b"WRONGPASS"))
    finally:
        other.close()
    try:
        foreign_tls = Redis(trusted=False)
    except ssl.SSLCertVerificationError:
        pass
    else:
        foreign_tls.close()
        raise Blocked()

    # Run-scoped service record: no bearer, password, raw Redis value,
    # claimed provider registration, authority or legal actor.
    original = {
        "schema": "infrastructure.n07.redis-original.v1",
        "classification": "REAL_REDIS_TLS_ACL_GETDEL_OBSERVED_UNATTESTED",
        "run_id": run_id,
        "source_pins": {
            name: state["sources"][name]
            for name in ("shared", "baobab-cp", "baobab-iam", "thamani", "baobab-tms")
        },
        "redis_image": state["runtime_images"]["redis"],
        "tls_verified": True,
        "run_lease_isolated": True,
        "acl_cross_tenant_denied": True,
        "anonymous_denied": True,
        "invalid_password_denied": True,
        "untrusted_certificate_denied": True,
        "cross_worker_getdel_live": False,
        "one_use_getdel_observed": True,
        "issuer_cp_connected_accepted": False,
        "tms_native_booking_accepted": False,
        "protected_accepted": False,
    }
    path = Path(RUN) / "n07-redis-observation.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(json.dumps(original, sort_keys=True, separators=(",", ":")).encode() + b"\n")
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return original


def main():
    try:
        state = read_state()
        live(state)
        print("N07_REAL_TLS_REDIS_OBSERVATION_UNATTESTED", flush=True)
        return 0  # only this single service probe, NEVER full acceptance
    except (OSError, ValueError, TypeError, KeyError, Blocked, ssl.SSLError):
        print("N07_REDIS_RUNTIME_BLOCKED_NO_ACCEPTANCE", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
