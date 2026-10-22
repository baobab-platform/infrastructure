"""INT-03C bounded evidence contract for REAL IAM->CP observations.

A receipt describes observations, NOT an independently accepted PASS. Only a
separately retained and reviewed connected execution can qualify INT-03C.
A mock can satisfy structure: this module never attests provider provenance,
the correctness of revoked tokens, or live acceptance. NAB-03 is distinct.
"""
import re

SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
CASES = (
    "iam_issued_token", "cp_current_principal", "wrong_audience_denied",
    "cross_tenant_denied", "revoked_credential_denied",
    "deactivated_principal_denied", "independent_teardown",
)
SCHEMA = "infrastructure.int03c.connected-identity.v2"
SOURCES = frozenset(("infrastructure", "baobab-iam", "baobab-cp", "shared"))
PROOFS = frozenset((
    "actual_issuer_token", "cp_principal_readback", "wrong_audience_issuer",
    "second_governed_tenant", "issuer_revocation_readback",
    "cp_deactivation_readback", "independent_teardown_readback",
))
AUTHORITY = {
    "iam_issued_token": "iam",
    "cp_current_principal": "cp",
    "wrong_audience_denied": "cp",
    "cross_tenant_denied": "cp",
    "revoked_credential_denied": "cp",
    "deactivated_principal_denied": "cp",
    "independent_teardown": "independent",
}
DENIALS = {
    "wrong_audience_denied": {(401, "AUTH_TOKEN_REQUIRED"), (403, "CALLER_NOT_PERMITTED")},
    "cross_tenant_denied": {(403, "TENANT_CONTEXT_MISMATCH"),
                             (403, "CONTEXT_DENIED"), (404, "CONTEXT_NOT_FOUND")},
    "revoked_credential_denied": {(401, "AUTH_TOKEN_REQUIRED"),
                                   (401, "SUBJECT_TOKEN_INVALID"),
                                   (403, "CALLER_NOT_PERMITTED")},
    "deactivated_principal_denied": {(403, "IDENTITY_RESOLUTION_FAILED"),
                                      (403, "CONTEXT_DENIED"),
                                      (403, "PRINCIPAL_NOT_ACTIVE"),
                                      (403, "TENANT_CONTEXT_MISMATCH")},
}


class EvidenceRefused(ValueError):
    """Evidence attempts an unverified authority claim or lacks required facts."""


def validate(record, *, expected_sources):
    """Validate an *unattested candidate* and never return qualification.

    Candidate completeness is useful for a downstream independent reviewer,
    but a JSON field, Boolean 'live', or synthetic test cannot establish that
    a network operation actually happened. In particular, a revoked JWT must
    be denied *while its exp has not passed*, with separate issuer readback.
    """
    required = {
        "schema", "sources", "synthetic", "provider", "observations", "proofs",
        "teardown", "qualified", "nab03_qualified", "independent_acceptance",
        "evidence_class",
    }
    if type(record) is not dict or set(record) != required:
        raise EvidenceRefused("closed INT-03C receipt shape required")
    if (record["schema"] != SCHEMA or record["synthetic"] is not True or
        record["provider"] != "IAM_CP_REAL_SERVICES" or
        record["qualified"] is not False or record["nab03_qualified"] is not False or
        record["independent_acceptance"] is not False or
        record["evidence_class"] != "OBSERVED_UNATTESTED"):
        raise EvidenceRefused("source evidence cannot claim certification")
    if (type(expected_sources) is not dict or set(expected_sources) != SOURCES or
        type(record["sources"]) is not dict or set(record["sources"]) != SOURCES or
        any(type(sha) is not str or SHA.fullmatch(sha) is None or
            record["sources"][name] != sha for name, sha in expected_sources.items())):
        raise EvidenceRefused("exact immutable source pins required")
    proofs = record["proofs"]
    if (type(proofs) is not dict or set(proofs) != PROOFS or
        any(value is not None and
            (type(value) is not str or not DIGEST.fullmatch(value))
            for value in proofs.values())):
        raise EvidenceRefused("missing or malformed original-proof digest")
    observations = record["observations"]
    if type(observations) is not dict or set(observations) != set(CASES):
        raise EvidenceRefused("seven case observations required")
    observed = 0
    for case in CASES:
        item = observations[case]
        if type(item) is not dict or set(item) != {
            "result", "http_status", "code", "authority", "evidence_digest",
        }:
            raise EvidenceRefused("unexpected per-case evidence")
        if item["result"] not in ("OBSERVED", "BLOCKED", "FAILED"):
            raise EvidenceRefused("source cannot report accepted PASS")
        status, code = item["http_status"], item["code"]
        if status is not None and (type(status) is not int or not 100 <= status <= 599):
            raise EvidenceRefused("invalid HTTP result")
        if type(code) is not str or len(code) > 64 or not re.fullmatch(r"[A-Z_]*", code):
            raise EvidenceRefused("unbounded problem code")
        if item["authority"] != AUTHORITY[case]:
            raise EvidenceRefused("wrong identity/CP observation origin")
        digest = item["evidence_digest"]
        if digest is not None and (type(digest) is not str or not DIGEST.fullmatch(digest)):
            raise EvidenceRefused("invalid original case evidence")
        if item["result"] == "OBSERVED":
            if not isinstance(digest, str):
                raise EvidenceRefused("missing externally retrievable case evidence")
            if case in DENIALS and (status, code) not in DENIALS[case]:
                raise EvidenceRefused("negative case did not deny as specified")
            if case == "independent_teardown":
                if status is not None or code:
                    raise EvidenceRefused("teardown requires independent non-HTTP verification")
            elif case in ("iam_issued_token", "cp_current_principal") and (status != 200 or code):
                raise EvidenceRefused("positive issuer/CP readback was not 200")
            observed += 1
        elif status is not None or code or digest is not None:
            raise EvidenceRefused("failed/blocked case cannot claim a verified observation")
    if record["teardown"] not in ("INDEPENDENTLY_OBSERVED_UNATTESTED", "FAILED", "NOT_RUN"):
        raise EvidenceRefused("invalid cleanup authority")
    candidate = (
        observed == len(CASES) and
        record["teardown"] == "INDEPENDENTLY_OBSERVED_UNATTESTED" and
        all(isinstance(value, str) for value in proofs.values())
    )
    if record["teardown"] == "INDEPENDENTLY_OBSERVED_UNATTESTED" and (
        observations["independent_teardown"]["result"] != "OBSERVED" or
        proofs["independent_teardown_readback"] is None):
        raise EvidenceRefused("teardown lacks independent evidence")
    # This Boolean means structurally complete *only*. Never qualified.
    return candidate


def blocked_receipt(sources):
    """Safe HELD/pending receipt; no issuer/CP mutation or PASS."""
    if type(sources) is not dict or set(sources) != SOURCES or any(
        type(x) is not str or not SHA.fullmatch(x) for x in sources.values()
    ):
        raise EvidenceRefused("exact source pins required")
    return {
        "schema": SCHEMA, "sources": dict(sources), "synthetic": True,
        "provider": "IAM_CP_REAL_SERVICES", "observations": {
            case: {"result": "BLOCKED", "http_status": None, "code": "",
                   "authority": AUTHORITY[case], "evidence_digest": None}
            for case in CASES
        }, "proofs": dict.fromkeys(PROOFS), "teardown": "NOT_RUN",
        "qualified": False, "nab03_qualified": False,
        "independent_acceptance": False, "evidence_class": "OBSERVED_UNATTESTED",
    }
