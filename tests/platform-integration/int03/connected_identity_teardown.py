"""INT-03C independent read-only destruction witness.

Never invoke cleanup through this module. A different operator must rerun
actual issuer, CP and Docker checks after the supervised owner stops. Source
test doubles are not runtime proof or external artifact attestation.
"""
from dataclasses import dataclass
from pathlib import Path
import re

import cms_evidence as custody
from cms_teardown_witness import DockerReadback, verify_private

SHA = re.compile(r"[0-9a-f]{40}\Z")
RUN = re.compile(r"[0-9a-f]{32}\Z")
CLIENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{3,99}\Z")
FORBIDDEN = {"baobab-int03-cms-consumer","baobab-int03-cms-validator"}
INACTIVE = frozenset({"REVOKED","DECOMMISSIONED","DISABLED","INACTIVE","DELETED"})
ORIGINALS = ("issuer-create.json","cp-create.json","runtime-start.json")


@dataclass(frozen=True)
class Owner:
    run_id: str
    docker_project: str
    clients: tuple
    cp_resources: tuple
    shared_sha: str
    iam_sha: str
    cp_sha: str
    private_root: Path

    @classmethod
    def read(cls, raw, *, parent):
        fields={"run_id","docker_project","clients","cp_resources",
                "shared_sha","iam_sha","cp_sha","private_leaf"}
        if not isinstance(raw,dict) or set(raw)!=fields:
            raise custody.Refused("exact prior INT-03C owner descriptor required")
        if (not RUN.fullmatch(raw["run_id"]) or
            raw["docker_project"]!="l4-"+raw["run_id"][:16] or
            not isinstance(raw["clients"],list) or
            len(raw["clients"])!=2 or len(set(raw["clients"]))!=2 or
            any(not isinstance(x,str) or not CLIENT.fullmatch(x) or x in FORBIDDEN
                for x in raw["clients"]) or
            not all(SHA.fullmatch(raw[k]) for k in ("shared_sha","iam_sha","cp_sha")) or
            not isinstance(raw["cp_resources"],list) or
            not raw["cp_resources"] or len(raw["cp_resources"])>24 or
            not all(isinstance(x,str) and
                    re.fullmatch(r"/v1/(tenants|markets|admin/grants)/[A-Za-z0-9_-]+",x)
                    for x in raw["cp_resources"]) or
            raw["private_leaf"]!=raw["run_id"]):
            raise custody.Refused("unreviewed owner, source or resource boundary")
        parent=custody.root_dir(parent)
        return cls(raw["run_id"],raw["docker_project"],
                   tuple(raw["clients"]),tuple(raw["cp_resources"]),
                   raw["shared_sha"],raw["iam_sha"],raw["cp_sha"],
                   parent/raw["run_id"])


def witness(owner, *, issuer_lookup, cp_lookup, principal_lookup,
            docker=None, prior_custody=None):
    """Require both real clients deleted, all CP resources terminated,
    original Principal status terminal and owned Docker/private state gone.

    issuer_lookup(client_id) must be provider-native admin readback; a token
    introspection response alone does not establish client deletion.
    principal_lookup() must be CP-owned, checker-authenticated status; this
    has no supported CP route yet, so an absent live adapter fails closed.
    """
    if not isinstance(owner,Owner) or not callable(issuer_lookup) or not callable(
            cp_lookup) or not callable(principal_lookup) or prior_custody is None:
        raise custody.Refused("independent issuer and CP checker unavailable")
    try:
        prior=custody.verify(prior_custody)
    except (OSError, ValueError, TypeError):
        # Do not expose private source paths or filesystem details.
        raise custody.Refused("independent original creation bytes unavailable") from None
    if (prior["run_id"]!=owner.run_id or
        prior["source_pins"]["shared"]!=owner.shared_sha or
        prior["source_pins"]["baobab-iam"]!=owner.iam_sha or
        prior["source_pins"]["baobab-cp"]!=owner.cp_sha or
        not set(ORIGINALS).issubset({x["name"] for x in prior["files"]})):
        raise custody.Refused("independent original creation evidence missing")
    for client in owner.clients:
        if issuer_lookup(client)!=404:
            raise custody.Refused("issuer client survives after teardown")
    for resource in owner.cp_resources:
        status,body=cp_lookup(resource)
        if status not in (404,410):
            if (status!=200 or not isinstance(body,dict) or
                body.get("status") not in INACTIVE and body.get("state") not in INACTIVE):
                raise custody.Refused("CP governed resource remains effective")
    # A claim that revoked token was denied is insufficient: a different
    # checker must directly prove the canonical Principal itself terminal.
    if principal_lookup() not in INACTIVE:
        raise custody.Refused("CP canonical Principal deactivation not verified")
    inspector=docker or DockerReadback()
    if inspector.verify(owner.docker_project) is not True:
        raise custody.Refused("owned Docker resources survive")
    verify_private(owner.private_root)
    return {"schema":"infrastructure.int03c.teardown-witness.v1",
            "run_id":owner.run_id,
            "fences":{"issuer":"INDEPENDENT_GET_VERIFIED",
                      "cp_resources":"INDEPENDENT_GET_VERIFIED",
                      "cp_principal":"INDEPENDENT_GET_VERIFIED",
                      "docker":"INDEPENDENT_GET_VERIFIED",
                      "private_runtime":"INDEPENDENT_GET_VERIFIED"},
            "independent_readback":True,
            "external_immutability":"NOT_PROVEN_BY_LOCAL_SEAL",
            "qualified":False,"independent_acceptance":False,
            "nab03_qualified":False}
