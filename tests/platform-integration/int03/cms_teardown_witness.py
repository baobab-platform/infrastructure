#!/usr/bin/env python3
"""Independent read-only INT-03 teardown witness, never its cleanup executor.

Cannot delete any resource or manufacture a pass from a cleanup return value.
Requires live Docker, Hydra and CP read-backs plus private-file inspection.
While Shared #354 is HELD this is testable source only, not a live attestation.
"""
from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path
import re
import ssl
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

import cms_evidence as custody

PROJECT = re.compile(r"(?:cms-int03-[0-9a-f]{16}|l4-[0-9a-f]{16})\Z")
RUN = re.compile(r"[0-9a-f]{16,32}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
RESOURCE = re.compile(r"/v1/(?:tenants|organisations|markets|admin/grants|provider-capability-certifications)/[a-zA-Z0-9_-]+(?:/overview)?\Z")
NAMES = ("baobab-int03-cms-consumer", "baobab-int03-cms-validator")
INACTIVE = frozenset({"REVOKED", "SUSPENDED", "DECOMMISSIONED", "DISABLED",
                      "DELETED", "INACTIVE", "WITHDRAWN", "TERMINATED"})
DOCKER_KINDS = ("container", "network", "volume")


@dataclass(frozen=True)
class Owner:
    project: str
    run_id: str
    iam_sha: str
    shared_sha: str
    cp_resources: tuple
    prior_digests: dict
    private_dir: Path

    @classmethod
    def from_record(cls, raw, *, parent):
        if not isinstance(raw, dict) or set(raw) != {
            "schema", "project", "run_id", "iam_sha", "shared_sha",
            "cp_resources", "private_leaf", "issuer_clients", "prior_digests"}:
            raise custody.Refused("teardown owner descriptor differs")
        if (raw["schema"] != "infrastructure.int03.teardown-owner.v1" or
            not PROJECT.fullmatch(raw["project"]) or not RUN.fullmatch(raw["run_id"]) or
            not SHA.fullmatch(raw["iam_sha"]) or not SHA.fullmatch(raw["shared_sha"]) or
            raw["issuer_clients"] != list(NAMES) or
            not isinstance(raw["cp_resources"], list) or
            not raw["cp_resources"] or len(raw["cp_resources"]) > 24 or
            not all(isinstance(x,str) and RESOURCE.fullmatch(x) for x in raw["cp_resources"]) or
            not isinstance(raw["prior_digests"],dict) or
            set(raw["prior_digests"]) != {"issuer_create","cp_create","runtime_start"} or
            not all(isinstance(v,str) and re.fullmatch(r"sha256:[0-9a-f]{64}",v) for v in raw["prior_digests"].values()) or
            len(set(raw["cp_resources"])) != len(raw["cp_resources"]) or
            raw["private_leaf"] != raw["project"]):
            raise custody.Refused("owned synthetic topology or provenance absent")
        directory = Path(parent) / raw["private_leaf"]
        if directory.parent != Path(parent):
            raise custody.Refused("private run path escaped")
        return cls(raw["project"], raw["run_id"], raw["iam_sha"],
                   raw["shared_sha"], tuple(raw["cp_resources"]),raw["prior_digests"], directory)


class DockerReadback:
    """Live Docker Engine query; zero exit and zero labels required."""
    def __init__(self, run_command=None):
        self.run = run_command or self._run

    @staticmethod
    def _run(argv):
        response = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, timeout=25, check=False)
        if response.returncode:
            raise custody.Refused("independent Docker read-back unavailable")
        if len(response.stdout) > 16384:
            raise custody.Refused("Docker read-back unbounded")
        return response.stdout.strip()

    def verify(self, project):
        if not PROJECT.fullmatch(project):
            raise custody.Refused("unapproved Docker project")
        for kind, args in (
            ("container", ["docker","ps","-aq"]),
            ("network",["docker","network","ls","-q"]),
            ("volume", ["docker","volume","ls","-q"])):
            cmd = args + ["--filter", "label=com.docker.compose.project=" + project]
            result = self.run(cmd)
            if result:
                raise custody.Refused("owned Docker " + kind + " survives teardown")
        # Compose ownership labels are not the whole asset set: built images
        # are normally not labelled with the Compose project.
        if project.startswith("cms-int03-"):
            tag=project.removeprefix("cms-int03-")
            references=["int03-cms-runtime:"+tag,"int03-cms-tool:"+tag]
        else:
            references=["l4-"+service+"-"+project for service in
                        ("iam","cp","human","pulse","nabhold")]
        for reference in references:
            if self.run(["docker","image","ls","-q","--filter","reference="+reference]):
                raise custody.Refused("owned run image survives teardown")
        return True


class HTTPSReadback:
    """Private TLS fixed origins, direct authenticated GET, no redirects."""
    def __init__(self, ca, *, issuer="https://hydra.int03.test", cp="https://cp.int03.test",
                 cp_token=None, request=None):
        for expected, url in (("hydra.int03.test",issuer),("cp.int03.test",cp)):
            u=urllib.parse.urlsplit(url)
            if (u.scheme!="https" or u.hostname!=expected or u.username or u.password or
                u.path not in ("","/") or u.query or u.fragment):
                raise custody.Refused("witness read-back crossed private origin")
        ca=Path(ca)
        if ca.is_symlink() or not ca.is_file():
            raise custody.Refused("private CA missing")
        try:
            context=ssl.create_default_context(cafile=str(ca))
        except (ssl.SSLError,OSError):
            raise custody.Refused("independent witness CA invalid") from None
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.open = request or urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context), NoRedirect()).open
        self.issuer=issuer.rstrip("/")
        self.cp=cp.rstrip("/")
        if (not isinstance(cp_token,str) or len(cp_token)<20 or
            len(cp_token)>8192 or any(c.isspace() for c in cp_token)):
            raise custody.Refused("independent ACTIVE CP reviewer credential required")
        self.token=cp_token

    def get(self, url, *, authenticated):
        headers={"Accept":"application/json","Cache-Control":"no-store"}
        if authenticated:
            headers["Authorization"]="Bearer "+self.token
        request=urllib.request.Request(url,headers=headers,method="GET")
        try:
            response=self.open(request,timeout=20)
        except urllib.error.HTTPError as error:
            if error.code in (404,410):
                return error.code,None
            raise custody.Refused("independent authority rejected read-back") from None
        except (urllib.error.URLError,TimeoutError,OSError,ValueError):
            raise custody.Refused("independent authority unavailable") from None
        with response:
            status=response.status
            raw=response.read(32769)
            if len(raw)>32768:
                raise custody.Refused("read-back response too large")
            if status==200:
                try:
                    return status,json.loads(raw)
                except ValueError:
                    raise custody.Refused("live CP authority returned invalid JSON") from None
        raise custody.Refused("unexpected authority response")

    def verify_issuer(self):
        for name in NAMES:
            status,_=self.get(self.issuer+"/admin/clients/"+name,authenticated=False)
            if status!=404:
                raise custody.Refused("real issuer client still active or reachable")
        return True

    def verify_cp(self, resource_paths):
        for path in resource_paths:
            if not RESOURCE.fullmatch(path):
                raise custody.Refused("unreviewed CP resource")
            status,document=self.get(self.cp+path,authenticated=True)
            if status in (404,410):
                continue
            if status!=200 or not isinstance(document,dict):
                raise custody.Refused("CP resource observation missing")
            if document.get("status") not in INACTIVE and document.get("state") not in INACTIVE:
                raise custody.Refused("CP still reports an effective governed resource")
        return True


def verify_private(directory):
    """Private owner directory may remain only as an empty recovery tombstone.

    Journal and secret data cannot be retained in the run directory; safe
    evidence lives in an independently captured, sealed external bundle.
    """
    directory=Path(directory)
    if directory.is_symlink():
        raise custody.Refused("untrusted private run path")
    if not directory.exists():
        return True
    info=directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or
        info.st_mode & 0o077):
        raise custody.Refused("private run directory ownership differs")
    if any(directory.iterdir()):
        raise custody.Refused("private run secret, state, or binary survives teardown")
    return True


def independent_inspection(owner, docker, authority):
    """All four independent fences, with no invocation of cleanup callbacks."""
    if not isinstance(owner,Owner):
        raise custody.Refused("immutable prior owner descriptor required")
    evidence={}
    # Attempt all fences even if one is defective; no result implies
    # readiness unless all independently checked sources pass.
    for name,operation in (
        ("acceptors_and_docker",lambda:docker.verify(owner.project)),
        ("issuer_clients",authority.verify_issuer),
        ("cp_governed_resources",lambda:authority.verify_cp(owner.cp_resources)),
        ("private_runtime",lambda:verify_private(owner.private_dir))):
        try:
            evidence[name]="INDEPENDENT_GET_VERIFIED" if operation() is True else "UNVERIFIED"
        except Exception:
            evidence[name]="UNVERIFIED"
    if set(evidence.values())!={"INDEPENDENT_GET_VERIFIED"}:
        raise custody.Refused("independent teardown incomplete; recovery must remain available")
    return {"schema":"infrastructure.int03.teardown-witness.v1",
            "project":owner.project,"run_id":owner.run_id,
            "source_pins":{"iam":owner.iam_sha,"shared":owner.shared_sha},
            "fences":evidence,"prior_evidence_digests":owner.prior_digests,
            "independent_readback":True,
            "evidence_class":"OBSERVED_UNATTESTED",
            "qualified":False,"full_int03_acceptance":False,
            "independent_acceptance":False}


def verify_prior_creation_custody(owner, custody_dir):
    """Prove the owner references actual prior source-pinned evidence bytes.

    An arbitrary 64-character digest alone is not evidence that issuer,
    CP and accepting runtime were ever created. Require a separately sealed
    bundle with all three original documents before checking their absence.
    """
    manifest=custody.verify(custody_dir)
    if (manifest["run_id"] != owner.run_id or
        manifest["source_pins"]["shared"] != owner.shared_sha or
        manifest["source_pins"]["baobab-iam"] != owner.iam_sha):
        raise custody.Refused("prior creation proof source/run provenance differs")
    recorded={entry["name"]:"sha256:"+entry["sha256"] for entry in manifest["files"]}
    exact={"issuer_create":"issuer-create.json",
           "cp_create":"cp-create.json",
           "runtime_start":"runtime-start.json"}
    if any(recorded.get(filename)!=owner.prior_digests[kind]
           for kind,filename in exact.items()):
        raise custody.Refused("issuer, CP or runtime creation evidence not retained")
    return True


def token_file(path):
    path=Path(path)
    s=path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(s.st_mode) or
        s.st_uid!=os.getuid() or s.st_mode & 0o077 or s.st_size>8192):
        raise custody.Refused("CP checker token is not private")
    return path.read_text().strip()


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--owner",type=Path,required=True)
    p.add_argument("--private-parent",type=Path,required=True)
    p.add_argument("--ca",type=Path,required=True)
    p.add_argument("--prior-custody",type=Path,required=True)
    p.add_argument("--cp-checker-token-file",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args(argv)
    try:
        if a.output.exists() or a.output.is_symlink():
            raise custody.Refused("cannot overwrite independent witness")
        data=json.loads(a.owner.read_text())
        owner=Owner.from_record(data,parent=a.private_parent)
        verify_prior_creation_custody(owner,a.prior_custody)
        observed=independent_inspection(owner,DockerReadback(),
                  HTTPSReadback(a.ca,cp_token=token_file(a.cp_checker_token_file)))
        # Evidence must be retained in an owner-private bundle *outside* the
        # destroyed runtime directory and then sealed by cms_evidence.py.
        custody.root_dir(a.output.parent)
        custody.exclusive(a.output,custody.canonical(observed))
        print("INT03_TEARDOWN_INDEPENDENT_READBACK_UNATTESTED; qualified=false")
        return 0
    except (custody.Refused,OSError,ValueError,TypeError,KeyError):
        print("INT03_TEARDOWN_READBACK_INCOMPLETE; qualified=false",file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
