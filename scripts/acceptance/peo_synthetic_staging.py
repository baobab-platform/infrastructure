#!/usr/bin/env python3
"""PEO-02E / PEO-03C controlled staging proof using *real* IAM OAuth workload credentials.

Do not replay a synthetic access token, use a hand-created JWT, disable TLS,
or substitute a hard-coded identity: the actual IAM issuer must mint both
client_credentials access tokens for their distinct API audiences.
Only synthetic, explicitly approved staging fixtures may be used.
"""
from __future__ import annotations

import base64
import datetime
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

MAX_RESPONSE = 65536

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("redirect forbidden for bearer-authenticated acceptance")


OPENER = urllib.request.build_opener(NoRedirect())

def require(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        raise RuntimeError(f"required staging input {key} is absent")
    return value


def reviewed_https(url: str, hosts: set[str]) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment or parsed.hostname not in hosts:
        raise RuntimeError("staging endpoint must be HTTPS and on the exact reviewed hostname allow-list")
    return url.rstrip("/")


def call(url: str, *, method: str = "GET", token: str | None = None,
         json_body: dict | None = None, form: dict | None = None) -> tuple[int, dict]:
    headers = {"Accept": "application/json", "Cache-Control": "no-store"}
    body = None
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    if json_body is not None:
        body = json.dumps(json_body, separators=(",", ":")).encode()
        headers["Content-Type"] = "application/cloudevents+json"
    if form is not None:
        body = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with OPENER.open(req, timeout=8) as response:
            status, raw = response.status, response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise RuntimeError("upstream response exceeds bound")
    try:
        decoded = json.loads(raw)
    except ValueError:
        decoded = {}
    return status, decoded if isinstance(decoded, dict) else {}


def oauth(url: str, client_id: str, client_secret: str, audience: str, scope: str) -> str:
    # OAuth RFC 6749 client_credentials with actual IAM server response.
    if not client_id or not client_secret or not audience:
        raise RuntimeError("no IAM workload identity configured")
    basic = base64.b64encode((client_id + ":" + client_secret).encode()).decode()
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "scope": scope,
            "audience": audience,
        }).encode(), method="POST", headers={
            "Authorization": "Basic " + basic,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        })
    try:
        with OPENER.open(request, timeout=8) as response:
            result = json.loads(response.read(MAX_RESPONSE))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"staging IAM token request refused: HTTP {e.code}") from None
    token = result.get("access_token")
    if not isinstance(token, str) or not token or result.get("token_type", "").lower() != "bearer":
        raise RuntimeError("IAM did not issue OAuth bearer access token")
    return token


def assert_check(check: bool, detail: str) -> None:
    if not check:
        raise RuntimeError(detail)


def main() -> int:
    if require("PEO_ACCEPTANCE_ENVIRONMENT") != "staging":
        raise RuntimeError("this acceptance cannot run outside staging")
    hosts = set(require("PEO_STAGING_ALLOWED_HOSTS").split(","))
    iam = reviewed_https(require("PEO_STAGING_IAM_TOKEN_URL"), hosts)
    cp = reviewed_https(require("PEO_STAGING_CP_BASE_URL"), hosts)
    subs = reviewed_https(require("PEO_STAGING_SUBSCRIPTIONS_BASE_URL"), hosts)
    tenant = require("PEO_SYNTHETIC_TENANT_ID")
    subscription = require("PEO_SYNTHETIC_PRODUCT_SUBSCRIPTION_ID")
    classification = require("PEO_SYNTHETIC_CLASSIFICATION_REFERENCE")
    assert_check(tenant.startswith("tn_") and subscription.startswith("sub_"),
                 "staging fixture IDs are not canonical")
    cp_token = oauth(iam, require("PEO_STAGING_SUBSCRIPTIONS_CLIENT_ID"),
                     require("PEO_STAGING_SUBSCRIPTIONS_CLIENT_SECRET"),
                     require("PEO_STAGING_CP_AUDIENCE"), "subscription:internal-authority")
    billing_token = oauth(iam, require("PEO_STAGING_CP_CLIENT_ID"),
                          require("PEO_STAGING_CP_CLIENT_SECRET"),
                          require("PEO_STAGING_BILLING_AUDIENCE"), "billing:observe")
    report: dict = {
        "environment": "staging",
        "real_iam_client_credentials": True,
        "synthetic_only": True,
        "tests": {},
        "control_plane_relay_to_inbox": "NOT_PROVED_BY_THIS_SCRIPT",
    }
    path = (cp + "/internal/subscriptions/v1/tenants/" + urllib.parse.quote(tenant, safe="")
            + "/product-subscriptions/" + urllib.parse.quote(subscription, safe="")
            + "/internal-authority?classification_reference="
            + urllib.parse.quote(classification, safe=""))
    status, response = call(path, token=cp_token)
    assert_check(status == 200 and response.get("eligible") is True
                 and response.get("tenant_id") == tenant
                 and response.get("product_subscription_id") == subscription
                 and response.get("classification_reference") == classification,
                 "current valid synthetic sponsorship did not yield tenant-bound positive PDP")
    report["tests"]["current_internal_authority"] = "PASS"
    status, response = call(path + "-invalid", token=cp_token)
    assert_check(status == 200 and response.get("eligible") is False,
                 "stale classification reference was not denied")
    report["tests"]["stale_classification_denial"] = "PASS"

    event_id = str(uuid.uuid4())
    grant = str(uuid.uuid4())
    operating = str(uuid.uuid4())
    event = {
        "specversion": "1.0", "id": event_id,
        "time": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "datacontenttype": "application/json", "baobabscope": "platform",
        "correlationid": str(uuid.uuid4()),
        "source": "urn:baobab-platform:service:baobab-cp",
        "type": "com.baobab-platform.control-plane.founding-sponsorship.suspended.v1",
        "subject": "founding-governance/" + grant,
        "dataschema": "https://contracts.baobab-platform.com/admission/v2/"
                      "founding-lifecycle-events.schema.json#/$defs/SponsorshipSuspended",
        "data": {"sponsorship_id": grant,
                 "operating_organisation_id": operating, "status": "SUSPENDED"},
    }
    route = subs + "/internal/v1/founding-lifecycle-events"
    status, ack = call(route, method="POST", token=billing_token, json_body=event)
    assert_check(status == 202 and ack.get("event_id") == event_id and
                 ack.get("durably_received") is True, "first durable delivery not ACKed")
    report["tests"]["iam_authenticated_first_delivery"] = "PASS"
    status, ack = call(route, method="POST", token=billing_token, json_body=event)
    assert_check(status == 200 and ack.get("replayed") is True,
                 "durable inbox did not deduplicate exact replay")
    report["tests"]["idempotent_redelivery"] = "PASS"
    changed = json.loads(json.dumps(event))
    changed["data"]["operating_organisation_id"] = str(uuid.uuid4())
    status, _ = call(route, method="POST", token=billing_token, json_body=changed)
    assert_check(status in (409, 422), "changed same-ID event replay was accepted")
    report["tests"]["tampered_replay_denial"] = "PASS"
    status, _ = call(route, method="POST", token=cp_token, json_body=event)
    assert_check(status in (401, 403), "CP-audience billing workload token crossed event-ingress audience")
    report["tests"]["wrong_audience_denial"] = "PASS"
    # Do not pretend this synthetic direct delivery proves the CP outbox
    # relay itself: that requires seeded governance mutation, a real CP
    # outbox row, and after-ACK published_at evidence via staging operations.
    directory = Path("peo-acceptance-evidence")
    directory.mkdir(exist_ok=True)
    (directory / "staging-workload-receipt.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"environment": "staging", "authenticated_checks": report["tests"],
                      "relay_proof": report["control_plane_relay_to_inbox"]}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Never print an access token, OAuth secret, full URI, tenant name or
        # raw response. The exception messages above contain no credentials.
        print("PEO controlled staging acceptance failed:", str(exc), file=sys.stderr)
        sys.exit(1)
