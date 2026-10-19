#!/usr/bin/env python3
"""Prepare the private INT-03 identity-smoke handoff, without provisioning.

Infrastructure owns this mechanical lab format, not identity or entitlement.
All inputs are operator declarations until the actual processes are observed.
No network call, token issuance, CP mutation or acceptance decision occurs.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import tempfile
import uuid

SOURCES = {"infrastructure", "baobab-iam", "baobab-cp", "shared", "nabhold"}
SCOPES = ["openid", "basic", "actor-type-human", "authority:self"]
ORIGIN = "https://nabhold.int03.test"
ISSUER = "https://iam.int02.test/realms/baobab"
CP = "https://cp.int02.test"
CLIENT = "nabhold-int03"
USERNAME = "l4-int03-human"
LIMIT = 32768


class Refused(Exception):
    """Deliberately excludes supplied credentials, paths and JSON values."""


def require(condition):
    if not condition:
        raise Refused("INT-03 handoff refused; no acceptance claimed")


def read_file(path, *, private=True):
    """One bounded descriptor prevents final-component symlink/FIFO races.

    Inputs belong to the invoking owner. The caller must also protect its
    parent directories; never run this against shared, attacker-writable paths.
    CA certificates are public but cannot be writable by another user.
    """
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                and info.st_nlink == 1 and 0 < info.st_size <= LIMIT)
        require(info.st_mode & (0o077 if private else 0o022) == 0)
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(LIMIT + 1)
        require(0 < len(data) <= LIMIT)
        return data.decode("utf-8", errors="strict")
    finally:
        os.close(fd)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def document(text):
    return json.loads(text, object_pairs_hook=unique)


def inputs(value):
    """Closed lab-only input: real tenants/staging endpoints are not options.

    The supplied UUID is an EXPECTED previously registered synthetic Principal,
    not a newly fabricated identity or a verified CP observation. The actual
    BFF smoke must establish its current issuer/subject mapping independently.
    """
    require(type(value) is dict and set(value) == {
        "synthetic", "sources", "principal_id", "username", "password", "ca_file"})
    require(value["synthetic"] is True and type(value["sources"]) is dict
            and set(value["sources"]) == SOURCES)
    require(all(type(v) is str and re.fullmatch(r"[0-9a-f]{40}", v)
                for v in value["sources"].values()))
    principal = value["principal_id"]
    require(type(principal) is str and str(uuid.UUID(principal)) == principal
            and uuid.UUID(principal).int != 0)
    require(value["username"] == USERNAME and type(value["password"]) is str
            and 16 <= len(value["password"]) <= 4096)
    # Dotenv is never shell sourced. Refusing quotes/controls makes every
    # generated single-quoted value unambiguous in Node's literal dotenv parser.
    require(not re.search(r"['\x00-\x1f\x7f]", value["password"]))
    require(type(value["ca_file"]) is str and Path(value["ca_file"]).is_absolute())
    return value


def client_fixture(template, secret):
    """Only an isolated clone of IAM's dormant human profile is enabled.

    The committed product client is never edited. No scopes, mappers, roles,
    audiences, admin actions or authentication-flow overrides may be added.
    This document has no effect until an authorised disposable-lab operator
    provisions it; it is never an activation input for protected staging.
    """
    expected = {
        "clientId", "name", "description", "enabled", "publicClient", "bearerOnly",
        "serviceAccountsEnabled", "protocol", "directAccessGrantsEnabled",
        "implicitFlowEnabled", "standardFlowEnabled", "attributes",
        "authenticationFlowBindingOverrides", "defaultClientScopes",
        "optionalClientScopes", "redirectUris", "webOrigins"}
    require(type(template) is dict and set(template) == expected)
    require(template["clientId"] == "nabhold-executive"
            and template["protocol"] == "openid-connect"
            and template["standardFlowEnabled"] is True)
    require(all(template[k] is False for k in (
        "enabled", "publicClient", "bearerOnly", "serviceAccountsEnabled",
        "directAccessGrantsEnabled", "implicitFlowEnabled")))
    require(template["defaultClientScopes"] == SCOPES
            and template["authenticationFlowBindingOverrides"] == {})
    require(all(template[k] == [] for k in ("optionalClientScopes", "redirectUris", "webOrigins")))
    require(template["attributes"] == {
        "pkce.code.challenge.method": "S256",
        "oauth2.device.authorization.grant.enabled": "false",
        "backchannel.logout.session.required": "true",
        "backchannel.logout.revoke.offline.tokens": "false"})
    result = dict(template)
    result.update(clientId=CLIENT, name="Disposable INT-03 confidential BFF",
                  description="Synthetic integration only; no executive or tenant authority.",
                  enabled=True, secret=secret, fullScopeAllowed=False,
                  redirectUris=[ORIGIN + "/api/auth/callback"])
    return result


def environment(value, destination, client_secret, redis_password, key, epoch, ca):
    """Match Nabhold's existing consumer format; do not invent a CP endpoint."""
    return {
        "NABHOLD_INTEGRATION_PROFILE": "keycloak-identity-smoke",
        "NABHOLD_INTEGRATION_SYNTHETIC": "true",
        **{f"NABHOLD_INTEGRATION_{alias}_SHA": value["sources"][repo]
           for alias, repo in (("INFRASTRUCTURE", "infrastructure"), ("IAM", "baobab-iam"),
                               ("CP", "baobab-cp"), ("SHARED", "shared"))},
        "NEXT_PUBLIC_SITE_URL": ORIGIN, "NABHOLD_OIDC_ENABLED": "true",
        "NABHOLD_OIDC_ENVIRONMENT": "integration", "NABHOLD_OIDC_ORIGIN": ORIGIN,
        "NABHOLD_OIDC_ISSUER": ISSUER, "NABHOLD_OIDC_CLIENT_ID": CLIENT,
        "NABHOLD_OIDC_CLIENT_SECRET": client_secret, "NABHOLD_OIDC_ID_TOKEN_ALGORITHM": "RS256",
        "NABHOLD_OIDC_INTROSPECTION_ENDPOINT": ISSUER + "/protocol/openid-connect/token/introspect",
        "NABHOLD_OIDC_CP_ORIGIN": CP, "BAOBAB_CONTROL_PLANE_API_URL": CP,
        "NODE_EXTRA_CA_CERTS": str(destination / "prepared" / "ca.pem"),
        "NABHOLD_BFF_STORE_ENABLED": "true", "NABHOLD_BFF_REDIS_HOST": "redis.int03.test",
        "NABHOLD_BFF_REDIS_PORT": "6379", "NABHOLD_BFF_REDIS_USERNAME": "nabhold",
        "NABHOLD_BFF_REDIS_PASSWORD": redis_password, "NABHOLD_BFF_REDIS_CA_PEM": ca,
        "NABHOLD_BFF_STORE_KEYS_JSON": json.dumps({"run": key}, separators=(",", ":")),
        "NABHOLD_BFF_STORE_ACTIVE_KEY": "run", "NABHOLD_BFF_STORE_EPOCH": epoch,
        "NABHOLD_INTEGRATION_USERNAME": USERNAME, "NABHOLD_INTEGRATION_PASSWORD": value["password"],
        "NABHOLD_INTEGRATION_PRINCIPAL_ID": value["principal_id"],
        "NABHOLD_CONTENT_DEV_FALLBACK": "false", "NABHOLD_DASHBOARD_PREVIEW": "false",
        "NABHOLD_CONTENT_SOURCE": "", "NABHOLD_CANONICAL_HOST": "",
        "NABHOLD_RELEASE_R0": "true", "NABHOLD_RELEASE_R1": "false",
        "NABHOLD_RELEASE_R2": "false", "NABHOLD_RELEASE_R3": "false"}


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(value)
        out.flush()
        os.fsync(out.fileno())


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def prepare(value, template, ca, destination):
    value = inputs(value)
    require(destination.is_absolute() and not destination.exists() and not destination.is_symlink())
    parent = destination.parent
    info = parent.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and info.st_mode & 0o077 == 0)
    # This is a public trust bundle from the lab, not a CA issuer/private key.
    # Node's consumer additionally validates X.509 CA extensions at launch;
    # neither this PEM envelope nor any hash proves that live TLS succeeds.
    certs = re.findall(r"-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----", ca)
    require(bool(certs) and not re.sub(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", "", ca,
                                    flags=re.S).strip() and "'" not in ca and len(ca) < 16384)
    client_secret, redis_password = secrets.token_hex(32), secrets.token_hex(32)
    key = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    epoch = "int03-" + secrets.token_hex(8)
    client = client_fixture(template, client_secret)
    env = environment(value, destination, client_secret, redis_password, key, epoch, ca)
    require(all(not re.search(r"['\x00\r]", v) for v in env.values()))
    # A newly created staging directory cannot replace a prior completed run.
    # os.rename replaces an empty directory on POSIX, so reserve the final
    # directory first and publish the bundle beneath it. Existing destinations
    # always fail, including an empty directory or dangling symlink.
    destination.mkdir(mode=0o700)
    try:
        pending = Path(tempfile.mkdtemp(prefix=".preparing-", dir=destination))
        write_private(pending / "ca.pem", ca)
        write_private(pending / "integration.env", "".join(f"{k}='{v}'\n" for k, v in env.items()))
        write_private(pending / "client.json", json.dumps(client, indent=2) + "\n")
        # Only the exact per-run key prefix is accessible. No command category,
        # EVAL, CONFIG, key scanning or other epoch's sessions are permitted.
        digest = hashlib.sha256(redis_password.encode()).hexdigest()
        write_private(pending / "users.acl", "user default off\n"
                      f"user nabhold on #{digest} ~nabhold:bff:v1:{epoch}:* "
                      "+set +get +getdel +del +ping +hello +client|setinfo +client|setname\n")
        manifest = {"schema": "infrastructure.int03.handoff.v1", "state": "PREPARED_NOT_PROVISIONED",
                    "profile": "keycloak-identity-smoke", "synthetic": True,
                    "declared_sources": value["sources"], "runtime_attested": False,
                    "identity_verified": False, "acceptance_claimed": False,
                    "protected_staging_accepted": False, "production_authorized": False}
        write_private(pending / "manifest.json", json.dumps(manifest, indent=2) + "\n")
        sync_directory(pending)
        os.rename(pending, destination / "prepared")
        sync_directory(destination)
        sync_directory(parent)
    except BaseException:
        # Preserve no partly generated credential bundle. This function owns
        # only the brand-new destination it created, never an existing path.
        shutil.rmtree(destination)
        raise
    return destination / "prepared"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--iam-template", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        value = inputs(document(read_file(args.inputs)))
        template = document(read_file(args.iam_template, private=False))
        prepare(value, template, read_file(value["ca_file"], private=False), Path(args.output))
    except (OSError, ValueError, TypeError, KeyError, Refused):
        print("INT-03 handoff refused; no acceptance claimed", file=__import__("sys").stderr)
        return 2
    print("INT-03 handoff prepared privately; services, identity and acceptance NOT VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
