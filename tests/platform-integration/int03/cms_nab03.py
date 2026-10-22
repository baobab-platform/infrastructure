"""NAB-03's fourteen *real-observation* assertions and fail-closed receipt.

Inputs are obtained by a future registry-authorised live executor, not by
copying JSON from tests. This verifier never creates clients, grants, topology
or publishes a passing qualification. HELD runs cannot invoke any case.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from cms_gate import CASES, CONSUMER, VALIDATOR

SCHEMA = "infrastructure.int03.nab03-observation.v1"
NAB03 = frozenset(CASES)
CONTENT = ("home", "navigation", "footer")


class Refused(ValueError):
    """A case or authority boundary is not attested by the supplied observation."""


@dataclass(frozen=True)
class HTTP:
    """Bounded facts collected at the real TLS edge; never include credentials."""
    status: int
    code: str = ""
    tenant_id: str = ""
    content_key: str = ""
    publication_state: str = ""
    record_present: bool = False
    endpoint: str = "cms"

    def __post_init__(self):
        if type(self.status) is not int or not 100 <= self.status <= 599:
            raise Refused("invalid live HTTP status")
        if any(type(v) is not str or len(v) > 120 for v in (
            self.code, self.tenant_id, self.content_key, self.publication_state,
            self.endpoint,
        )) or type(self.record_present) is not bool:
            raise Refused("unbounded HTTP observation")
        if self.endpoint not in ("cms", "cp"):
            raise Refused("unexpected authority endpoint")


def denial(observed, status, code, endpoint="cms"):
    return (isinstance(observed, HTTP) and observed.endpoint == endpoint and
            observed.status == status and observed.code == code and
            observed.record_present is False)


def published(observed, key, tenant):
    return (isinstance(observed, HTTP) and observed.endpoint == "cms" and
            observed.status == 200 and observed.code == "" and
            observed.record_present is True and
            observed.publication_state == "PUBLISHED" and
            observed.content_key == key and observed.tenant_id == tenant)


def absent(observed, key):
    return (isinstance(observed, HTTP) and observed.endpoint == "cms" and
            observed.status == 200 and observed.record_present is False and
            observed.content_key == key)


def case_verdict(case, observations, tenant):
    """All observations are REQUIRED; missing tests are not default success.

    Negative credentials require issuer read-back in the eventual live owner,
    rather than treating a fabricated 401 as proof of disable/revocation.
    This helper checks expected transport results ONLY.
    """
    if case not in NAB03 or not isinstance(observations, tuple):
        return False
    if case == "published-home-nav-footer":
        return (len(observations) == 3 and
                all(published(item, key, tenant) for item, key in zip(observations, CONTENT)))
    if case in ("wrong-audience-token", "wrong-credential", "disabled-caller",
                "expired-caller-token", "revoked-caller-token"):
        return len(observations) == 1 and denial(observations[0], 401, "AUTHENTICATION_REQUIRED")
    if case == "missing-grant":
        return (len(observations) == 1 and isinstance(observations[0], HTTP) and
                observations[0].endpoint == "cp" and observations[0].status == 403)
    if case in ("wrong-owner-or-context", "neighbour-tenant"):
        return len(observations) == 1 and denial(observations[0], 403, "CONTENT_CONTEXT_REJECTED")
    if case == "draft-or-preview":
        return (len(observations) == 2 and
                denial(observations[0], 403, "CONTENT_PREVIEW_NOT_PERMITTED") and
                absent(observations[1], "home"))
    if case == "withdrawn-content":
        return len(observations) == 1 and absent(observations[0], "home")
    if case == "dependency-outage-and-restoration":
        return (len(observations) == 2 and
                denial(observations[0], 503, "CONTENT_CONTEXT_UNAVAILABLE") and
                published(observations[1], "home", tenant))
    if case == "validator-negatives":
        return (len(observations) == 2 and
                denial(observations[0], 401, "SUBJECT_TOKEN_INVALID", "cp") and
                denial(observations[1], 403, "CONTENT_CONTEXT_REJECTED"))
    if case == "teardown":
        return observations == ("VERIFIED_ACCEPTORS", "VERIFIED_ISSUER",
                                "VERIFIED_CP", "VERIFIED_PRIVATE")
    return False


class ObservationRegister:
    """Immutable run pins, explicit cases; never an independent gate review.

    Only the runner which actually invokes the real provider operations may
    supply results. This module cannot promote them beyond non-attested source
    observations, and cannot override the Shared registry hold.
    """

    def __init__(self, gate, tenant, *, live=False):
        if not live:
            raise Refused("real issuer/CP/CMS execution required")
        if not isinstance(gate, dict) or gate.get("schema") != "infrastructure.int03.cms-gate.v1":
            raise Refused("canonical registry gate missing")
        if not isinstance(gate.get("gate"), dict) or gate["gate"].get("verdict") != "OPEN":
            raise Refused("registry activation HELD or REFUSED")
        if gate.get("scenario") != "NAB-03" or gate.get("cases") != dict.fromkeys(CASES, "BLOCKED"):
            raise Refused("incomplete canonical case gate")
        if not isinstance(tenant, str) or not tenant or len(tenant) > 128:
            raise Refused("bounded CP tenant required")
        self.tenant = tenant
        self.gate = gate
        self.outcomes = dict.fromkeys(CASES, "BLOCKED")

    def record(self, case, observations):
        if case not in self.outcomes or self.outcomes[case] != "BLOCKED":
            raise Refused("case unknown or already evaluated")
        if not case_verdict(case, observations, self.tenant):
            raise Refused("case observations fail expected provider semantics")
        self.outcomes[case] = "OBSERVED_UNATTESTED"

    def receipt(self):
        return {
            "schema": SCHEMA,
            "scenario": "NAB-03",
            "case_count": len(CASES),
            "cases": self.outcomes.copy(),
            "identities": (CONSUMER, VALIDATOR),
            "evidence_class": "UNATTESTED_CONNECTED_OBSERVATION_CONTRACT",
            "qualified": False,
            "full_int03_acceptance": False,
            "independent_acceptance": False,
        }


def blocked_receipt():
    """The only acceptable local output while the activation hold is active."""
    return {
        "schema": SCHEMA, "scenario": "NAB-03",
        "cases": dict.fromkeys(CASES, "BLOCKED"),
        "identities_created": False, "qualified": False,
        "full_int03_acceptance": False,
        "reason": "CANONICAL_REGISTRY_ACTIVATION_HELD",
    }
