#!/usr/bin/env python3
"""Second-process CMS-only Docker/image cleanup and evidence custody.

This witnesses *component* teardown on the actual Actions Docker daemon.
It does not verify IAM or CP revocation and cannot qualify any NAB-03 case.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

import cms_evidence as custody
from cms_teardown_witness import DockerReadback, verify_private
from cms_gate import CASES

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
EVIDENCE = ROOT / "tests/platform-integration/evidence"
STATE = ROOT / "tests/platform-integration/.runtime"
RUN = re.compile(r"[0-9a-f]{16}\Z")


def receipt_file(path):
    info=path.lstat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
        raise custody.Refused("component receipt is not private")
    data=path.read_bytes()
    if len(data)>1_048_576 or not data:
        raise custody.Refused("component receipt absent/unbounded")
    reported=path.with_name("receipt.sha256")
    if reported.is_symlink() or not reported.is_file():
        raise custody.Refused("original component receipt digest missing")
    saved=reported.read_text().strip().split()
    if (len(saved)!=2 or saved[1]!="receipt.json" or
        saved[0]!=hashlib.sha256(data).hexdigest()):
        raise custody.Refused("component writer bytes not independently verified")
    receipt=json.loads(data)
    if (not isinstance(receipt,dict) or
        receipt.get("schema")!="infrastructure.int03.cms-component.v1" or
        receipt.get("component_outcome")!="PASS" or receipt.get("teardown")!="PASS" or
        receipt.get("qualified") is not False or
        receipt.get("identities_created") is not False or
        receipt.get("cases")!=dict.fromkeys(CASES,"BLOCKED") or
        not isinstance(receipt.get("run_id"),str) or not RUN.fullmatch(receipt["run_id"])):
        raise custody.Refused("CMS component produced no acceptable bounded receipt")
    return receipt


def witness(path, *, docker=None):
    """Use actual Docker, not the cleanup command result, and keep scope exact."""
    observed=receipt_file(path)
    run_id=observed["run_id"]
    project="cms-int03-"+run_id
    inspector=docker or DockerReadback()
    if inspector.verify(project) is not True:
        raise custody.Refused("Docker destruction not independently observed")
    if (STATE / "int03-cms-component-session.json").exists():
        raise custody.Refused("component recovery handle survived")
    verify_private(STATE / project)
    result={
        "schema":"infrastructure.int03.cms-component-teardown-witness.v1",
        "run_id":run_id,"project":project,
        "docker_containers_networks_volumes_and_images":"INDEPENDENTLY_ABSENT",
        "private_runtime":"INDEPENDENTLY_ABSENT",
        "source_receipt_sha256":"sha256:"+hashlib.sha256(path.read_bytes()).hexdigest(),
        "scope":"CMS_PG17_COMPONENT_ONLY",
        "iam_teardown":"NOT_EXERCISED","cp_teardown":"NOT_EXERCISED",
        "qualified":False,"full_int03_acceptance":False,
        "independent_acceptance":False,
    }
    return result,observed


def capture():
    candidates=sorted(EVIDENCE.glob("cms-component-*/completed/receipt.json"))
    if len(candidates)!=1:
        raise custody.Refused("exactly one completed disposable CMS evidence run required")
    path=candidates[0]
    observed,original=witness(path)
    target=path.parents[1]/"custody"
    target.mkdir(mode=0o700,exist_ok=False)
    custody.exclusive(target/"component.json",custody.canonical(original))
    custody.exclusive(target/"teardown.json",custody.canonical(observed))
    locks=json.loads((BASE/"cms-lock.json").read_text())
    git=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,check=False,
                       capture_output=True,text=True,timeout=10)
    if git.returncode or not re.fullmatch("[0-9a-f]{40}",git.stdout.strip()):
        raise custody.Refused("actual Infrastructure revision not available")
    pins={**locks["sources"],"infrastructure":git.stdout.strip()}
    run=os.getenv("GITHUB_RUN_ID")
    custody.seal(target,["component.json","teardown.json"],
                 run_id=observed["run_id"],sources=pins,
                 workflow_run=int(run) if run and run.isdigit() else None)
    custody.verify(target)
    return target


def verify():
    targets=sorted(EVIDENCE.glob("cms-component-*/custody/manifest.json"))
    if len(targets)!=1:
        raise custody.Refused("exactly one sealed CMS bundle required")
    return custody.verify(targets[0].parent)


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("capture","verify"))
    args=parser.parse_args(argv)
    try:
        if args.action=="capture":
            capture()
        else:
            verify()
        print("INT03_CMS_COMPONENT_EVIDENCE_HASHED_AND_CLEANED; NAB03_BLOCKED; qualified=false")
        return 0
    except (custody.Refused,OSError,ValueError,TypeError,KeyError,subprocess.TimeoutExpired):
        print("INT03_CMS_COMPONENT_CUSTODY_OR_TEARDOWN_REFUSED; qualified=false",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
