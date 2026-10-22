"""Governed CP-only synthetic topology qualification seam for NAB-03.

No CP objects are created by importing this module. The only mutations use
authenticated CP routes, never direct SQL, fabricated UUIDs, fake approval or
local capability authority. Unlike issuer activation, CP-only engineering can
continue while the Shared #354 CMS identity gate is HELD. Connected NAB-03
still MUST fail closed while the registry is HELD.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

MAX_BODY = 65536
CP_ORIGIN = "cp.int03.test"
CERT_ID = re.compile(r"cert_[0-9a-f]{32}\Z")
RELEASE_ID = re.compile(r"erl_[a-z0-9]+\Z")
MARKET_ID = re.compile(r"mkt_[a-z0-9]+\Z")
GRANT_ID = re.compile(r"agr_[a-z0-9]+\Z")
SAFE_PATH = re.compile(r"/[a-z0-9/_-]+\Z")
SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
GATE_CASES = frozenset(("tenant", "organisation", "principal", "market", "grant",
                        "release", "certification", "binding"))
CERTIFY_ROUTE = "/v1/provider-capability-certifications"


class Refused(RuntimeError):
    """No issuer, CP grant, CMS acceptance or approval is inferred."""


def canonical_uuid(value):
    if not isinstance(value, str):
        raise Refused("CP-generated canonical identifier required")
    try:
        candidate = uuid.UUID(value)
    except ValueError:
        raise Refused("CP identifier invalid") from None
    if str(candidate) != value or candidate.version not in (4, 7):
        raise Refused("CP canonical identifier invalid")
    return value


def checked_identity(acting, checking):
    if not isinstance(acting, Operator) or not isinstance(checking, Operator):
        raise Refused("two separate CP operators are required")
    if acting.principal_id == checking.principal_id or acting.credential == checking.credential:
        raise Refused("maker/checker cannot be the same Principal or bearer")


@dataclass(frozen=True)
class Operator:
    """A real, pre-existing ACTIVE CP human administrator; not a synthetic JWT."""
    principal_id: str
    credential: str
    role: str

    def __post_init__(self):
        canonical_uuid(self.principal_id)
        if (not isinstance(self.credential, str) or
            not 20 <= len(self.credential) <= 8192 or
            any(c.isspace() for c in self.credential) or
            self.role not in ("maker", "checker")):
            raise Refused("verified CP human operator identity required")


class CPGateway:
    """TLS CA checked, non-redirecting CP transport; no unsafe host fallback."""

    def __init__(self, base, ca_file, *, opener=None):
        parsed = urllib.parse.urlsplit(base)
        if (parsed.scheme != "https" or parsed.hostname != CP_ORIGIN or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            parsed.path not in ("", "/")):
            raise Refused("CP-only synthetic lab HTTPS origin required")
        path = Path(ca_file)
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise Refused("private CP CA required")
        try:
            context = ssl.create_default_context(cafile=str(path))
        except (ssl.SSLError, OSError):
            raise Refused("private CP CA unreadable or invalid") from None

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.base = base.rstrip("/")
        self.opener = opener or urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context), NoRedirect())

    def call(self, operator, method, path, *, body=None, idempotency=None,
             if_match=None, expect=(200,)):
        if not isinstance(operator, Operator) or not SAFE_PATH.fullmatch(path):
            raise Refused("CP route or principal invalid")
        if method not in ("GET", "POST", "PATCH") or not isinstance(expect, tuple):
            raise Refused("unsupported CP method")
        if method == "GET" and body is not None:
            raise Refused("GET cannot carry an authority document")
        if method != "GET" and not isinstance(body, dict):
            raise Refused("CP writes require a reviewed document")
        if len(path) > 200:
            raise Refused("CP route too long")
        data = None if body is None else json.dumps(
            body, sort_keys=True, separators=(",", ":")).encode()
        if data is not None and len(data) > MAX_BODY:
            raise Refused("CP write document exceeds bound")
        headers = {"Authorization": "Bearer " + operator.credential,
                   "Accept": "application/json", "Cache-Control": "no-store"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if idempotency:
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{16,128}", idempotency):
                raise Refused("invalid CP idempotency key")
            headers["Idempotency-Key"] = idempotency
        if if_match:
            if not re.fullmatch(r'"[0-9]+"', if_match):
                raise Refused("CP strong If-Match revision required")
            headers["If-Match"] = if_match
        try:
            request = urllib.request.Request(self.base + path, data=data,
                                             headers=headers, method=method)
            with self.opener.open(request, timeout=20) as response:
                if response.status not in expect:
                    raise Refused("CP operation did not return expected status")
                raw = response.read(MAX_BODY + 1)
                if len(raw) > MAX_BODY:
                    raise Refused("CP response body exceeds bound")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise Refused("CP operation returned non-object")
                return result
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            # Never expose tokens, response bodies, request payloads, URLs,
            # legal evidence, tenant or Principal identities in public logs.
            raise Refused("private CP operation unavailable or malformed") from None


class Fixture:
    """Owns sequencing, not CP authority or independent certification."""

    def __init__(self, cp, maker, checker):
        checked_identity(maker, checker)
        if maker.role != "maker" or checker.role != "checker":
            raise Refused("operator role assignment differs")
        self.cp, self.maker, self.checker = cp, maker, checker

    def register_tenant(self, reviewed_request, *, key):
        """Submit CP registration only for independently AUTHORISED onboarding.

        CP allocates the Tenant ID asynchronously. An accepted operation is
        not an ACTIVE tenant; the operator must await CP completion and call
        verify_tenant with the actual emitted ID.
        """
        if (not isinstance(reviewed_request, dict) or
            not isinstance(reviewed_request.get("tenant_onboarding_request_id"), str) or
            any(k in reviewed_request for k in
                ("tenant_id", "status", "principal_id", "authorised_by",
                 "approval", "bootstrap_reason", "evidence_reference"))):
            raise Refused("CP-authorised onboarding request required, not bootstrap")
        out = self.cp.call(self.maker, "POST", "/v1/tenants",
                           body=reviewed_request, idempotency=key, expect=(202,))
        if not isinstance(out.get("operation_id"), str):
            raise Refused("CP Tenant registration operation not issued")
        return {"operation_id": out["operation_id"],
                "outcome": "PENDING_CP_OPERATION",
                "tenant_registered": False, "qualified": False}

    def admit_organisation(self, tenant_id, reviewed_document):
        """Use the actual CP verified-case/decision path, never raw SQL."""
        canonical_uuid(tenant_id)
        if (not isinstance(reviewed_document, dict) or
            not isinstance(reviewed_document.get("verification_case_id"), str) or
            not isinstance(reviewed_document.get("admission_decision_id"), str) or
            not isinstance(reviewed_document.get("applicant_organisation"), dict) or
            not isinstance(reviewed_document.get("platform_account"), dict) or
            any(k in reviewed_document for k in
                ("organisation_id", "status", "verified", "legal_entity_id",
                 "approved", "is_active"))):
            raise Refused("actual CP verification/admission references required")
        out = self.cp.call(self.maker, "POST",
                           f"/v1/tenants/{tenant_id}/organisation-admission",
                           body=reviewed_document, expect=(200,))
        if out.get("identity_resolution") == "QUARANTINED":
            raise Refused("CP quarantined Organisation identity")
        # No local Organisation ID is issued. A subsequent caller must read
        # the actual canonical result and verify it via the CP GET route.
        return {"cp_outcome": "ADMISSION_RETURNED_UNVERIFIED",
                "qualified": False}

    def issue_existing_principal_grant(self, principal_id, permission, scope,
                                       *, grant_type, reason, key):
        """CP must resolve this already ACTIVE Principal before issuance.

        This never creates an identity; grant issuance is CP's own guarded
        administrative route with its policy catalogue and tenant boundary.
        """
        canonical_uuid(principal_id)
        if (not isinstance(permission, str) or not permission or
            not isinstance(scope, dict) or not scope or
            grant_type not in ("STANDING", "TIME_BOUND", "JUST_IN_TIME") or
            not isinstance(reason, str) or len(reason) < 10):
            raise Refused("CP grant must have an explicit bounded purpose")
        request = {"principal_id": principal_id, "permission": permission,
                   "scope": scope, "grant_type": grant_type, "reason": reason}
        out = self.cp.call(self.maker, "POST", "/v1/admin/grants",
                           body=request, idempotency=key, expect=(200, 201))
        gid = out.get("grant_id")
        if not isinstance(gid, str) or not GRANT_ID.fullmatch(gid):
            raise Refused("CP grant ID not issued")
        # Grant is not made active by this client. The independent reviewer
        # must verify grant status on GET, including SoD/prohibition.
        return gid

    def record_engine_release(self, reviewed_document):
        if (not isinstance(reviewed_document, dict) or
            not isinstance(reviewed_document.get("engine_id"), str) or
            not isinstance(reviewed_document.get("source_revision"), str) or
            not isinstance(reviewed_document.get("artifacts"), list) or
            not reviewed_document["artifacts"] or
            not isinstance(reviewed_document.get("provider_support"), list) or
            any(k in reviewed_document for k in
                ("release_id", "status", "recorded_by", "approved_by"))):
            raise Refused("immutable reviewed EngineRelease declaration required")
        out = self.cp.call(self.maker, "POST", "/v1/engine-releases",
                           body=reviewed_document, expect=(200, 201))
        release_id = out.get("release_id")
        if not isinstance(release_id, str) or not RELEASE_ID.fullmatch(release_id):
            raise Refused("CP did not mint EngineRelease")
        if out.get("recorded_by") != self.maker.principal_id or out.get("status") != "CANDIDATE":
            raise Refused("EngineRelease record is not a maker-owned CANDIDATE")
        return release_id

    def create_market(self, document, *, key):
        if not isinstance(document, dict) or document.get("owner_tenant_id") is None:
            raise Refused("CP market needs approved owning Tenant")
        canonical_uuid(document["owner_tenant_id"])
        # CP mints the market ID and initially leaves it non-active. No
        # status, approval, reviewer or minted ID comes from this document.
        if any(x in document for x in ("market_id", "status", "approved_by",
                                      "activated_by", "created_by")):
            raise Refused("caller attempted to forge market authority")
        m = self.cp.call(self.maker, "POST", "/v1/markets", body=document,
                         idempotency=key, expect=(201,))
        mid = m.get("market_id")
        if not isinstance(mid, str) or not MARKET_ID.fullmatch(mid):
            raise Refused("market ID not issued by CP")
        if m.get("created_by") != self.maker.principal_id or m.get("status") == "ACTIVE":
            raise Refused("market was self-activated or maker unverified")
        return mid

    def activate_market(self, mid, *, reason):
        if not isinstance(mid, str) or not MARKET_ID.fullmatch(mid):
            raise Refused("CP market ID invalid")
        prior = self.cp.call(self.checker, "GET", f"/v1/markets/{mid}")
        if prior.get("created_by") == self.checker.principal_id:
            raise Refused("market activation maker/checker conflict")
        if prior.get("market_id") != mid or prior.get("status") == "ACTIVE":
            raise Refused("market missing or already active")
        revision = prior.get("revision")
        if type(revision) is not int or revision < 1:
            raise Refused("CP market revision not available")
        if not isinstance(reason, str) or not 10 <= len(reason) <= 500:
            raise Refused("independent activation reason required")
        self.cp.call(self.checker, "POST", f"/v1/markets/{mid}/activate",
                     body={"reason": reason}, if_match=f'"{revision}"', expect=(200,))
        fresh = self.cp.call(self.maker, "GET", f"/v1/markets/{mid}")
        if (fresh.get("market_id") != mid or fresh.get("status") != "ACTIVE" or
            fresh.get("activated_by") != self.checker.principal_id):
            raise Refused("CP market maker/checker read-back differs")
        return fresh

    def verify_tenant(self, tenant_id):
        canonical_uuid(tenant_id)
        t = self.cp.call(self.checker, "GET", f"/v1/tenants/{tenant_id}")
        if t.get("tenant_id") != tenant_id:
            raise Refused("CP Tenant proof missing")
        return t

    def verify_organisation(self, organisation_id):
        canonical_uuid(organisation_id)
        org = self.cp.call(self.checker, "GET",
                           f"/v1/organisations/{organisation_id}/overview")
        if org.get("organisation_id") != organisation_id:
            raise Refused("CP Organisation identity read-back differs")
        return org

    def verify_grant(self, grant_id, principal_id):
        if not isinstance(grant_id, str) or not GRANT_ID.fullmatch(grant_id):
            raise Refused("CP grant ID required")
        canonical_uuid(principal_id)
        grant = self.cp.call(self.checker, "GET", f"/v1/admin/grants/{grant_id}")
        if grant.get("principal_id") != principal_id or grant.get("status") != "ACTIVE":
            raise Refused("CP Principal grant absent or inactive")
        return grant

    def verify_release(self, release_id):
        if not isinstance(release_id, str) or not RELEASE_ID.fullmatch(release_id):
            raise Refused("CP immutable release ID required")
        release = self.cp.call(self.checker, "GET", f"/v1/engine-releases/{release_id}")
        if release.get("release_id") != release_id or release.get("status") != "APPROVED":
            raise Refused("provider EngineRelease not independently approved")
        if release.get("recorded_by") == self.checker.principal_id:
            raise Refused("release recorder cannot be provider certifier")
        return release

    def certify_provider(self, *, provider_id, capability_key, release_id, contract_version,
                         evidence, qualification_profile):
        # Neither evidence nor certification is self-issued: reviewer uses
        # separate ACTIVE human Principal; CP enforces maker-checker again.
        release = self.verify_release(release_id)
        if not isinstance(evidence, list) or not evidence or any(
                not isinstance(item, dict) or not SHA256.fullmatch(item.get("digest", ""))
                or not str(item.get("uri", "")).startswith(("https://", "oci://"))
                for item in evidence):
            raise Refused("retained immutable real evidence references required")
        if type(contract_version) is not int or contract_version < 1:
            raise Refused("canonical capability contract version required")
        body = {"provider_id": provider_id, "capability_key": capability_key,
                "contract_version": contract_version, "release_id": release_id,
                "qualification_profile": qualification_profile, "evidence": evidence,
                "reason": "Independent qualification of disposable CMS provider capability"}
        result = self.cp.call(self.checker, "POST", CERTIFY_ROUTE, body=body,
                              expect=(200, 201))
        cid = result.get("certification_id")
        if not isinstance(cid, str) or not CERT_ID.fullmatch(cid):
            raise Refused("certification identifier not CP-issued")
        read = self.cp.call(self.maker, "GET", f"{CERTIFY_ROUTE}/{cid}")
        if (read.get("certification_id") != cid or read.get("status") != "CERTIFIED" or
            read.get("certified_by") != self.checker.principal_id or
            read.get("release_id") != release_id or
            read.get("provider_id") != provider_id or
            read.get("capability_key") != capability_key or
            read.get("contract_version") != contract_version or
            read.get("qualification_profile") != qualification_profile):
            raise Refused("independent CP certification read-back differs")
        if read.get("certified_by") == release.get("recorded_by"):
            raise Refused("self-certified EngineRelease")
        return read

    def verify_resolved_provider(self, resolve, *, context_id, provider_id,
                                 engine_instance_id, capability_key,
                                 certification_id):
        """Require the CURRENT CP capability resolver, not a local binding.

        `resolve` is the separate live workload HTTP port invoking
        POST /v1/capabilities/resolve with a CP-issued own context handle.
        It must authenticate the *workload*, not either human administrator.
        """
        canonical_uuid(context_id)
        if (not callable(resolve) or not isinstance(provider_id, str) or
            not isinstance(engine_instance_id, str) or
            not isinstance(capability_key, str) or not
            isinstance(certification_id, str) or not CERT_ID.fullmatch(certification_id)):
            raise Refused("current provider resolution inputs required")
        cert = self.cp.call(self.checker, "GET",
                            f"/v1/provider-capability-certifications/{certification_id}")
        if (cert.get("certification_id") != certification_id or
            cert.get("status") != "CERTIFIED" or
            cert.get("provider_id") != provider_id or
            cert.get("capability_key") != capability_key):
            raise Refused("CP certification not current")
        if cert.get("certified_by") == self.maker.principal_id:
            raise Refused("CP certification actor not independent")
        result = resolve({"context_id": context_id,
                          "capability_key": capability_key,
                          "required_contract_version": cert.get("contract_version")})
        invocation = result.get("invocation") if isinstance(result, dict) else None
        if (not isinstance(result, dict) or result.get("decision") != "RESOLVED" or
            result.get("context_id") != context_id or result.get("capability_key") != capability_key or
            not isinstance(result.get("grant_id"), str) or
            not isinstance(result.get("binding_id"), str) or
            not isinstance(invocation, dict) or
            invocation.get("provider_id") != provider_id or
            invocation.get("engine_instance_id") != engine_instance_id or
            invocation.get("contract_version") != cert.get("contract_version")):
            raise Refused("CP did not resolve the certified live provider binding")
        # Resolver selection is a real CP fact, not full provider invocation
        # or performance/security proof. No NAB-03 qualification implied.
        return {"binding_id": result["binding_id"],
                "grant_id": result["grant_id"],
                "provider_id": provider_id,
                "engine_instance_id": engine_instance_id,
                "evidence": "CP_RESOLVER_UNATTESTED",
                "qualified": False}

    def verify_changeset_binding(self, changeset_id):
        # CP changeset lifecycle is the *only* human-governed provisioning
        # path, not a locally set capability_binding status flag.
        if not isinstance(changeset_id, str) or not re.fullmatch(r"cs_[a-z0-9]+", changeset_id):
            raise Refused("governed CP changeset ID required")
        record = self.cp.call(self.checker, "GET",
                              f"/v1/admin/changesets/{changeset_id}")
        result = self.cp.call(self.maker, "GET",
                              f"/v1/admin/changesets/{changeset_id}/outcome")
        if record.get("changeset_id") != changeset_id or result.get("changeset_id") != changeset_id:
            raise Refused("CP binding changeset provenance absent")
        if record.get("approved_by") == record.get("created_by"):
            raise Refused("CP changeset was self-approved")
        return {"changeset_id": changeset_id,
                "review": "CP_READBACK_ONLY_NEEDS_RUNTIME_RESOLVER_PROOF",
                "qualified": False}
