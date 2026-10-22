"""Source-only negative tests: stubs cannot produce a live proof."""
import unittest
from connected_identity_evidence import EvidenceRefused
from connected_identity_revocation import supervised_revoke


class Issuer:
    def __init__(self,active=True):
        self.active=active
        self.revocations=0
    def discover(self): return True
    def execute(self,operation,fields,auth):
        if operation!="introspection_endpoint" or not auth.startswith("Basic "):
            raise EvidenceRefused("untrusted issuer client")
        return {"active":self.active,"client_id":"reviewed-owner",
                "aud":["baobab-control-plane"],"scope":"context:resolve","exp":1200}
    def assert_introspection(self,doc,*,client_id,audience,scope,now):
        if doc["active"] is not True or client_id!="reviewed-owner" or now>=1200:
            raise EvidenceRefused("issuer precondition invalid")
        return True
    def revoke(self,bearer,auth):
        if not auth.startswith("Basic ") or bearer!="t"*128:
            raise EvidenceRefused("issuer mutation refused")
        self.revocations+=1
        self.active=False
        return True
    def assert_revoked(self,doc,*,expiry,now):
        if doc["active"] is not False or now>=expiry:
            raise EvidenceRefused("natural expiry or active token")
        return True


class CP:
    def __init__(self,allow_first=True,deny_after=True):
        self.calls=0
        self.allow_first=allow_first
        self.deny_after=deny_after
    def request(self,method,path,bearer,payload):
        if (method!="POST" or path!="/v1/platform-context/resolve" or
            bearer!="t"*128):
            raise EvidenceRefused("CP context boundary")
        self.calls+=1
        if self.calls==1 and self.allow_first:
            return {"status":200,"code":"","document":{"tenant_id":payload["tenant_id"]}}
        if self.calls==2 and self.deny_after:
            return {"status":401,"code":"AUTH_TOKEN_REQUIRED","document":None}
        return {"status":403,"code":"TENANT_CONTEXT_MISMATCH","document":None}


def kwargs(issuer,cp,clock=lambda:1000):
    return dict(issuer=issuer,cp=cp,bearer="t"*128,owner="reviewed-owner",
       checker="reviewed-checker",owner_secret="a"*48,checker_secret="b"*48,
       audience="baobab-control-plane",scope="context:resolve",
       expected_expiry=1200,clock=clock,
       cp_own_tenant_context={"tenant_id":"tenant_cp_owned",
           "organisation_id":"org_cp_owned","country_code":"ZA",
           "expected_organisation_type":"ORGANISATION"})


class Revocation(unittest.TestCase):
    def test_real_authority_sequence_is_required(self):
        iam,cp=Issuer(),CP()
        result=supervised_revoke(**kwargs(iam,cp))
        self.assertEqual(iam.revocations,1)
        self.assertEqual(cp.calls,2)
        self.assertFalse(result["qualified"])
        self.assertFalse(result["independently_attested"])
        self.assertEqual(result["cp_original_token_after"]["status"],401)

    def test_was_never_accepted_by_cp_does_not_prove_revocation(self):
        iam,cp=Issuer(),CP(allow_first=False)
        with self.assertRaises(EvidenceRefused):
            supervised_revoke(**kwargs(iam,cp))
        self.assertEqual(iam.revocations,0)

    def test_revocation_does_not_count_while_natural_expiry(self):
        iam,cp=Issuer(),CP()
        with self.assertRaises(EvidenceRefused):
            supervised_revoke(**kwargs(iam,cp,clock=lambda:1190))
        self.assertEqual(iam.revocations,0)

    def test_unrelated_cp_denial_is_not_issuer_revocation_proof(self):
        iam,cp=Issuer(),CP(deny_after=False)
        with self.assertRaises(EvidenceRefused):
            supervised_revoke(**kwargs(iam,cp))
        self.assertEqual(iam.revocations,1)
        self.assertEqual(cp.calls,2)

    def test_source_does_not_revoke_foreign_or_duplicate_client(self):
        iam,cp=Issuer(),CP()
        bad=kwargs(iam,cp)
        bad["checker"]="reviewed-owner"
        with self.assertRaises(EvidenceRefused):
            supervised_revoke(**bad)
        self.assertEqual(iam.revocations,0)


if __name__=="__main__":
    unittest.main()
