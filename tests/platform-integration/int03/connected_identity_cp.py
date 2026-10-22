"""Real HTTPS CP observation port for INT-03C's supervised identity journey.

Read-only in the *governance* sense: context resolution can persist a
short-lived CP Context, but this module never registers a Tenant, Principal,
market, grant, provider or IAM client, nor revokes an identity. It consumes
only separately issued, governed private credentials from the owning runner.
Synthetic transport tests are *not* qualification.
"""
import json
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from connected_identity_evidence import EvidenceRefused

MAX_BODY = 32768
ORIGINS = frozenset(("cp.int02.test", "cp.int03.test"))
CODES = frozenset((
    "AUTH_TOKEN_REQUIRED", "AUTHORIZATION_DENIED", "IDENTITY_RESOLUTION_FAILED",
    "TENANT_CONTEXT_MISMATCH", "CONTEXT_DENIED", "CONTEXT_NOT_FOUND",
    "CALLER_NOT_PERMITTED", "SUBJECT_TOKEN_INVALID", "PRINCIPAL_INACTIVE",
    "TENANT_NOT_ACTIVE", "ORGANISATION_NOT_RESOLVED", "INVALID_REQUEST",
    "CONTEXT_STORE_UNAVAILABLE",
))


class CPTransport:
    """TLS-verifying, closed path/method, bounded, no-redirect live CP client."""
    def __init__(self, origin, ca_file, *, open_request=None):
        parsed = urllib.parse.urlsplit(origin)
        if (parsed.scheme != "https" or parsed.hostname not in ORIGINS or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in ("", "/") or parsed.port not in (None,443)):
            raise EvidenceRefused("private CP host boundary required")
        ca = Path(ca_file)
        if ca.is_symlink() or not ca.is_file() or ca.stat().st_size == 0:
            raise EvidenceRefused("actual disposable CP trust anchor required")
        try:
            context=ssl.create_default_context(cafile=str(ca))
        except (ssl.SSLError,OSError):
            raise EvidenceRefused("CP CA invalid") from None

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):
                return None
        self.open=open_request or urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context),NoRedirect()).open
        self.origin=origin.rstrip("/")

    def request(self, method, path, token, body=None):
        if ((method,path) not in (
            ("GET","/v1/admin/effective-authority"),
            ("POST","/v1/platform-context/resolve"),
            ("POST","/v1/platform-context/validate")) or
            not isinstance(token,str) or not 16 <= len(token) <= 8192 or
            any(x.isspace() for x in token)):
            raise EvidenceRefused("unregistered CP operation or invalid private token")
        if (method=="POST" and (not isinstance(body,dict) or
                                len(json.dumps(body).encode())>8192)) or (
                method=="GET" and body is not None):
            raise EvidenceRefused("bounded CP request required")
        data=(json.dumps(body,separators=(",",":")).encode()
              if method=="POST" else None)
        req=urllib.request.Request(self.origin+path,data=data,method=method,
            headers={"Authorization":"Bearer "+token,
                     "Accept":"application/json",
                     "Cache-Control":"no-store",
                     **({"Content-Type":"application/json"} if data is not None else {})})
        try:
            response=self.open(req,timeout=20)
        except urllib.error.HTTPError as err:
            response=err
        except (urllib.error.URLError,OSError,TimeoutError,ValueError):
            raise EvidenceRefused("CP read-back unavailable") from None
        with response:
            status=response.status if hasattr(response,"status") else response.code
            raw=response.read(MAX_BODY+1)
        if len(raw)>MAX_BODY or type(status) is not int:
            raise EvidenceRefused("CP read-back unbounded")
        try:
            parsed=json.loads(raw)
        except (ValueError,UnicodeDecodeError):
            raise EvidenceRefused("CP response was not valid JSON") from None
        if not isinstance(parsed,dict):
            raise EvidenceRefused("CP JSON shape invalid")
        if status==200:
            return {"status":200,"code":"","document":parsed}
        code=parsed.get("code")
        if (status not in (400,401,403,404,410,503) or
            type(code) is not str or code not in CODES or
            parsed.get("status")!=status):
            raise EvidenceRefused("unexpected CP denial semantics")
        return {"status":status,"code":code,"document":None}


def assert_current_human(readback, expected_principal):
    """Actual CP self-effective-authority resolves an ACTIVE human Principal.

    This does not mean the caller is allowed to certify itself or grant any
    authority. A real CP Principal UUID is corroborated, not locally minted.
    """
    if (type(readback) is not dict or readback.get("status") != 200 or
        not isinstance(readback.get("document"),dict) or
        not isinstance(expected_principal,str) or
        not re.fullmatch(r"[0-9a-f-]{36}",expected_principal) or
        readback["document"].get("principal_id") != expected_principal):
        raise EvidenceRefused("CP ACTIVE Principal readback differs")
    return True


def assert_negative(readback, case):
    """Require the *correct authority's* denial, never any convenient 403."""
    allowed={
        "wrong_audience_denied":{(401,"AUTH_TOKEN_REQUIRED"),
                                 (403,"AUTHORIZATION_DENIED")},
        "cross_tenant_denied":{(403,"TENANT_CONTEXT_MISMATCH"),
                               (403,"CONTEXT_DENIED"),(404,"CONTEXT_NOT_FOUND")},
        "revoked_credential_denied":{(401,"AUTH_TOKEN_REQUIRED"),
                                    (403,"AUTHORIZATION_DENIED")},
        "deactivated_principal_denied":{(403,"PRINCIPAL_INACTIVE"),
                                       (403,"IDENTITY_RESOLUTION_FAILED"),
                                       (403,"CONTEXT_DENIED")},
    }
    if case not in allowed or not isinstance(readback,dict) or (
        readback.get("status"),readback.get("code")) not in allowed[case]:
        raise EvidenceRefused("CP negative case is not a qualifying denial")
    return True


def read_private_token(file):
    """No bearer in argv, CI output, receipt or error message."""
    import os
    import stat
    path=Path(file)
    info=path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(info.st_mode) or
        info.st_uid!=os.getuid() or info.st_mode & 0o077 or
        not 16<=info.st_size<=8192):
        raise EvidenceRefused("disposable issuer token file not owner-private")
    token=path.read_text(encoding="utf-8").strip()
    if not 16<=len(token)<=8192 or any(ch.isspace() for ch in token):
        raise EvidenceRefused("invalid private bearer")
    return token
