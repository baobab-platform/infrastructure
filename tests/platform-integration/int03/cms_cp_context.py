"""Real CP context round-trip for a governed synthetic CMS fixture.

The CP, not this module, issues canonical context and validates ownership.
It never creates tenants, Organisations, market membership, Principal grants,
certifications or provider bindings. Those must be installed via CP's governed
maker/checker APIs first. Test doubles prove protocol guards only.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

from cms_lifecycle import Refused

MAX_BODY = 32768
COUNTRY = re.compile(r"[A-Z]{2}\Z")
KINDS = frozenset({"ORGANISATION", "BUYER_ORGANISATION", "SUPPLIER_ORGANISATION"})


def canonical_uuid(value):
    try:
        result = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise Refused("invalid canonical UUID") from None
    if result.version not in (4, 7) or str(result) != value:
        raise Refused("noncanonical topology UUID")
    return value


def moment(value):
    if not isinstance(value, str):
        raise Refused("CP timestamp absent")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Refused("CP timestamp malformed") from None
    if result.tzinfo is None:
        raise Refused("CP timestamp lacks offset")
    return result.astimezone(timezone.utc)


def assert_resolved(payload, *, tenant, organisation, country, kind, now):
    """Fail closed on CP mismatches, expiry and unbounded context."""
    if not isinstance(payload, dict):
        raise Refused("CP context not a JSON object")
    cid = canonical_uuid(payload.get("context_id"))
    if payload.get("tenant_id") != tenant or payload.get("organisation_id") != organisation:
        raise Refused("CP context ownership mismatch")
    if payload.get("organisation_type") != kind or payload.get("country_code") != country:
        raise Refused("CP context organisation or country differs")
    if not isinstance(payload.get("market_id"), str) or not payload["market_id"]:
        raise Refused("CP did not attest an active market")
    if not isinstance(payload.get("currency_code"), str) or not re.fullmatch(r"[A-Z]{3}", payload["currency_code"]):
        raise Refused("CP did not attest market currency")
    resolved, expires = moment(payload.get("resolved_at")), moment(payload.get("expires_at"))
    if resolved > now or expires <= now or expires <= resolved:
        raise Refused("CP context is unbounded, future or expired")
    return cid, expires


def assert_validated(payload, *, cid, tenant, organisation, market, expires, now):
    if not isinstance(payload, dict) or payload.get("context_id") != cid:
        raise Refused("CP validator did not attest the issued context")
    if payload.get("tenant_id") != tenant or payload.get("organisation_id") != organisation:
        raise Refused("CP validator identity or tenant mismatch")
    if payload.get("market_id") != market or payload.get("authority_purpose") != "RUNTIME":
        raise Refused("CP validator returned non-runtime or wrong market authority")
    if "provisioning_authority" in payload:
        raise Refused("provisioning authority cannot authorise CMS publication")
    if moment(payload.get("expires_at")) != expires or expires <= now:
        raise Refused("CP validator expiry differs or has elapsed")
    if moment(payload.get("resolved_at")) > now:
        raise Refused("CP validation timestamp is future")


class HTTPSControlPlane:
    """Authenticated CP transport: caller supplies two live issuer tokens.

    No response bodies, credentials, claims or full URL are included in errors,
    logs or receipts. CA pin is from the disposable Infrastructure run.
    """
    def __init__(self, origin, ca_file, *, transport=None):
        parsed = urllib.parse.urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in ("", "/")):
            raise Refused("CP origin must be a bare verified HTTPS host")
        ca = Path(ca_file)
        if not ca.is_file() or ca.is_symlink() or not ca.stat().st_size:
            raise Refused("private lab CA required")
        self.origin = origin.rstrip("/")
        self.context = ssl.create_default_context(cafile=str(ca))
        self.transport = transport or self._network

    def _network(self, relative_path, bearer, body, timeout):
        request = urllib.request.Request(
            self.origin + relative_path, method="POST",
            headers={"Authorization": "Bearer " + bearer, "Content-Type": "application/json",
                     "Accept": "application/json"},
            data=json.dumps(body, separators=(",", ":")).encode(),
        )
        # urllib follows redirects by default. A custom handler rejects them
        # before a credential-bearing request can escape the CP origin.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self.context), NoRedirect())
        with opener.open(request, timeout=timeout) as resp:
            if resp.status != 200:
                raise Refused("CP did not approve context operation")
            raw = resp.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise Refused("CP response exceeded size bound")
        return raw

    def _post(self, path, bearer, payload, timeout):
        if path not in ("/v1/platform-context/resolve", "/v1/platform-context/validate"):
            raise Refused("unexpected CP endpoint")
        if not isinstance(bearer, str) or not 16 <= len(bearer) <= 8192 or any(c.isspace() for c in bearer):
            raise Refused("invalid private bearer input")
        try:
            raw = self.transport(path, bearer, payload, timeout)
            if not isinstance(raw, bytes) or len(raw) > MAX_BODY:
                raise Refused("bounded CP JSON response required")
            return json.loads(raw)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            # Deliberately discard raw service responses and token-bearing URLs.
            raise Refused("CP live operation unavailable or malformed") from None

    def resolve_and_validate(self, lifecycle, *, consumer_token, validator_token,
                             tenant_id, organisation_id, country_code, organisation_kind):
        tenant_id, organisation_id = canonical_uuid(tenant_id), canonical_uuid(organisation_id)
        if not COUNTRY.fullmatch(country_code) or organisation_kind not in KINDS:
            raise Refused("invalid CP topology constraint")
        request = {"tenant_id": tenant_id, "organisation_id": organisation_id,
                   "country_code": country_code, "expected_organisation_type": organisation_kind}
        resolved = lifecycle.execute("cp-context-resolve",
            lambda seconds: self._post("/v1/platform-context/resolve", consumer_token,
                                        request, seconds))
        now = datetime.now(timezone.utc)
        context_id, expiry = assert_resolved(resolved, tenant=tenant_id,
            organisation=organisation_id, country=country_code,
            kind=organisation_kind, now=now)
        validated = lifecycle.execute("cp-context-validate",
            lambda seconds: self._post("/v1/platform-context/validate", validator_token,
                {"context_id": context_id, "subject_token": consumer_token}, seconds))
        assert_validated(validated, cid=context_id, tenant=tenant_id,
                         organisation=organisation_id, market=resolved["market_id"],
                         expires=expiry, now=datetime.now(timezone.utc))
        # No "certified" or "qualified" flag: CP's maker/checker/release/binding
        # acceptance must be independently obtained and retained.
        return {"context_id": context_id, "tenant_id": tenant_id,
                "organisation_id": organisation_id, "market_id": resolved["market_id"],
                "expires_at": expiry.isoformat(),
                "source": "CP_ACTUAL_HTTPS_ROUNDTRIP_UNCERTIFIED",
                "qualified": False}
