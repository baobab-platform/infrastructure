"""Supervised issuer-revocation -> CP-denial witness for an unexpired token.

Called only with one governed INT-03C synthetic identity and an already
independently validated own-Tenant CP context. Does not create clients or
Principal records, deactivate Principal status, or promote NAB-03.
"""
from datetime import datetime, timezone

from connected_identity_evidence import EvidenceRefused
from connected_identity_cp import assert_negative
from connected_identity_issuer_run import basic


def supervised_revoke(*, issuer, cp, bearer, owner, checker, owner_secret,
                      checker_secret, audience, scope, expected_expiry,
                      cp_own_tenant_context, clock=None):
    """A pre-revocation CP positive is essential to rule out unrelated denial.

    Issuer revocation acknowledgement alone is not accepted. A separate
    verifier must independently read the active->inactive transition before
    token expiry; CP must then reject use of the SAME unexpired bearer.
    """
    clock=clock or (lambda:int(datetime.now(timezone.utc).timestamp()))
    if (not isinstance(bearer,str) or not 32<=len(bearer)<=16384 or
        owner==checker or owner_secret==checker_secret or
        type(expected_expiry) is not int or clock()+45>=expected_expiry or
        not isinstance(cp_own_tenant_context,dict) or
        set(cp_own_tenant_context)!={"tenant_id","organisation_id",
                                    "country_code","expected_organisation_type"}):
        raise EvidenceRefused("bounded governed revocation input required")
    owner_auth=basic(owner,owner_secret)
    checker_auth=basic(checker,checker_secret)
    issuer.discover()
    def readback():
        return issuer.execute("introspection_endpoint",
               {"token":bearer,"token_type_hint":"access_token"},checker_auth)
    before=readback()
    issuer.assert_introspection(before,client_id=owner,audience=audience,
                                scope=scope,now=clock())
    cp_before=cp.request("POST","/v1/platform-context/resolve",
                         bearer,cp_own_tenant_context)
    if (cp_before.get("status")!=200 or
        not isinstance(cp_before.get("document"),dict) or
        cp_before["document"].get("tenant_id")!=cp_own_tenant_context["tenant_id"]):
        raise EvidenceRefused("CP did not accept this token before revocation")
    # Nothing can assert a PASS between this mutation and independent proof.
    issuer.revoke(bearer,owner_auth)
    after=readback()
    issuer.assert_revoked(after,expiry=expected_expiry,now=clock())
    cp_after=cp.request("POST","/v1/platform-context/resolve",
                        bearer,cp_own_tenant_context)
    assert_negative(cp_after,"revoked_credential_denied")
    if clock()>=expected_expiry:
        raise EvidenceRefused("token expired naturally before CP denial")
    return {
        "schema":"infrastructure.int03c.revocation-observation.v1",
        "issuer_readback":"ACTIVE_TO_INACTIVE_BEFORE_EXPIRY",
        "cp_original_token_before":"HTTP_200",
        "cp_original_token_after":{
            "status":cp_after["status"],"code":cp_after["code"]},
        "principal_deactivation":"NOT_PERFORMED",
        "independently_attested":False,
        "qualified":False,"nab03_qualified":False,
    }
