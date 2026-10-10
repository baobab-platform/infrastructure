#!/usr/bin/env python3
"""PEO-02F: prove *real* governed CP -> outbox -> IAM -> Subscriptions -> inbox.

This is deliberately different from the direct-to-Subscriptions protocol
acceptance. It suspends one reviewed, synthetic, ACTIVE sponsorship through
CP's independent human governance API, then observes both databases through
separate read-only TLS connections. No event is forged or inserted by this
script, and no user/entity is onboarded.

Requires a short-lived IAM OIDC *human* reviewer token issued out-of-band by
a genuinely authenticated admin, plus two IAM OAuth client_credentials tokens
for separate engine audiences. The actual relay uses its deployed IAM-managed
token; the subscriptions inbox records the verified producer client ID.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit, unquote
import uuid

from peo_synthetic_staging import OPENER, oauth, require, reviewed_https
from urllib.error import HTTPError
from urllib.request import Request

EVENT_TYPE = "com.baobab-platform.control-plane.founding-sponsorship.suspended.v1"
EVENT_SOURCE = "urn:baobab-platform:service:baobab-cp"
SCHEMA = ("https://contracts.baobab-platform.com/admission/v2/"
          "founding-lifecycle-events.schema.json#/$defs/SponsorshipSuspended")


def uid(value: str) -> str:
    return str(uuid.UUID(value))


def canonical_digest(envelope: dict) -> str:
    return hashlib.sha256(json.dumps(envelope, sort_keys=True,
                                     separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def readonly_connection(uri: str, ca_file: str, permitted_hosts: set[str]) -> dict[str, str]:
    parsed = urlsplit(uri)
    if (parsed.scheme != "postgresql" or not parsed.hostname
            or parsed.hostname not in permitted_hosts or not parsed.username
            or not parsed.password or not parsed.path.strip("/")
            or parsed.query or parsed.fragment):
        raise RuntimeError("staging evidence DB URL is not a reviewed PostgreSQL read-only credential")
    if not Path(ca_file).is_file() or not Path(ca_file).is_absolute():
        raise RuntimeError("staging read-only evidence requires a trusted TLS CA file")
    return {
        "PGHOST": parsed.hostname,
        "PGPORT": str(parsed.port or 5432),
        "PGDATABASE": unquote(parsed.path.lstrip("/")),
        "PGUSER": unquote(parsed.username),
        "PGPASSWORD": unquote(parsed.password),
        "PGSSLMODE": "verify-full",
        "PGSSLROOTCERT": ca_file,
        "PGCONNECT_TIMEOUT": "5",
        "PGAPPNAME": "peo-02f-staging-proof",
    }


def sql_one(sql: str, connection: dict[str, str]) -> dict | None:
    # SQL is assembled only with UUID strings validated by uuid.UUID().
    # Read-only credentials and a read-only transaction are BOTH required.
    proc = subprocess.run(
        ["psql", "-w", "-X", "-A", "-t", "-q", "-v", "ON_ERROR_STOP=1"],
        input=("BEGIN READ ONLY;\n" + sql + "\nCOMMIT;\n").encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, **connection}, timeout=15, check=False)
    if proc.returncode:
        # Do not expose DB credentials, DSN, query contents or internal host
        # names from psql errors in CI logs.
        raise RuntimeError("reviewed staging read-only SQL evidence query failed")
    rows = [line for line in proc.stdout.decode().splitlines()
            if line.strip().startswith("{")]
    if not rows:
        return None
    if len(rows) != 1:
        raise RuntimeError("staging SQL returned ambiguous cross-engine evidence")
    value = json.loads(rows[0])
    if not isinstance(value, dict):
        raise RuntimeError("SQL evidence shape invalid")
    return value


def initial_fixture(cp: dict[str, str], grant: str) -> dict:
    row = sql_one(f"""
      SELECT row_to_json(r) FROM (
        SELECT s.sponsorship_id::text AS grant_id,
               s.operating_organisation_id::text AS organisation_id,
               s.sponsor_organisation_id::text AS sponsor_id,
               s.proposed_by::text, s.approved_by::text,
               s.status, s.scope, s.authority_basis_reference,
               s.evidence_references, s.effective_from, s.effective_to,
               op.display_name AS operating_name,
               sponsor.display_name AS sponsor_name
        FROM admission.founding_group_sponsorship s
        JOIN registry.organisation_profile op
          ON op.canonical_entity_id=s.operating_organisation_id
        JOIN registry.organisation_profile sponsor
          ON sponsor.canonical_entity_id=s.sponsor_organisation_id
        WHERE s.sponsorship_id='{grant}'::uuid
          AND s.status='ACTIVE' AND s.scope='INTERNAL_GROUP_ADMISSION'
          AND s.effective_from<=clock_timestamp()
          AND s.effective_to>clock_timestamp()
      ) r;""", cp)
    if row is None:
        raise RuntimeError("no approved, current ACTIVE staging sponsorship fixture")
    if not (row["operating_name"].startswith("Synthetic PEO ")
            and row["sponsor_name"].startswith("Synthetic PEO ")
            and row["authority_basis_reference"].startswith("staging/peo-relay/")
            and row["evidence_references"]
            and all(str(e).startswith("staging/peo-relay/")
                    for e in row["evidence_references"])
            and row["proposed_by"] != row["approved_by"]):
        raise RuntimeError("sponsorship fixture does not have independently approved synthetic-only provenance")
    return row



def final_governance_status(cp: dict[str, str], grant: str) -> str:
    row = sql_one(f"""
      SELECT row_to_json(r) FROM (
        SELECT status FROM admission.founding_group_sponsorship
        WHERE sponsorship_id='{grant}'::uuid
      ) r;""", cp)
    if row is None:
        raise RuntimeError("the governed synthetic sponsorship disappeared")
    return str(row["status"])


def cp_outbox(cp: dict[str, str], grant: str, correlation: str) -> dict | None:
    return sql_one(f"""
      SELECT row_to_json(r) FROM (
        SELECT id::text AS outbox_id, aggregate_id, event_type,
               aggregate_version, correlation_id::text,
               occurred_at, published_at, publish_attempts, last_error,
               payload
        FROM messaging.outbox
        WHERE aggregate_type='founding_group_sponsorship'
          AND aggregate_id='{grant}'
          AND correlation_id='{correlation}'::uuid
          AND event_type='{EVENT_TYPE}'
      ) r;""", cp)


def subscriptions_inbox(sub: dict[str, str], event_id: str) -> dict | None:
    return sql_one(f"""
      SELECT row_to_json(r) FROM (
        SELECT event_id::text, event_type, event_source,
               aggregate_id::text, payload_sha256,
               received_by_client_id, received_at, processed_at,
               envelope
        FROM billing.founding_event_inbox
        WHERE event_id='{event_id}'::uuid
      ) r;""", sub)


def timestamp(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(dt.timezone.utc)


def verify_delivery(outbox: dict, inbox: dict, *, grant: str,
                    correlation: str, expected_client: str) -> dict:
    event = outbox.get("payload")
    remote = inbox.get("envelope")
    if not isinstance(event, dict) or not isinstance(remote, dict):
        raise ValueError("both engines must persist canonical CloudEvents JSON")
    event_id = uid(event["id"])
    if (uid(outbox["correlation_id"]) != correlation
            or uid(event["correlationid"]) != correlation
            or uid(inbox["event_id"]) != event_id
            or outbox["aggregate_id"] != grant
            or uid(inbox["aggregate_id"]) != grant
            or outbox["event_type"] != EVENT_TYPE
            or inbox["event_type"] != EVENT_TYPE
            or event["type"] != EVENT_TYPE
            or inbox["event_source"] != EVENT_SOURCE
            or event["source"] != EVENT_SOURCE
            or event["subject"] != "founding-governance/" + grant
            or event["dataschema"] != SCHEMA
            or event["data"]["sponsorship_id"] != grant
            or event["data"]["status"] != "SUSPENDED"
            or outbox.get("publish_attempts", 0) < 1
            or not outbox.get("published_at")
            or not inbox.get("received_at") or not inbox.get("processed_at")
            or inbox.get("received_by_client_id") != expected_client):
        raise ValueError("producer publication / verified workload identity / recipient fields do not converge")
    producer_hash = canonical_digest(event)
    consumer_hash = canonical_digest(remote)
    if producer_hash != consumer_hash or event != remote:
        raise ValueError("publisher and subscriber persisted different canonical envelopes")
    actual_wire_hash = inbox.get("payload_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", actual_wire_hash):
        raise ValueError("subscriber missing SHA-256 digest of authenticated HTTP body")
    created = timestamp(outbox["occurred_at"])
    received = timestamp(inbox["received_at"])
    published = timestamp(outbox["published_at"])
    processed = timestamp(inbox["processed_at"])
    if not (created <= received <= published and received <= processed):
        raise ValueError("durable receiver must record before CP marks event published")
    if (published - created).total_seconds() > 180:
        raise ValueError("delayed delivery exceeded bounded staging proof window")
    return {
        "event_id": event_id,
        "aggregate_id": grant,
        "correlation_id": correlation,
        "event_type": EVENT_TYPE,
        "producer_outbox_id": uid(outbox["outbox_id"]),
        "producer_occurred_at": outbox["occurred_at"],
        "consumer_received_at": inbox["received_at"],
        "consumer_processed_at": inbox["processed_at"],
        "producer_published_at": outbox["published_at"],
        "producer_attempts": outbox["publish_attempts"],
        "verified_iam_workload_client_id": inbox["received_by_client_id"],
        "cross_engine_canonical_sha256": producer_hash,
        "receiver_wire_sha256": actual_wire_hash,
        "result": "PROVED",
    }


def transition(cp_url: str, reviewer_token: str, grant: str, correlation: str) -> None:
    body = {
        "reason": "Independently authorised synthetic PEO relay staging acceptance transition",
        "evidence_reference": "staging/peo-relay/" + correlation,
        "expected_status": "ACTIVE",
    }
    url = cp_url + "/v2/founding-governance/sponsorships/" + grant + "/suspend"
    request = Request(
        url, data=json.dumps(body, separators=(",", ":")).encode(), method="POST",
        headers={
            "Authorization": "Bearer " + reviewer_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": "peo-relay-" + correlation,
            "X-Correlation-ID": correlation,
            "Cache-Control": "no-store",
        })
    try:
        with OPENER.open(request, timeout=12) as result:
            response_status = result.status
            raw = result.read(8192)
    except HTTPError as error:
        # Do not echo the reviewer bearer token or private deployment URL.
        raise RuntimeError(f"independently authorised CP governance command rejected: HTTP {error.code}") from None
    receipt = json.loads(raw)
    if (response_status != 200 or receipt.get("target_id") != grant
            or receipt.get("kind") != "SPONSORSHIP"
            or receipt.get("status") != "SUSPENDED"):
        raise RuntimeError("CP did not acknowledge exact governed synthetic suspension")


def check_iam() -> dict:
    hosts = set(require("PEO_STAGING_ALLOWED_HOSTS").split(","))
    token_endpoint = reviewed_https(require("PEO_STAGING_IAM_TOKEN_URL"), hosts)
    # Proof that IAM really issues the two independently scoped workload
    # credentials; never print or persist either access token.
    a = oauth(token_endpoint, require("PEO_STAGING_SUBSCRIPTIONS_CLIENT_ID"),
              require("PEO_STAGING_SUBSCRIPTIONS_CLIENT_SECRET"),
              require("PEO_STAGING_CP_AUDIENCE"), "subscription:internal-authority")
    b = oauth(token_endpoint, require("PEO_STAGING_CP_CLIENT_ID"),
              require("PEO_STAGING_CP_CLIENT_SECRET"),
              require("PEO_STAGING_BILLING_AUDIENCE"), "billing:observe")
    if not a or not b or a == b:
        raise RuntimeError("two independent IAM workload token issuances were not demonstrated")
    return {"oauth_iam_issued_tokens": "PASS",
            "audiences_distinct": require("PEO_STAGING_CP_AUDIENCE") !=
                                  require("PEO_STAGING_BILLING_AUDIENCE")}


def main() -> int:
    if require("PEO_ACCEPTANCE_ENVIRONMENT") != "staging":
        raise RuntimeError("PEO-02F real delivery proof permitted only in staging")
    if require("PEO_STAGING_RELAY_MUTATION_APPROVED") != "true":
        raise RuntimeError("human reviewer has not approved one-time synthetic grant suspension")
    hosts = set(require("PEO_STAGING_ALLOWED_HOSTS").split(","))
    cp_url = reviewed_https(require("PEO_STAGING_CP_BASE_URL"), hosts)
    ca_file = require("PEO_STAGING_EVIDENCE_DB_CA_FILE")
    db_hosts = set(require("PEO_STAGING_ALLOWED_DB_HOSTS").split(","))
    cp = readonly_connection(require("PEO_STAGING_CP_EVIDENCE_DB_URL"), ca_file, db_hosts)
    sub = readonly_connection(require("PEO_STAGING_SUB_EVIDENCE_DB_URL"), ca_file, db_hosts)
    grant = uid(require("PEO_STAGING_SYNTHETIC_GRANT_UUID"))
    reviewer_file = Path(require("PEO_STAGING_HUMAN_REVIEWER_TOKEN_FILE"))
    if not reviewer_file.is_file() or not reviewer_file.is_absolute():
        raise RuntimeError("short-lived IAM-issued human reviewer token file is absent")
    reviewer_token = reviewer_file.read_text().strip()
    if not reviewer_token or len(reviewer_token) > 8192 or any(c.isspace() for c in reviewer_token):
        raise RuntimeError("invalid short-lived human reviewer credential")
    if cp["PGHOST"] == sub["PGHOST"] and cp["PGDATABASE"] == sub["PGDATABASE"]:
        raise RuntimeError("producer and consumer evidence must use independently owned databases")
    iam_proof = check_iam()
    if not iam_proof["audiences_distinct"]:
        raise RuntimeError("workload tokens must be minted for distinct CP and Subscriptions audiences")
    fixture = initial_fixture(cp, grant)
    correlation = str(uuid.uuid4())
    report = {
        "status": "IN_PROGRESS",
        "environment": "staging",
        "real_iam": iam_proof,
        "governed_fixture_id": grant,
        "correlation_id": correlation,
        "human_authz_enforced_by": "Control Plane admission:decide",
        "expected_workload_client_id": require("PEO_STAGING_CP_CLIENT_ID"),
        "github_run_id": os.getenv("GITHUB_RUN_ID", "operator-local"),
        "deployment": {
            "cp_revision": require("PEO_STAGING_CP_DEPLOYED_REVISION"),
            "subscriptions_revision": require("PEO_STAGING_SUB_DEPLOYED_REVISION"),
        },
        "governance": {"operation": "SUSPEND", "independent_maker_checker": True,
                       "synthetic_marker_verified": True, "status_before": fixture["status"]},
        "cross_engine": None,
    }
    evidence_dir = Path("peo-acceptance-evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / "cp-subscriptions-relay.json"
    # This is a one-way human-controlled transition. Always leave an INCOMPLETE
    # artifact if a request is accepted but later transport evidence fails.
    try:
        transition(cp_url, reviewer_token, grant, correlation)
        if final_governance_status(cp, grant) != "SUSPENDED":
            raise RuntimeError("Control Plane database does not reflect independent suspension")
        report["governance"]["status_after"] = "SUSPENDED"
        report["governance"]["committed_in_cp_database"] = True
        report["status"] = "PENDING_DURABLE_DELIVERY"
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            outbox = cp_outbox(cp, grant, correlation)
            if outbox and outbox.get("published_at"):
                event_id = uid(outbox["payload"]["id"])
                inbox = subscriptions_inbox(sub, event_id)
                if inbox:
                    report["cross_engine"] = verify_delivery(
                        outbox, inbox, grant=grant, correlation=correlation,
                        expected_client=report["expected_workload_client_id"])
                    report["status"] = "PROVED"
                    break
            time.sleep(3)
        if report["status"] != "PROVED":
            raise RuntimeError("bounded polling did not prove CP outbox / authenticated Subscriptions inbox convergence")
        return 0
    finally:
        evidence_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
        # No tokens, passwords, names, user principals or raw payloads are
        # stored in the artifact. Human review must still certify this proof.


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("PEO-02F independently governed staging relay proof failed:", str(exc), file=sys.stderr)
        sys.exit(1)
