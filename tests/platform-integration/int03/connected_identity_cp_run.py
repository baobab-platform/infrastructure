#!/usr/bin/env python3
"""INT-03C read-only governed CP observation lane (never an acceptance lane).

Use only development-only IAM tokens and CP-owned synthetic topology already
approved by distinct authorised administrators. It makes real private TLS
requests. It does not provision/revoke any identity, and leaves issuer
issuance, revocation readback, CP deactivation and teardown independently
BLOCKED until their separate evidence is retained and attested.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from cms_evidence import canonical, exclusive, root_dir, seal, verify
from connected_identity_cp import CPTransport, assert_current_human, assert_negative, read_private_token
from connected_identity_evidence import (
    AUTHORITY, EvidenceRefused, blocked_receipt, validate,
)

BASE=Path(__file__).resolve().parent
INPUT_SCHEMA="infrastructure.int03c.cp-observer-input.v1"
CASES=("cp_current_principal","wrong_audience_denied","cross_tenant_denied",
       "revoked_credential_denied","deactivated_principal_denied")
ROUTES={
    "cp_current_principal":"GET /v1/admin/effective-authority",
    "wrong_audience_denied":"POST /v1/platform-context/resolve",
    "cross_tenant_denied":"POST /v1/platform-context/resolve",
    "revoked_credential_denied":"GET /v1/admin/effective-authority",
    "deactivated_principal_denied":"GET /v1/admin/effective-authority",
}


def canonical_uuid(value):
    try:
        parsed=uuid.UUID(value)
    except (ValueError,TypeError,AttributeError):
        raise EvidenceRefused("canonical CP topology UUID required") from None
    if parsed.version not in (4,7) or str(parsed)!=value:
        raise EvidenceRefused("CP UUID must be canonical v4/v7")
    return value


def read_reviewed(path):
    """Refuse untrusted fixture plans: not a substitute for maker/checker."""
    from cms_evidence import safe_file
    p=Path(path)
    root_dir(p.parent)
    safe_file(p.parent,p.name)
    plan=json.loads(p.read_bytes())
    fields={"schema","run_id","environment","sources","cp_origin","ca_file",
            "tenant_id","neighbour_tenant_id","organisation_id","country_code",
            "organisation_kind","human_principal_id","tokens"}
    token_names={"human","workload","wrong_audience","revoked","deactivated"}
    if (type(plan) is not dict or set(plan)!=fields or
        plan["schema"]!=INPUT_SCHEMA or plan["environment"]!="development" or
        not re.fullmatch(r"[0-9a-f]{32}",plan["run_id"]) or
        type(plan["tokens"]) is not dict or set(plan["tokens"])!=token_names or
        any(type(value) is not str for value in plan["tokens"].values())):
        raise EvidenceRefused("operator must supply exact reviewed nonproduction plan")
    ids=[canonical_uuid(plan[key]) for key in (
        "tenant_id","neighbour_tenant_id","organisation_id","human_principal_id")]
    if ids[0]==ids[1] or plan["country_code"] not in ("ZA","UG") or plan["organisation_kind"] not in (
            "ORGANISATION","BUYER_ORGANISATION","SUPPLIER_ORGANISATION"):
        raise EvidenceRefused("distinct governed Tenant/market topology required")
    return plan


def source_pins(plan):
    """Require real immutable checked-out revision for Infrastructure plus lock."""
    p=plan.get("sources")
    if type(p) is not dict or set(p)!={"infrastructure","shared","baobab-cms",
        "baobab-iam","baobab-cp","nabhold"}:
        raise EvidenceRefused("source pin inventory incomplete")
    lock=json.loads((BASE/"cms-lock.json").read_text())
    if any(p.get(k)!=lock["sources"][k] for k in lock["sources"]):
        raise EvidenceRefused("native IAM/CP/Shared source lock differs")
    root=BASE.parents[2]
    for cmd in (
        ["git","-C",str(root),"rev-parse","HEAD"],
        ["git","-C",str(root),"status","--porcelain","--untracked-files=all"],
    ):
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=10,check=False)
        if result.returncode:
            raise EvidenceRefused("clean Infrastructure checkout unavailable")
        if cmd[-1]=="HEAD" and result.stdout.strip()!=p["infrastructure"]:
            raise EvidenceRefused("Infrastructure revision differs")
        if cmd[-1]=="--untracked-files=all" and result.stdout.strip():
            raise EvidenceRefused("operator must use clean exact source pin")
    return p


def execute(port, plan, tokens):
    """Gather bounded CP-only facts, fail closed on unrelated denied actions.

    No HTTP response body/credential is stored. Observations cannot say PASS
    or independently confirm issuer revocation/teardown.
    """
    intended={"tenant_id":plan["tenant_id"],
              "organisation_id":plan["organisation_id"],
              "country_code":plan["country_code"],
              "expected_organisation_type":plan["organisation_kind"]}
    checks={}
    cp_self=port.request("GET","/v1/admin/effective-authority",tokens["human"])
    assert_current_human(cp_self,plan["human_principal_id"])
    checks["cp_current_principal"]=(200,"")

    # This CP context resolution creates only a short-lived Context using
    # an already registered workload; never creates canonical topology.
    good=port.request("POST","/v1/platform-context/resolve",tokens["workload"],intended)
    if (good["status"]!=200 or
        good["document"].get("tenant_id")!=plan["tenant_id"] or
        good["document"].get("organisation_id")!=plan["organisation_id"] or
        not isinstance(good["document"].get("context_id"),str) or
        not good["document"].get("expires_at")):
        raise EvidenceRefused("actual CP own-tenant current Context unavailable")
    bad=port.request("POST","/v1/platform-context/resolve",
                     tokens["wrong_audience"],intended)
    assert_negative(bad,"wrong_audience_denied")
    checks["wrong_audience_denied"]=(bad["status"],bad["code"])
    neighbour=dict(intended,tenant_id=plan["neighbour_tenant_id"])
    bad=port.request("POST","/v1/platform-context/resolve",tokens["workload"],neighbour)
    assert_negative(bad,"cross_tenant_denied")
    checks["cross_tenant_denied"]=(bad["status"],bad["code"])
    for case, token_key in (("revoked_credential_denied","revoked"),
                            ("deactivated_principal_denied","deactivated")):
        read=port.request("GET","/v1/admin/effective-authority",tokens[token_key])
        assert_negative(read,case)
        checks[case]=(read["status"],read["code"])
    return checks


def capture(plan, checks, output):
    """Seal sanitized CP source facts; no issuer proof, no PASS or acceptance."""
    root=Path(output)
    root.mkdir(mode=0o700,exist_ok=False)
    root_dir(root)
    record=blocked_receipt({k:plan["sources"][k] for k in (
        "infrastructure","baobab-iam","baobab-cp","shared")})
    names=[]
    for case in CASES:
        status,code=checks[case]
        fact={"schema":"infrastructure.int03c.cp-observation.v1",
              "case":case,"authority":"cp","method_route":ROUTES[case],
              "http_status":status,"code":code,
              "observed_at":datetime.now(timezone.utc).isoformat(),
              "qualified":False,"independent_acceptance":False}
        name=case+".json"
        raw=canonical(fact)
        exclusive(root/name,raw)
        names.append(name)
        record["observations"][case]={
            "result":"OBSERVED","http_status":status,"code":code,
            "authority":AUTHORITY[case],
            "evidence_digest":"sha256:"+hashlib.sha256(raw).hexdigest(),
        }
    # IAM token creation proof and teardown are intentionally BLOCKED; the
    # reviewer must separately provide an immutable original issuer record.
    if validate(record,expected_sources=record["sources"]):
        raise EvidenceRefused("unattested CP probe must never complete qualification")
    exclusive(root/"int03c-receipt.json",canonical(record))
    names.append("int03c-receipt.json")
    seal(root,names,run_id=plan["run_id"],sources=plan["sources"])
    verify(root)
    return record


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("inspect","probe"))
    parser.add_argument("--plan",type=Path,required=True)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args(argv)
    try:
        p=read_reviewed(args.plan)
        if args.action=="inspect":
            print("INT03C_CP_PROBE_REQUIRES_GOVERNED_RUNTIME; qualified=false")
            return 0
        if args.out is None or args.out.exists() or args.out.is_symlink():
            raise EvidenceRefused("new private evidence directory required")
        source_pins(p)
        tokens={name:read_private_token(value) for name,value in p["tokens"].items()}
        actual=CPTransport(p["cp_origin"],p["ca_file"])
        checks=execute(actual,p,tokens)
        capture(p,checks,args.out)
        print("INT03C_CP_NEGATIVES_OBSERVED_UNATTESTED; qualified=false")
        return 0
    except (EvidenceRefused,OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired):
        print("INT03C_CP_PROBE_BLOCKED_OR_REFUSED; qualified=false",file=sys.stderr)
        return 2


if __name__=="__main__":
    sys.exit(main())
