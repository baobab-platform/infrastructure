"""Explicit, CP-API-only operator workflow for synthetic CMS topology.

A single step is submitted per invocation. The CP, not this CLI, controls
status, IDs, changeset approvals, grants, provider certification and runtime
selection. No unattended admin token, bootstrap, SQL injection, fake issuer,
or automatic maker/checker escalation. A step can be prepared under #354 HELD,
but this is NOT identity activation or NAB-03 qualification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from cms_cp_governance import CPGateway, Fixture, Operator, Refused

PLAN_SCHEMA = "infrastructure.int03.cp-governed-fixture-plan.v1"
STEPS = frozenset({"tenant", "organisation", "market", "market-activate",
                   "principal-grant", "engine-release", "provider-certify",
                   "provisioning-create", "provisioning-approve", "provisioning-apply",
                   "provisioning-verify"})
RUN_ID = re.compile(r"int03-cp-[a-z0-9-]{12,90}\Z")


def private_file(path):
    file = Path(path)
    stat = file.lstat()
    if file.is_symlink() or not file.is_file() or stat.st_uid != os.getuid() or stat.st_mode & 0o077:
        raise Refused("private operator evidence file must be owner-only")
    if stat.st_size < 1 or stat.st_size > 65536:
        raise Refused("bounded private operator evidence required")
    return file.read_text(encoding="utf-8").strip()


def read_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    if (not isinstance(plan, dict) or set(plan) !=
        {"schema", "run_id", "environment", "step", "document", "idempotency_key"} or
        plan["schema"] != PLAN_SCHEMA or plan["environment"] != "development" or
        plan["step"] not in STEPS or
        not isinstance(plan["document"], dict) or
        not RUN_ID.fullmatch(plan["run_id"]) or
        not isinstance(plan["idempotency_key"], str) or
        not re.fullmatch(r"[a-zA-Z0-9._:-]{16,128}", plan["idempotency_key"])):
        raise Refused("unreviewed or non-development CP fixture plan")
    prohibited = {"grant_status", "status", "approved", "approved_by",
                  "certified", "certified_by", "bearer", "client_secret",
                  "token", "secret", "password", "private_key"}
    def check(x):
        if isinstance(x, dict):
            if prohibited.intersection(x):
                raise Refused("CP fixture plan carries authority or credentials")
            for v in x.values():
                check(v)
        elif isinstance(x, list):
            for v in x:
                check(v)
    check(plan["document"])
    return plan


def execute_step(fixture, plan):
    """All mutations go through CP with separate pre-existing human operators."""
    d = plan["document"]
    step = plan["step"]
    key = plan["idempotency_key"]
    if step == "tenant":
        return fixture.register_tenant(d, key=key)
    if step == "organisation":
        if set(d) != {"tenant_id", "admission"}:
            raise Refused("reviewed CP Organisation admission bundle required")
        return fixture.admit_organisation(d["tenant_id"], d["admission"])
    if step == "market":
        return {"market_id": fixture.create_market(d, key=key), "qualified": False}
    if step == "market-activate":
        if set(d) != {"market_id", "reason"}:
            raise Refused("CP market activation only")
        m = fixture.activate_market(d["market_id"], reason=d["reason"])
        return {"market_id": m["market_id"], "market_status": m["status"], "qualified": False}
    if step == "principal-grant":
        if set(d) != {"principal_id", "permission", "scope", "grant_type", "reason"}:
            raise Refused("CP existing Principal grant only")
        gid = fixture.issue_existing_principal_grant(
            d["principal_id"], d["permission"], d["scope"],
            grant_type=d["grant_type"], reason=d["reason"], key=key)
        return {"grant_id": gid, "qualified": False}
    if step == "provisioning-create":
        if set(d) != {"tenant_id","tenant_onboarding_request_id"}:
            raise Refused("authorised CP TenantProvisioning plan input required")
        return fixture.request_provisioning(
            d["tenant_id"], d["tenant_onboarding_request_id"], key=key)
    if step == "provisioning-approve":
        if set(d) != {"tenant_id","tenant_provisioning_id",
                      "reviewed_plan_digest","reason"}:
            raise Refused("independently reviewed CP plan digest required")
        return fixture.approve_provisioning_plan(
            d["tenant_id"],d["tenant_provisioning_id"],
            reviewed_plan_digest=d["reviewed_plan_digest"],
            reason=d["reason"])
    if step == "provisioning-apply":
        if set(d) != {"tenant_id","tenant_provisioning_id","reviewed_plan_digest"}:
            raise Refused("reviewed CP apply plan required")
        return fixture.apply_approved_provisioning(
            d["tenant_id"],d["tenant_provisioning_id"],
            reviewed_plan_digest=d["reviewed_plan_digest"],idempotency_key=key)
    if step == "provisioning-verify":
        if set(d) != {"tenant_id","tenant_provisioning_id",
                      "capability_key","engine_instance_id"}:
            raise Refused("CP desired binding verification input required")
        return fixture.verify_provisioning_binding(
            d["tenant_id"],d["tenant_provisioning_id"],
            d["capability_key"],d["engine_instance_id"])
    if step == "engine-release":
        return {"release_id": fixture.record_engine_release(d), "qualified": False}
    if step == "provider-certify":
        required = {"provider_id", "capability_key", "contract_version",
                    "release_id", "qualification_profile", "evidence"}
        if set(d) != required:
            raise Refused("independent CP provider certification inputs required")
        c = fixture.certify_provider(**d)
        return {"certification_id": c["certification_id"], "qualified": False}
    raise Refused("unknown CP authority step")


def save_custody(path, document, *, exclusive):
    """Atomic, fsynced owner-private intent journal and safe observation."""
    path=Path(path)
    raw=(json.dumps(document,sort_keys=True,separators=(",",":"))+chr(10)).encode()
    if len(raw)>16384:
        raise Refused("bounded CP custody required")
    destination=path if exclusive else path.parent/("."+path.name+"."+os.urandom(8).hex())
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd=os.open(destination,flags,0o600)
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        if not exclusive:
            os.replace(destination,path)
        dfd=os.open(path.parent,os.O_DIRECTORY|os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        if not exclusive:
            destination.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n",1)[0])
    parser.add_argument("action", choices=("inspect", "apply"))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--cp-origin", default="https://cp.int03.test")
    parser.add_argument("--ca", type=Path)
    parser.add_argument("--maker-principal")
    parser.add_argument("--checker-principal")
    parser.add_argument("--maker-token-file", type=Path)
    parser.add_argument("--checker-token-file", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        plan = read_plan(args.plan)
        digest = "sha256:" + hashlib.sha256(json.dumps(
            plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if args.action == "inspect":
            print("CP_FIXTURE_REVIEW_REQUIRED: " + plan["step"] +
                  " digest=" + digest + "; qualified=false; identities_created=false")
            return 0
        if (not args.ca or not args.maker_principal or not args.checker_principal or
            not args.maker_token_file or not args.checker_token_file or not args.receipt):
            raise Refused("explicit independent operator evidence and out-of-repo receipt required")
        if args.receipt.exists() or args.receipt.is_symlink():
            raise Refused("existing CP fixture receipt requires independent reconciliation")
        # Verify durable custody is available *before* attempting a CP POST.
        # A failed/uncertain POST must be reconciled by CP idempotency/read-back,
        # never automatically retried with a different operation identity.
        target = args.receipt
        parent = target.parent
        st = parent.lstat()
        if parent.is_symlink() or not parent.is_dir() or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise Refused("private 0700 receipt directory required")
        maker=Operator(args.maker_principal, private_file(args.maker_token_file), "maker")
        checker=Operator(args.checker_principal, private_file(args.checker_token_file), "checker")
        cp=CPGateway(args.cp_origin, args.ca)
        fixture=Fixture(cp,maker,checker)
        # Require real CP to identify both independent ACTIVE administrators
        # before accepting their authorisation to write any topology record.
        fixture.verify_operator_registration()
        # Commit an unqualified intent before the first network mutation.
        # A crash leaves ATTEMPTING for a separate CP owner to reconcile.
        base={"schema":"infrastructure.int03.cp-fixture-observation.v1",
              "run_id":plan["run_id"],"step":plan["step"],
              "plan_digest":digest,"qualified":False,
              "full_int03_acceptance":False,"identity_registry_unmodified":True,
              "independent_acceptance":False}
        save_custody(target,dict(base,state="ATTEMPTING_CP_POST"),exclusive=True)
        result=execute_step(fixture, plan)
        # Record only CP-issued identifiers and bounded observations.
        save_custody(target,dict(base,state="CP_RESPONSE_OBSERVED_UNATTESTED",
                                 cp_observation=result),exclusive=False)
        print("CP_FIXTURE_OPERATION_OBSERVED; independent acceptance pending; qualified=false")
        return 0
    except (Refused, ValueError, OSError, KeyError, TypeError):
        # Do not expose token, response body, private path or internal system
        # exception in public CI logs.
        print("CP_FIXTURE_HELD_OR_UNVERIFIED; qualified=false", file=sys.stderr)
        return 2


if __name__=="__main__":
    sys.exit(main())
