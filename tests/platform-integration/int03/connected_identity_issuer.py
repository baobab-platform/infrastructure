"""Reviewable, private OAuth issuer port for supervised INT-03C.
No client is created; approval and runtime credentials come from IAM's
governed fixture authority. It never authenticates as the held CMS clients.
"""
import json
import re
import ssl
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error
from connected_identity_evidence import EvidenceRefused

ALLOWED = ("https://hydra.int03.test",
           "https://iam.int02.test/realms/baobab")
MAX = 16384


class IssuerPort:
    def __init__(self, issuer, ca, *, transport=None):
        if issuer not in ALLOWED:
            raise EvidenceRefused("unapproved private issuer")
        trust = Path(ca)
        if trust.is_symlink() or not trust.is_file() or not trust.stat().st_size:
            raise EvidenceRefused("issuer trust anchor missing")
        try:
            tls = ssl.create_default_context(cafile=str(trust))
        except (OSError, ssl.SSLError):
            raise EvidenceRefused("issuer CA invalid") from None

        class DenyRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.open = transport or urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=tls), DenyRedirect()).open
        self.issuer = issuer
        self.endpoints = {}

    def _request(self, url, *, data=None, headers=None):
        p = urllib.parse.urlsplit(url)
        origin = urllib.parse.urlsplit(self.issuer)
        if (p.scheme != "https" or p.netloc != origin.netloc or
            not url.startswith(self.issuer + "/") or
            p.query or p.fragment or p.username or p.password or
            p.port not in (None, 443)):
            raise EvidenceRefused("issuer operation crossed private trust boundary")
        if data is not None and (not isinstance(data, bytes) or len(data) > 8192):
            raise EvidenceRefused("unbounded issuer input")
        request = urllib.request.Request(url, data=data, headers=headers or {},
                                         method="POST" if data is not None else "GET")
        try:
            with self.open(request, timeout=20) as response:
                if response.status != 200:
                    raise EvidenceRefused("issuer did not confirm operation")
                raw = response.read(MAX + 1)
        except (urllib.error.URLError, OSError, TimeoutError, ValueError):
            raise EvidenceRefused("issuer operation unavailable") from None
        if len(raw) > MAX:
            raise EvidenceRefused("issuer response unbounded")
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise EvidenceRefused("issuer response malformed") from None
        if type(result) is not dict:
            raise EvidenceRefused("issuer response not an object")
        return result

    def discover(self):
        metadata = self._request(self.issuer + "/.well-known/openid-configuration")
        if metadata.get("issuer") != self.issuer:
            raise EvidenceRefused("issuer discovery mismatch")
        endpoints = {}
        for name in ("token_endpoint", "introspection_endpoint", "revocation_endpoint"):
            endpoint = metadata.get(name)
            if not isinstance(endpoint, str):
                raise EvidenceRefused("issuer operation not available")
            parsed = urllib.parse.urlsplit(endpoint)
            if (not endpoint.startswith(self.issuer + "/") or
                parsed.netloc != urllib.parse.urlsplit(self.issuer).netloc or
                parsed.scheme != "https" or parsed.query or parsed.fragment):
                raise EvidenceRefused("unsafe OAuth discovery endpoint")
            endpoints[name] = endpoint
        self.endpoints = endpoints
        return True

    def execute(self, operation, fields, private_auth):
        """Call only approved OAuth2 operations; never return token in logs."""
        if operation not in ("token_endpoint", "introspection_endpoint") or (
                operation not in self.endpoints):
            raise EvidenceRefused("unapproved issuer operation")
        if type(fields) is not dict or type(private_auth) is not str or (
                not private_auth.startswith("Basic ") or len(private_auth) > 1024):
            raise EvidenceRefused("independent private OAuth client required")
        data = urllib.parse.urlencode(fields).encode()
        return self._request(self.endpoints[operation], data=data,
                             headers={"Authorization": private_auth,
                                      "Content-Type": "application/x-www-form-urlencoded",
                                      "Accept": "application/json"})

    def revoke(self, token, owner_basic):
        """RFC7009 request by the original owner; checker MUST introspect after.

        Return value is transport-only, never an independently witnessed
        revoked access token. A 200 acknowledgement is not revocation proof.
        """
        if ("revocation_endpoint" not in self.endpoints or
            not isinstance(token, str) or not 32 <= len(token) <= MAX or
            not isinstance(owner_basic,str) or not owner_basic.startswith("Basic ") or
            len(owner_basic)>1024):
            raise EvidenceRefused("supervised issuer revocation not prepared")
        endpoint=self.endpoints["revocation_endpoint"]
        raw=urllib.parse.urlencode(
            {"token":token,"token_type_hint":"access_token"}).encode()
        request=urllib.request.Request(endpoint,data=raw,method="POST",
            headers={"Authorization":owner_basic,
                     "Content-Type":"application/x-www-form-urlencoded"})
        try:
            with self.open(request,timeout=20) as response:
                if response.status not in (200,204) or len(response.read(1025))>1024:
                    raise EvidenceRefused("issuer refused revocation")
        except (urllib.error.URLError,OSError,TimeoutError,ValueError):
            raise EvidenceRefused("issuer revocation unavailable") from None
        return True

    @staticmethod
    def assert_introspection(response, *, client_id, audience, scope, now):
        if (type(response) is not dict or response.get("active") is not True or
            response.get("client_id") != client_id):
            raise EvidenceRefused("issuer did not confirm active client")
        aud = response.get("aud")
        audiences = (aud,) if isinstance(aud, str) else aud
        if not isinstance(audiences, (list, tuple)) or audience not in audiences:
            raise EvidenceRefused("issuer audience differs")
        scopes = response.get("scope")
        expiry = response.get("exp")
        if (not isinstance(scopes, str) or scope not in scopes.split() or
            type(expiry) is not int or not now + 30 < expiry <= now + 900):
            raise EvidenceRefused("issuer scope or short expiry differs")
        return {"client_id": client_id, "audience": audience, "scope": scope,
                "expiry": expiry, "issuer_current": True, "qualified": False}

    @staticmethod
    def assert_revoked(response, *, expiry, now):
        if type(response) is not dict or response.get("active") is not False or now >= expiry:
            raise EvidenceRefused("revocation not independently observed before expiry")
        return {"issuer_revoked_before_expiry": True, "cp_denial_unverified": True,
                "qualified": False}
