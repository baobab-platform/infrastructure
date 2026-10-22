"""Real HTTPS transport for the NAB-03 CMS content route.

The caller supplies live, disposable issuer tokens and CP-issued context IDs;
this transport creates neither. HTTP bodies/credentials never appear in a
receipt or exception. No mock transport is accepted by the running harness.
"""
import json
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

from cms_nab03 import HTTP, Refused

MAX_RESPONSE = 16384
MAX_REQUEST = 8192
CONTENT_KEY = re.compile(r"[a-z0-9][a-z0-9-]{0,99}\Z")
SAFE_BEARER = re.compile(r"[A-Za-z0-9._~+/-]+={0,2}\Z")


class HTTPSCMS:
    """No redirects, unauthenticated fallback, host ports or TLS exceptions."""

    def __init__(self, origin, ca_file):
        url = urllib.parse.urlsplit(origin)
        if (url.scheme != "https" or not url.hostname or url.username or
            url.password or url.query or url.fragment or url.path not in ("", "/")):
            raise Refused("CMS requires a bare HTTPS endpoint")
        ca = Path(ca_file)
        if ca.is_symlink() or not ca.is_file() or ca.stat().st_size == 0:
            raise Refused("reviewed disposable CA required")
        try:
            verified = ssl.create_default_context(cafile=str(ca))
        except (ssl.SSLError, OSError, ValueError):
            raise Refused("disposable CA cannot be verified") from None
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.origin = origin.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=verified), NoRedirect())

    def resolve(self, *, context_id, tenant_id, content_key, bearer, timeout,
                preview=False, digital_estate_id=None, market_id=None):
        """Observe actual CMS status, code and *minimal* content metadata."""
        try:
            if str(uuid.UUID(context_id)) != context_id:
                raise ValueError
        except (AttributeError, ValueError, TypeError):
            raise Refused("CP-issued context ID must be canonical UUID") from None
        if not isinstance(tenant_id, str) or not tenant_id or len(tenant_id) > 128:
            raise Refused("bounded CP tenant ID required")
        if not isinstance(content_key, str) or not CONTENT_KEY.fullmatch(content_key):
            raise Refused("invalid content key")
        if (not isinstance(bearer, str) or len(bearer) > 8192 or
            (bearer and SAFE_BEARER.fullmatch(bearer) is None)):
            raise Refused("invalid private bearer credential")
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
            raise Refused("bounded request timeout required")
        body = {"tenant_id": tenant_id, "content_key": content_key}
        if preview:
            body["preview_mode"] = True
        if digital_estate_id:
            body["digital_estate_id"] = digital_estate_id
        if market_id:
            body["market_id"] = market_id
        data = json.dumps(body, separators=(",", ":")).encode()
        if len(data) > MAX_REQUEST:
            raise Refused("CMS body too large")
        request = urllib.request.Request(
            self.origin + "/v1/content/resolve?context_id=" + context_id,
            data=data, method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json",
                     **({"Authorization": "Bearer " + bearer} if bearer else {})})
        try:
            try:
                response = self.opener.open(request, timeout=timeout)
            except urllib.error.HTTPError as err:
                response = err
            with response:
                status = response.status
                payload = response.read(MAX_RESPONSE + 1)
            if len(payload) > MAX_RESPONSE:
                raise Refused("CMS reply exceeds bound")
            result = json.loads(payload)
            if not isinstance(result, dict):
                raise Refused("CMS response must be JSON object")
            if status == 200:
                if "record" not in result:
                    raise Refused("CMS returned success without content record field")
                record = result["record"]
                if record is not None and not isinstance(record, dict):
                    raise Refused("CMS content record malformed")
                return HTTP(status=200, tenant_id=record.get("tenant_id", "") if record else "",
                            content_key=record.get("content_key", content_key) if record else content_key,
                            publication_state=record.get("publication_state", "") if record else "",
                            record_present=record is not None)
            code = result.get("code")
            if not isinstance(code, str) or not re.fullmatch(r"[A-Z_]{1,80}", code):
                raise Refused("CMS denied with unknown problem code")
            return HTTP(status=status, code=code)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            # Never echo request URL (which may contain context IDs), response
            # bodies, cookies, bearer tokens or remote exception messages.
            raise Refused("CMS real HTTPS observation unavailable") from None
