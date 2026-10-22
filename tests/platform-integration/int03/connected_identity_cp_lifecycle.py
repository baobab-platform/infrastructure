"""INT-03C governed CP Principal deactivation HTTP client.

The only side effect is through CP's separately approved nonproduction
maker/checker endpoint, never direct Postgres, token editing or IAM Admin.
Requires ACTIVE real human CP admins and compares actual independent CP
Principal state before and after exact digest-bound completion.
"""
from dataclasses import dataclass
import re

from cms_cp_governance import CPGateway, Fixture, Operator, Refused, canonical_uuid

EXACT_SUBJECTS=frozenset(("baobab-int03c-issuer-owner","baobab-int03c-issuer-verifier"))
RUN=re.compile(r"[0-9a-f]{32}\Z")
SHA=re.compile(r"[0-9a-f]{40}\Z")
DIGEST=re.compile(r"sha256:[0-9a-f]{64}\Z")
BASE="/v1/admin/int03c"


@dataclass(frozen=True)
class LifecycleProof:
    principal_id: str
    request_id: str
    plan_digest: str
    status: str
    qualified: bool=False


class GovernedPrincipal:
    """CP alone changes canonical Principal status; caller owns no SQL."""

    def __init__(self,cp,maker,checker):
        if not isinstance(cp,CPGateway):
            raise Refused("real CP-only private transport required")
        self.fixture=Fixture(cp,maker,checker)
        self.cp,self.maker,self.checker=cp,maker,checker

    def verify_admins(self):
        return self.fixture.verify_operator_registration()

    def read(self, principal, *, checker=True):
        canonical_uuid(principal)
        response=self.cp.call(self.checker if checker else self.maker,
          "GET",f"{BASE}/principals/{principal}")
        if response.get("principal_id")!=principal or response.get("status") not in ("ACTIVE","DISABLED"):
            raise Refused("CP canonical current Principal readback differs")
        return response["status"]

    def propose(self,principal,*,subject,run,source_sha,idempotency_key):
        canonical_uuid(principal)
        canonical_uuid(idempotency_key)
        if subject not in EXACT_SUBJECTS or not isinstance(run,str) or not RUN.fullmatch(run) or (
            not isinstance(source_sha,str) or not SHA.fullmatch(source_sha)):
            raise Refused("reviewed canonical synthetic identity absent")
        self.verify_admins()
        if self.read(principal,checker=False)!="ACTIVE":
            raise Refused("target was not ACTIVE before authorisation")
        response=self.cp.call(self.maker,"POST",f"{BASE}/principals/{principal}/deactivation-requests",
            body={"issuer":"https://hydra.int03.test",
                  "subject":subject,"run_id":run,
                  "source_sha":source_sha,
                  "idempotency_key":idempotency_key},
            expect=(202,))
        ident=response.get("request_id")
        digest=response.get("plan_digest")
        if (not isinstance(ident,str) or not isinstance(digest,str) or
            not DIGEST.fullmatch(digest) or
            response.get("principal_id")!=principal or
            response.get("decision")!="PENDING" or
            not isinstance(response.get("expires_at"),str)):
            raise Refused("CP issued no independently approvable immutable plan")
        canonical_uuid(ident)
        return LifecycleProof(principal,ident,digest,"PENDING")

    def independently_approve(self,proof):
        if not isinstance(proof,LifecycleProof) or proof.status!="PENDING" or proof.qualified:
            raise Refused("only original pending CP plan may be approved")
        if self.read(proof.principal_id)!="ACTIVE":
            raise Refused("CP Principal changed before independent approval")
        response=self.cp.call(self.checker,"POST",
            f"{BASE}/deactivation-requests/{proof.request_id}/approve",
            body={"plan_digest":proof.plan_digest},expect=(200,))
        if (response.get("request_id")!=proof.request_id or
            response.get("principal_id")!=proof.principal_id or
            response.get("plan_digest")!=proof.plan_digest or
            response.get("decision")!="COMPLETED"):
            raise Refused("CP checker did not apply exact approved plan")
        if self.read(proof.principal_id)!="DISABLED":
            raise Refused("CP still recognises ACTIVE canonical Principal")
        return LifecycleProof(proof.principal_id,proof.request_id,
                              proof.plan_digest,"CP_DISABLED_OBSERVED_UNATTESTED")
