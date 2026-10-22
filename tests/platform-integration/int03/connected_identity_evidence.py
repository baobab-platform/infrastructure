"""INT-03C strict evidence boundary for connected IAM/CP negative qualification.

This module validates observations produced by a separate, real private runner.
It does not mint tokens, provision identities, or turn source tests into live PASS.
"""
import re

SHA = re.compile(r"[0-9a-f]{40}\\Z")
CASES = ("iam_issued_token", "cp_current_principal", "wrong_audience_denied",
         "cross_tenant_denied", "revoked_credential_denied",
         "deactivated_principal_denied", "independent_teardown")
DENIAL = frozenset((401, 403, 404))
SCHEMA = "infrastructure.int03c.connected-identity.v1"


class EvidenceRefused(ValueError):
    """Evidence is incomplete, inconsistent, or makes an unsupported claim."""


def validate(record, *, expected_sources):
    """Validate independently observed results; never infer observations.

    The connected runner must obtain real issuer and CP observations and
    bind them to exact clean source revisions. This function deliberately
    accepts no free-form tokens, response bodies, or user identifiers.
    """
    if type(record) is not dict or set(record) != {
        "schema", "sources", "synthetic", "provider", "observations",
        "teardown", "qualified", "nab03_qualified"
    }:
        raise EvidenceRefused("unexpected receipt shape")
    if (record["schema"] != SCHEMA or record["synthetic"] is not True or
        record["provider"] != "REAL_IAM_CP" or record["nab03_qualified"] is not False):
        raise EvidenceRefused("unsupported authority or acceptance claim")
    if (type(expected_sources) is not dict or not expected_sources or
        type(record["sources"]) is not dict or
        set(record["sources"]) != set(expected_sources) or
        any(type(sha) is not str or not SHA.fullmatch(sha) or
            record["sources"][name] != sha
            for name, sha in expected_sources.items())):
        raise EvidenceRefused("source pin mismatch")
    observations = record["observations"]
    if type(observations) is not dict or set(observations) != set(CASES):
        raise EvidenceRefused("missing connected case")
    for case in CASES:
        item = observations[case]
        if type(item) is not dict or set(item) != {"result", "http_status", "live"}:
            raise EvidenceRefused("invalid observation shape")
        if item["result"] not in ("PASS", "FAIL", "BLOCKED") or type(item["live"]) is not bool:
            raise EvidenceRefused("invalid case result")
        status = item["http_status"]
        if status is not None and (type(status) is not int or status < 100 or status > 599):
            raise EvidenceRefused("invalid HTTP observation")
        if item["result"] == "PASS":
            if not item["live"]:
                raise EvidenceRefused("source-only case cannot pass")
            if case in ("wrong_audience_denied", "cross_tenant_denied",
                        "revoked_credential_denied", "deactivated_principal_denied"):
                if status not in DENIAL:
                    raise EvidenceRefused("negative case did not deny")
            elif case == "independent_teardown":
                if status is not None:
                    raise EvidenceRefused("teardown must use independent readback")
            elif status != 200:
                raise EvidenceRefused("positive case not observed")
    teardown = record["teardown"]
    if teardown not in ("INDEPENDENTLY_VERIFIED", "FAILED", "NOT_RUN"):
        raise EvidenceRefused("unknown teardown outcome")
    complete = (teardown == "INDEPENDENTLY_VERIFIED" and
                all(observations[c]["result"] == "PASS" for c in CASES))
    if record["qualified"] is not complete or type(record["qualified"]) is not bool:
        raise EvidenceRefused("unsupported qualification")
    return complete
