"""Source-only INT-03C evidence tests: these never qualify real IAM/CP."""
import unittest

from connected_identity_evidence import (
    AUTHORITY, CASES, PROOFS, SCHEMA, EvidenceRefused, blocked_receipt, validate,
)

SOURCES = {"infrastructure": "a" * 40, "baobab-iam": "b" * 40,
           "baobab-cp": "c" * 40, "shared": "d" * 40}
DENIAL = {
    "wrong_audience_denied": (401, "AUTH_TOKEN_REQUIRED"),
    "cross_tenant_denied": (403, "TENANT_CONTEXT_MISMATCH"),
    "revoked_credential_denied": (401, "SUBJECT_TOKEN_INVALID"),
    "deactivated_principal_denied": (403, "PRINCIPAL_NOT_ACTIVE"),
}


def sample():
    record = blocked_receipt(SOURCES)
    for case in CASES:
        status, code = DENIAL.get(case, (None, "") if case == "independent_teardown" else (200, ""))
        record["observations"][case] = {
            "result": "OBSERVED", "http_status": status, "code": code,
            "authority": AUTHORITY[case], "evidence_digest": "sha256:" + "e" * 64,
        }
    record["proofs"] = dict.fromkeys(PROOFS, "sha256:" + "f" * 64)
    record["teardown"] = "INDEPENDENTLY_OBSERVED_UNATTESTED"
    return record


class EvidenceTests(unittest.TestCase):
    def test_complete_candidate_is_explicitly_not_qualified(self):
        record = sample()
        self.assertTrue(validate(record, expected_sources=SOURCES))
        self.assertIs(record["qualified"], False)
        self.assertIs(record["independent_acceptance"], False)
        self.assertIs(record["nab03_qualified"], False)

    def test_blocked_is_valid_but_not_complete(self):
        r=blocked_receipt(SOURCES)
        self.assertEqual(r["schema"], SCHEMA)
        self.assertFalse(validate(r, expected_sources=SOURCES))
        self.assertEqual(set(r["observations"]), set(CASES))

    def test_missing_case_fails(self):
        r = sample()
        del r["observations"]["cross_tenant_denied"]
        with self.assertRaises(EvidenceRefused):
            validate(r, expected_sources=SOURCES)

    def test_revocation_must_deny_and_have_original_readback(self):
        r = sample()
        r["observations"]["revoked_credential_denied"]["http_status"] = 200
        with self.assertRaises(EvidenceRefused):
            validate(r, expected_sources=SOURCES)
        r=sample()
        r["proofs"]["issuer_revocation_readback"]=None
        self.assertFalse(validate(r,expected_sources=SOURCES))
        r=sample()
        r["observations"]["revoked_credential_denied"]["code"]="TENANT_CONTEXT_MISMATCH"
        with self.assertRaises(EvidenceRefused):
            validate(r,expected_sources=SOURCES)

    def test_missing_real_evidence_digest_refused(self):
        r=sample()
        r["observations"]["cp_current_principal"]["evidence_digest"]=None
        with self.assertRaises(EvidenceRefused):
            validate(r, expected_sources=SOURCES)

    def test_no_mock_pass_or_self_qualification(self):
        for change in (
            {"qualified":True}, {"independent_acceptance":True},
            {"nab03_qualified":True}, {"provider":"SYNTHETIC_DOUBLE"},
            {"evidence_class":"ACCEPTED"},
        ):
            r=sample()
            r.update(change)
            with self.assertRaises(EvidenceRefused):
                validate(r,expected_sources=SOURCES)
        r=sample()
        r["observations"]["cp_current_principal"]["result"]="PASS"
        with self.assertRaises(EvidenceRefused):
            validate(r,expected_sources=SOURCES)

    def test_teardown_required(self):
        r=sample()
        r["teardown"]="NOT_RUN"
        self.assertFalse(validate(r,expected_sources=SOURCES))
        r=sample()
        r["observations"]["independent_teardown"]["result"]="BLOCKED"
        r["observations"]["independent_teardown"]["http_status"]=None
        r["observations"]["independent_teardown"]["evidence_digest"]=None
        with self.assertRaises(EvidenceRefused):
            validate(r,expected_sources=SOURCES)

    def test_wrong_pin_and_invalid_regex_rejected(self):
        r=sample()
        r["sources"]["baobab-cp"]="e"*40
        with self.assertRaises(EvidenceRefused):
            validate(r,expected_sources=SOURCES)
        r=sample()
        r["sources"]["baobab-cp"]="c"*39+"\\Z"
        with self.assertRaises(EvidenceRefused):
            validate(r,expected_sources=SOURCES)

    def test_explicit_unqualified_failure_allowed(self):
        r=sample()
        r["observations"]["cross_tenant_denied"]={
            "result":"FAILED","http_status":None,"code":"",
            "authority":"cp","evidence_digest":None,
        }
        self.assertFalse(validate(r,expected_sources=SOURCES))

    def test_no_credential_extra_metadata(self):
        r=sample()
        r["observations"]["cp_current_principal"]["subject_token"]="secret"
        with self.assertRaises(EvidenceRefused):
            validate(r,expected_sources=SOURCES)
        r=sample()
        r["proofs"]["raw_token"]="leak"
        with self.assertRaises(EvidenceRefused):
            validate(r,expected_sources=SOURCES)


if __name__ == "__main__":
    unittest.main()
