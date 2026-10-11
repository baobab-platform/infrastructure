#!/usr/bin/env python3
"""PEO-02T authenticated, read-only CP negative-scope staging evidence.

Cannot create documentary restrictions, issue legal authority, or activate tenants.
Requires a reviewed preexisting SYNTHETIC context and a human-approved staging run.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import re
import ssl
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import (
    HTTPRedirectHandler, HTTPSHandler, Request, build_opener,
)
from uuid import UUID

POLICY = "ADR-BCP-026/PEO-02T:negative-only"
EVIDENCE = Path("peo-acceptance-evidence/cp-documentary-restriction.json")
REQUIRED = (
    "PEO_STAGING_IAM_TOKEN_URL", "PEO_STAGING_CP_BASE_URL",
    "PEO_STAGING_ALLOWED_HOSTS", "PEO_STAGING_CP_AUDIENCE",
    "PEO_STAGING_DOCUMENTARY_CLIENT_ID", "PEO_STAGING_DOCUMENTARY_CLIENT_SECRET",
    "PEO_STAGING_DOCUMENTARY_CONTEXT_ID",
    "PEO_STAGING_DOCUMENTARY_ORGANISATION_ID",
    "PEO_STAGING_DOCUMENTARY_MARKET",
    "PEO_STAGING_DOCUMENTARY_HELD_CAPABILITY",
    "PEO_STAGING_DOCUMENTARY_CLEAR_CAPABILITY",
    "PEO_STAGING_CP_DEPLOYED_REVISION",
)


class ProofDenied(RuntimeError):
    """Fail-closed acceptance rejection (no token/response material in errors)."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProofDenied("endpoint redirected outside reviewed trust boundary")


def reviewed_endpoint(url: str, allowed_hosts: set[str]) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname not in allowed_hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or parsed.query
    ):
        raise ProofDenied("endpoint is not a reviewed, exact HTTPS staging host")
    return url.rstrip("/")


def current_time(raw: object) -> datetime:
    if not isinstance(raw, str):
        raise ProofDenied("CP decision lacks trusted time")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProofDenied("CP decision time invalid") from exc
    if parsed.tzinfo is None:
        raise ProofDenied("CP decision time has no timezone")
    return parsed.astimezone(timezone.utc)


def verify_decision(
    value: object,
    *,
    context: str,
    organisation: str,
    capability: str,
    market: str,
    operation: str,
    expected_blocked: bool,
    now: datetime,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProofDenied("CP response is not a decision object")
    expected = {
        "context_id": context,
        "organisation_id": organisation,
        "capability": capability,
        "market": market,
        "operation_reference": operation,
        "blocked": expected_blocked,
        "authority_granted": False,
        "policy_reference": POLICY,
    }
    for key, wanted in expected.items():
        if type(value.get(key)) is not type(wanted) or value.get(key) != wanted:
            raise ProofDenied("CP decision is blocked, privileged, or context-mismatched")
    evaluated = current_time(value.get("evaluated_at"))
    expires = current_time(value.get("expires_at"))
    if (
        evaluated > now
        or (now - evaluated).total_seconds() > 3
        or expires <= now
        or (expires - evaluated).total_seconds() > 2
    ):
        raise ProofDenied("CP negative-only decision stale or over-leased")
    return {
        "context_id": context,
        "organisation_id": organisation,
        "capability": capability,
        "market": market,
        "blocked": expected_blocked,
        "authority_granted": False,
        "policy_reference": POLICY,
        "evaluated_at": evaluated.isoformat(),
        "expires_at": expires.isoformat(),
    }


def _call_json(opener, request: Request) -> object:
    try:
        with opener.open(request, timeout=8) as response:
            if response.status != 200:
                raise ProofDenied("IAM or CP did not return HTTP 200")
            data = response.read(65537)
            if len(data) > 65536:
                raise ProofDenied("oversized IAM/CP response")
            return json.loads(data)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise ProofDenied("authenticated IAM/CP staging exchange failed") from exc


def _uuid(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ProofDenied("synthetic context or Organisation ID is invalid") from exc


def run(env: dict[str, str]) -> dict[str, object]:
    if env.get("PEO_STAGING_DOCUMENTARY_APPROVED") != "true":
        raise ProofDenied("independent protected synthetic approval missing")
    if any(not env.get(k) for k in REQUIRED):
        raise ProofDenied("protected staging identity, context, or deployment input absent")
    allowed = set(env["PEO_STAGING_ALLOWED_HOSTS"].split(","))
    if not allowed or any(not h or h.strip() != h or "*" in h for h in allowed):
        raise ProofDenied("staging host allowlist is missing or wildcarded")
    iam = reviewed_endpoint(env["PEO_STAGING_IAM_TOKEN_URL"], allowed)
    cp = reviewed_endpoint(env["PEO_STAGING_CP_BASE_URL"], allowed)
    context = _uuid(env["PEO_STAGING_DOCUMENTARY_CONTEXT_ID"])
    organisation = _uuid(env["PEO_STAGING_DOCUMENTARY_ORGANISATION_ID"])
    market = env["PEO_STAGING_DOCUMENTARY_MARKET"]
    held = env["PEO_STAGING_DOCUMENTARY_HELD_CAPABILITY"]
    clear = env["PEO_STAGING_DOCUMENTARY_CLEAR_CAPABILITY"]
    if (
        re.fullmatch(r"[A-Z]{2}", market) is None
        or any(re.fullmatch(r"[a-z][a-z0-9._-]{2,199}", v) is None for v in (held, clear))
        or held == clear
        or len(env["PEO_STAGING_CP_DEPLOYED_REVISION"]) < 12
    ):
        raise ProofDenied("staging negative-scope selectors or release pin invalid")
    opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), NoRedirects())
    basic = base64.b64encode(
        (env["PEO_STAGING_DOCUMENTARY_CLIENT_ID"] + ":" +
         env["PEO_STAGING_DOCUMENTARY_CLIENT_SECRET"]).encode()
    ).decode()
    token_response = _call_json(opener, Request(
        iam,
        data=urlencode({
            "grant_type": "client_credentials",
            "scope": "documentary:restriction-assess context:resolve",
            "audience": env["PEO_STAGING_CP_AUDIENCE"],
        }).encode(),
        headers={
            "Authorization": "Basic " + basic,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    ))
    if (
        not isinstance(token_response, dict)
        or token_response.get("token_type", "").lower() != "bearer"
        or not isinstance(token_response.get("access_token"), str)
        or not token_response["access_token"].strip()
    ):
        raise ProofDenied("real IAM workload token not issued")
    token = token_response["access_token"]
    checks = []
    for capability, should_block, suffix in (
        (held, True, "held"), (clear, False, "clear"),
    ):
        operation = "synthetic/documentary/" + suffix
        payload = json.dumps({
            "context_id": context, "capability": capability,
            "market": market, "operation_reference": operation,
        }).encode()
        result = _call_json(opener, Request(
            cp + "/internal/documentary/v1/restrictions/assess",
            data=payload,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
                "Cache-Control": "no-store",
                "X-Correlation-ID": "synthetic-peo02t-" + suffix,
            },
            method="POST",
        ))
        checks.append(verify_decision(
            result, context=context, organisation=organisation,
            capability=capability, market=market, operation=operation,
            expected_blocked=should_blocked(should_block),
            now=datetime.now(timezone.utc),
        ))
    return {
        "status": "PROVED",
        "scope": "PEO-02T_NEGATIVE_ONLY_STAGING_SYNTHETIC",
        "cp_deployed_revision": env["PEO_STAGING_CP_DEPLOYED_REVISION"],
        "checks": checks,
        "provider_or_business_activation_certified": False,
    }


def should_blocked(expected: bool) -> bool:
    return expected


def main() -> int:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = run(dict(os.environ))
    except ProofDenied as exc:
        EVIDENCE.write_text(json.dumps({
            "status": "PENDING",
            "scope": "PEO-02T_NEGATIVE_ONLY_STAGING_SYNTHETIC",
            "reason": str(exc),
            "provider_or_business_activation_certified": False,
        }, indent=2) + "\n")
        print("PEO-02T staging evidence PENDING: " + str(exc), file=sys.stderr)
        return 1
    EVIDENCE.write_text(json.dumps(report, indent=2) + "\n")
    print("PEO-02T synthetic negative restriction CP assessment PROVED (not production)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
