#!/usr/bin/env python3
"""N02 owner-only development ingress renderer; NEVER deploys or grants authority.

Takes the *same* private browser qualification profile as IAM #147. Renders
only a fixed verified NGINX template, not arbitrary proxy commands, workload
credentials or a mutable host name. The operator separately owns the private
TLS roots, certificates, host-only Kratos cookie configuration and teardown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import urllib.parse

MARKER = "__N02_FIRST_PARTY_FQDN__"
FQDN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
RUN = re.compile(r"[0-9a-f]{32}\Z")
TEMPLATE = Path(__file__).resolve().parent / "n02-ingress" / "nginx.conf.template"


class Refused(ValueError):
    """Only constant refusal codes may be emitted, never private values."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise Refused(code)


def no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        require(name not in result, "N02_DUPLICATE_PRIVATE_FIELD")
        result[name] = value
    return result


def private_profile(path: str) -> dict:
    require(isinstance(path, str) and Path(path).is_absolute(),
            "N02_PRIVATE_PROFILE_ABSOLUTE_REQUIRED")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        require(stat.S_ISREG(meta.st_mode) and meta.st_uid == os.getuid()
                and meta.st_nlink == 1 and not meta.st_mode & 0o077
                and 0 < meta.st_size <= 32768, "N02_PRIVATE_PROFILE_OWNER_REQUIRED")
        raw = stream.read(32769)
    require(len(raw) <= 32768, "N02_PRIVATE_PROFILE_TOO_LARGE")
    doc = json.loads(raw, object_pairs_hook=no_duplicates)
    require(isinstance(doc, dict), "N02_PRIVATE_PROFILE_INVALID")
    return doc


def reviewed_name(doc: dict) -> str:
    require(doc.get("schema") == "baobab.iam.n02.browser-qualification.v1"
            and doc.get("environment") == "development"
            and doc.get("require_aal2") is True
            and os.environ.get("BAOBAB_ENVIRONMENT") == "development",
            "N02_REVIEWED_DEVELOPMENT_ONLY")
    require(isinstance(doc.get("run_id"), str) and RUN.fullmatch(doc["run_id"]) is not None,
            "N02_RUN_ID_REQUIRED")
    for key in ("iam_source_sha", "shared_source_sha", "cp_source_sha",
                "infrastructure_harness_sha"):
        require(isinstance(doc.get(key), str)
                and SHA.fullmatch(doc[key]) is not None, "N02_SOURCE_PIN_REQUIRED")
    estate = doc.get("bff_origin")
    kratos = doc.get("kratos_origin")
    hydra = doc.get("hydra_origin")
    require(isinstance(estate, str) and isinstance(kratos, str)
            and isinstance(hydra, str), "N02_ORIGIN_REQUIRED")
    parsed = urllib.parse.urlsplit(estate)
    h = urllib.parse.urlsplit(hydra)
    require(parsed.scheme == "https" and parsed.hostname is not None
            and parsed.port is None and not parsed.username and not parsed.password
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment
            and estate.rstrip("/") == kratos.rstrip("/")
            and h.scheme == "https" and h.hostname is not None
            and h.netloc != parsed.netloc
            and not h.username and not h.password and not h.query and not h.fragment
            and h.path in ("", "/"), "N02_HOST_ONLY_KRATOS_AND_HYDRA_ISOLATION_REQUIRED")
    fqdn = parsed.hostname
    require(len(fqdn) <= 253 and FQDN.fullmatch(fqdn) is not None
            and fqdn == parsed.netloc and fqdn == fqdn.lower(),
            "N02_REVIEWED_FIRST_PARTY_FQDN_REQUIRED")
    return fqdn


def render(doc: dict) -> bytes:
    fqdn = reviewed_name(doc)
    template = TEMPLATE.read_text(encoding="utf-8")
    require(template.count(MARKER) >= 5, "N02_INGRESS_TEMPLATE_DRIFT")
    rendered = template.replace(MARKER, fqdn)
    require(MARKER not in rendered
            and "proxy_pass https://127.0.0.1:9443;" in rendered
            and rendered.count("proxy_ssl_verify on;") == 3
            and "proxy_pass http://127.0.0.1:3000;" in rendered
            and "/sessions/whoami" in rendered
            and "ssl_reject_handshake on;" in rendered,
            "N02_INGRESS_TLS_OR_ROUTE_DRIFT")
    return rendered.encode("utf-8")


def publish_private(directory: str, configuration: bytes) -> str:
    root = Path(directory)
    require(root.is_absolute() and not root.is_symlink(), "N02_INGRESS_OUTPUT_PATH_REQUIRED")
    info = root.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and not info.st_mode & 0o077, "N02_INGRESS_PRIVATE_OUTPUT_REQUIRED")
    destination = root / "nginx.conf"
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(configuration)
        stream.flush()
        os.fsync(stream.fileno())
    folder = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(folder)
    finally:
        os.close(folder)
    return hashlib.sha256(configuration).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="owner-private current N02 browser profile")
    parser.add_argument("--output-dir", required=True, help="existing owner-private 0700 directory")
    args = parser.parse_args()
    try:
        configuration = render(private_profile(args.profile))
        digest = publish_private(args.output_dir, configuration)
    except (Refused, OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        code = str(exc) if isinstance(exc, Refused) else "N02_INGRESS_OR_PROFILE_UNAVAILABLE"
        if not re.fullmatch(r"N02_[A-Z_]+", code):
            code = "N02_INGRESS_OR_PROFILE_UNAVAILABLE"
        print("N02_INGRESS_BLOCKED " + code)
        return 2
    # No hostnames, profile contents, user identities or secrets in CI logs.
    print("N02_INGRESS_SOURCE_RENDERED_UNATTESTED sha256=" + digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
