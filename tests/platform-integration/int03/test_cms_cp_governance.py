"""CP-owned topology tests. Fake replies test fail-closed guards only.

No fake CP object is evidence of actual registration, grant, release,
certification, market activation, engine binding or connected NAB-03.
"""
import unittest
import uuid

from cms_cp_governance import Fixture, Operator, Refused, CERTIFY_ROUTE


def ident():
    return str(uuid.uuid4())


class FakeCP:
    """Test adapter only: every call is recorded, never a real authority."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def call(self, operator, method, path, *, body=None, idempotency=None,
             if_match=None, expect=(200,)):
        self.calls.append((operator, method, path, body, idempotency, if_match, expect))
        if not self.responses:
            raise Refused("CP mock exhausted")
        return self.responses.pop(0)


class CPContract(unittest.TestCase):
    def setUp(self):
        self.maker=Operator(ident(), "maker_private_placeholder_" + "a"*32, "maker")
        self.checker=Operator(ident(), "checker_private_placeholder_" + "b"*32, "checker")
    def fixture(self, replies):
        cp=FakeCP(replies)
        return Fixture(cp,self.maker,self.checker),cp

    def test_two_distinct_human_cp_principals_required(self):
        with self.assertRaises(Refused):
            Fixture(FakeCP([]),self.maker,self.maker)
        with self.assertRaises(Refused):
            Fixture(FakeCP([]),Operator(self.maker.principal_id,self.maker.credential,"checker"),self.maker)

    def test_operator_tokens_resolve_to_independent_active_cp_principals(self):
        f,cp=self.fixture([{"principal_id":self.maker.principal_id},
                           {"principal_id":self.checker.principal_id}])
        self.assertTrue(f.verify_operator_registration())
        self.assertEqual([x[2] for x in cp.calls],
                         ["/v1/admin/effective-authority"]*2)
        f,_=self.fixture([{"principal_id":self.checker.principal_id}])
        with self.assertRaises(Refused):
            f.verify_operator_registration()

    def test_canonical_tenant_is_cp_minted_after_authorised_onboarding(self):
        approved={"tenant_onboarding_request_id":"tor_reviewed",
                  "legal_entity_id":"reviewed-entity","display_name":"INT03 synthetic",
                  "isolation_strategy":"row_level_security","residency_region":"af-south-1"}
        f,cp=self.fixture([{"operation_id":"op_accepted"}])
        r=f.register_tenant(approved,key="int03-tenant-idempotent-2026")
        self.assertFalse(r["tenant_registered"])
        self.assertFalse(r["qualified"])
        self.assertEqual(cp.calls[0][2],"/v1/tenants")
        self.assertEqual(cp.calls[0][1],"POST")
        self.assertEqual(cp.calls[0][6],(202,))
        for wrong in (dict(approved,tenant_id=ident()),dict(approved,status="ACTIVE"),
                      dict(approved,bootstrap_reason="copy"),
                      {k:v for k,v in approved.items() if k!="tenant_onboarding_request_id"}):
            with self.assertRaises(Refused):
                f.register_tenant(wrong,key="int03-tenant-idempotent-2026")

    def test_cp_verified_admission_cannot_forge_organisation_identity(self):
        tenant=ident()
        approved={"admission_decision_id":"admission_decision_abc",
                  "verification_case_id":"vcase_reviewed",
                  "applicant_organisation":{"legal_name":"Synthetic Lab",
                                            "registration_identifiers":[{"value":"synthetic"}]},
                  "platform_account":{"assignment":"reviewed"}}
        f,cp=self.fixture([{"identity_resolution":"NEW_ORGANISATION"}])
        result=f.admit_organisation(tenant,approved)
        self.assertFalse(result["qualified"])
        self.assertTrue(cp.calls[0][2].endswith("/organisation-admission"))
        with self.assertRaises(Refused):
            f.admit_organisation(tenant,dict(approved,verified=True))

    def test_market_maker_checker_and_independent_get(self):
        tenant=ident()
        mid="mkt_abc123"
        mk={"market_id":mid,"owner_tenant_id":tenant,"created_by":self.maker.principal_id,
            "status":"VALIDATED","revision":1}
        active=dict(mk,status="ACTIVE",activated_by=self.checker.principal_id,revision=2)
        f,cp=self.fixture([mk,mk,{},active])
        got=f.create_market({"owner_tenant_id":tenant,"canonical_key":"int03.za",
                             "market_type":"COUNTRY", "name":"Synthetic ZA"},
                            key="int03-market-seed-v1")
        self.assertEqual(got,mid)
        read=f.activate_market(mid,reason="Independent synthetic lab approval")
        self.assertEqual(read["status"],"ACTIVE")
        self.assertEqual([x[1] for x in cp.calls],["POST","GET","POST","GET"])
        self.assertEqual(cp.calls[2][5],'"1"')
        self.assertEqual(cp.calls[2][0].principal_id,self.checker.principal_id)
        bad=FakeCP([dict(mk,created_by=self.checker.principal_id)])
        with self.assertRaises(Refused):
            Fixture(bad,self.maker,self.checker).activate_market(mid,reason="Independent synthetic lab approval")
        with self.assertRaises(Refused):
            f.create_market({"owner_tenant_id":tenant,"status":"ACTIVE"},key="int03-market-seed-v1")

    def test_principal_grants_through_cp_only(self):
        principal=ident()
        gid="agr_synthetic1"
        f,cp=self.fixture([{"grant_id":gid},{"grant_id":gid,"principal_id":principal,"status":"ACTIVE"}])
        got=f.issue_existing_principal_grant(principal,"administrator.read",
            {"level":"TENANT","tenant_id":ident()},
            grant_type="STANDING",reason="Development-only synthetic proof",key="int03-grant-1234567890")
        self.assertEqual(got,gid)
        f.verify_grant(gid,principal)
        self.assertEqual(cp.calls[0][2],"/v1/admin/grants")
        with self.assertRaises(Refused):
            f.issue_existing_principal_grant(ident(),"x",{"level":"PLATFORM"},
                grant_type="DIRECT",reason="Development-only synthetic proof",key="int03-grant-1234567890")

    def test_release_recording_not_approval(self):
        release={"release_id":"erl_123abc","recorded_by":self.maker.principal_id,"status":"CANDIDATE"}
        f,cp=self.fixture([release])
        reviewed={"engine_id":"baobab-cms","source_revision":"a"*40,
                  "artifacts":[{"digest":"sha256:"+"a"*64}],
                  "provider_support":[{"provider_key":"baobab-cms.payload","capability_key":"content.entry.resolve","contract_versions":[1]}]}
        r=f.record_engine_release(reviewed)
        self.assertEqual(r,"erl_123abc")
        self.assertEqual(cp.calls[0][2],"/v1/engine-releases")
        with self.assertRaises(Refused):
            f.record_engine_release(dict(reviewed,status="APPROVED"))

    def test_certification_requires_independent_approved_release_and_digest(self):
        rid="erl_123abc"
        pid="provider_synthetic"
        key="content.entry.resolve"
        cert_id="cert_"+"a"*32
        release={"release_id":rid,"recorded_by":self.maker.principal_id,"status":"APPROVED"}
        certificate={"certification_id":cert_id,"certified_by":self.checker.principal_id,
                     "release_id":rid,"provider_id":pid,"capability_key":key,
                     "contract_version":1,"qualification_profile":"int03.cms.actual",
                     "status":"CERTIFIED"}
        f,cp=self.fixture([release,{"certification_id":cert_id},certificate])
        evidence=[{"type":"INTEGRATION_TEST","uri":"https://github.com/baobab-platform/infrastructure/actions/runs/123",
                   "digest":"sha256:"+"a"*64}]
        certificate["evidence"]=evidence
        result=f.certify_provider(provider_id=pid,capability_key=key,release_id=rid,
                   contract_version=1,evidence=evidence,qualification_profile="int03.cms.actual")
        self.assertEqual(result["status"],"CERTIFIED")
        self.assertEqual(result["evidence"],evidence)
        self.assertEqual(cp.calls[1][2],CERTIFY_ROUTE)
        self.assertEqual(cp.calls[1][0].principal_id,self.checker.principal_id)
        f2,_=self.fixture([dict(release,recorded_by=self.checker.principal_id)])
        with self.assertRaises(Refused):
            f2.certify_provider(provider_id=pid,capability_key=key,release_id=rid,
                       contract_version=1,evidence=evidence,qualification_profile="int03.cms.actual")
        f3,_=self.fixture([release])
        with self.assertRaises(Refused):
            f3.certify_provider(provider_id=pid,capability_key=key,release_id=rid,
                       contract_version=1,evidence=[{"uri":"https://e","digest":"unverified"}],
                       qualification_profile="int03.cms.actual")

    def test_current_certified_provider_requires_actual_cp_resolver(self):
        cert_id="cert_"+"a"*32
        ctx=ident()
        provider="provider_abc123"
        instance="instance_abc123"
        cap="content.entry.resolve"
        cert={"certification_id":cert_id,"certified_by":self.checker.principal_id,
              "status":"CERTIFIED","provider_id":provider,"capability_key":cap,
              "contract_version":1}
        f,_=self.fixture([cert])
        def resolve(body):
            self.assertEqual(body["context_id"],ctx)
            self.assertEqual(body["required_contract_version"],1)
            return {"decision":"RESOLVED","context_id":ctx,"capability_key":cap,
                    "grant_id":"grant_abc123","binding_id":"bind_abc123",
                    "invocation":{"provider_id":provider,
                                  "engine_instance_id":instance,"contract_version":1}}
        r=f.verify_resolved_provider(resolve,context_id=ctx,provider_id=provider,
                  engine_instance_id=instance,capability_key=cap,certification_id=cert_id)
        self.assertFalse(r["qualified"])
        f,_=self.fixture([cert])
        with self.assertRaises(Refused):
            f.verify_resolved_provider(lambda b: dict(resolve(b),decision="DENIED"),
                   context_id=ctx,provider_id=provider,engine_instance_id=instance,
                   capability_key=cap,certification_id=cert_id)
        f,_=self.fixture([dict(cert,status="REVOKED")])
        with self.assertRaises(Refused):
            f.verify_resolved_provider(resolve,context_id=ctx,
                    provider_id=provider,engine_instance_id=instance,
                    capability_key=cap,certification_id=cert_id)

    def test_binding_changeset_cannot_claim_runtime_acceptance(self):
        cs="cs_123abc"
        digest="sha256:"+"a"*64
        record={"changeset_id":cs,"requested_by":self.maker.principal_id,
                "approval_id":"approval_123","state":"COMPLETED",
                "current_plan":{"plan_digest":digest}}
        outcome={"changeset_id":cs,"final_state":"COMPLETED",
                 "applied_plan_digest":digest}
        f,cp=self.fixture([record,outcome])
        r=f.verify_changeset_binding(cs)
        self.assertFalse(r["qualified"])
        self.assertIn("RUNTIME_RESOLVER_PROOF",r["review"])
        f,_=self.fixture([record,dict(outcome,applied_plan_digest="sha256:"+"b"*64)])
        with self.assertRaises(Refused):
            f.verify_changeset_binding(cs)
        self.assertEqual(cp.calls[0][2],"/v1/admin/changesets/"+cs)
        with self.assertRaises(Refused):
            f.verify_changeset_binding("client_supplied_UUID")

    def test_missing_or_cross_tenant_cp_get_is_denied(self):
        tenant=ident()
        f,_=self.fixture([{"tenant_id":ident()}])
        with self.assertRaises(Refused):
            f.verify_tenant(tenant)
        f,_=self.fixture([{"organisation_id":ident()}])
        with self.assertRaises(Refused):
            f.verify_organisation(ident())


if __name__ == "__main__":
    unittest.main()
