"""Source tests cannot mint actual CP Principals or independent approval."""
import unittest
import uuid

from cms_cp_governance import CPGateway, Operator, Refused
from connected_identity_cp_lifecycle import GovernedPrincipal, LifecycleProof


class FakeGateway(CPGateway):
    """Deliberate test-only adapter; no network evidence or acceptance."""
    def __init__(self,principal,maker,checker):
        self.target=principal
        self.maker=maker
        self.checker=checker
        self.stage="ACTIVE"
        self.calls=[]
        self.reference=str(uuid.uuid4())
        self.digest="sha256:"+"a"*64

    def call(self,operator,method,path,*,body=None,idempotency=None,
             if_match=None,expect=(200,)):
        self.calls.append((operator.principal_id,method,path,body))
        if path=="/v1/admin/effective-authority":
            return {"principal_id":operator.principal_id}
        if path.endswith(self.target):
            return {"principal_id":self.target,"status":self.stage}
        if method=="POST" and path.endswith("deactivation-requests"):
            if operator.principal_id!=self.maker.principal_id:
                raise Refused("wrong maker")
            return {"principal_id":self.target,"request_id":self.reference,
                    "plan_digest":self.digest,"decision":"PENDING",
                    "expires_at":"2026-11-01T00:00:00Z"}
        if method=="POST" and path.endswith("/approve"):
            if operator.principal_id!=self.checker.principal_id or body.get("plan_digest")!=self.digest:
                raise Refused("unapproved")
            self.stage="DISABLED"
            return {"principal_id":self.target,"request_id":self.reference,
                    "plan_digest":self.digest,"decision":"COMPLETED"}
        raise Refused("unknown source-only operation")


class GovernedTests(unittest.TestCase):
    def setUp(self):
        self.principal=str(uuid.uuid4())
        self.maker=Operator(str(uuid.uuid4()),"private-maker-token-"+"m"*48,"maker")
        self.checker=Operator(str(uuid.uuid4()),"private-checker-token-"+"c"*48,"checker")
        self.cp=FakeGateway(self.principal,self.maker,self.checker)
        self.boundary=GovernedPrincipal(self.cp,self.maker,self.checker)

    def proposed(self):
        return self.boundary.propose(self.principal,subject="baobab-int03c-issuer-owner",
               run="b"*32,source_sha="c"*40,idempotency_key=str(uuid.uuid4()))

    def test_both_humans_and_exact_cp_digest(self):
        proposed=self.proposed()
        self.assertFalse(proposed.qualified)
        self.assertEqual(proposed.status,"PENDING")
        finished=self.boundary.independently_approve(proposed)
        self.assertEqual(finished.status,"CP_DISABLED_OBSERVED_UNATTESTED")
        self.assertFalse(finished.qualified)
        self.assertEqual(self.cp.stage,"DISABLED")
        self.assertTrue(any(c[0]==self.maker.principal_id and c[1]=="POST" for c in self.cp.calls))
        self.assertTrue(any(c[0]==self.checker.principal_id and c[1]=="POST" for c in self.cp.calls))

    def test_forbidden_maker_same_as_checker(self):
        with self.assertRaises(Refused):
            GovernedPrincipal(self.cp,self.maker,self.maker)

    def test_stale_principal_or_wrong_target_denied(self):
        self.cp.stage="DISABLED"
        with self.assertRaises(Refused):
            self.proposed()
        self.cp.stage="ACTIVE"
        with self.assertRaises(Refused):
            self.boundary.propose(str(uuid.uuid4()),subject="baobab-int03-cms-consumer",
                run="b"*32,source_sha="c"*40,idempotency_key=str(uuid.uuid4()))

    def test_cannot_claim_checker_approval_from_maker(self):
        proposed=self.proposed()
        self.cp.checker=self.maker
        with self.assertRaises(Refused):
            self.boundary.independently_approve(proposed)

    def test_digest_mismatch_denied(self):
        proposal=self.proposed()
        with self.assertRaises(Refused):
            self.boundary.independently_approve(
                LifecycleProof(proposal.principal_id,proposal.request_id,
                               "sha256:"+"f"*64,"PENDING"))
