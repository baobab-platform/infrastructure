"""Seven-case INT-03C original-byte custody; never an acceptance signer.

The source receipts cannot promote themselves. A separate reviewer must
download externally retained artifact bytes and repeat all checks against
issuer, CP and accepting-runtime evidence after disposal.
"""
import json
from pathlib import Path

import cms_evidence as custody
from connected_identity_evidence import CASES, EvidenceRefused, validate

PROOF_FILE = {
    "actual_issuer_token": "issuer-create.json",
    "cp_principal_readback": "cp-principal.json",
    "wrong_audience_issuer": "wrong-audience-issuer.json",
    "second_governed_tenant": "neighbour-tenant.json",
    "issuer_revocation_readback": "issuer-revocation.json",
    "cp_deactivation_readback": "principal-deactivation.json",
    "independent_teardown_readback": "independent-teardown.json",
}


def verify_candidate(directory, *, source_pins):
    """Rehash every original, bound by record and sealed manifest digests."""
    root=Path(directory)
    manifest=custody.verify(root)
    if (type(source_pins) is not dict or
        manifest.get("source_pins")!=source_pins or
        not manifest.get("run_id")):
        raise EvidenceRefused("exact immutable run and source pins required")
    inventory={item["name"]:item["sha256"] for item in manifest["files"]}
    if "int03c-receipt.json" not in inventory:
        raise EvidenceRefused("original closed seven-case receipt absent")
    record=json.loads((root/"int03c-receipt.json").read_bytes())
    expected={key:source_pins[key] for key in (
        "infrastructure","shared","baobab-iam","baobab-cp")}
    candidate=validate(record,expected_sources=expected)
    if record["independent_acceptance"] is not False or record["qualified"] is not False:
        raise EvidenceRefused("unreviewed receipt promotes its own authority")
    for case in CASES:
        name=case+".json"
        detail=record["observations"][case]
        if detail["result"]=="OBSERVED":
            if name not in inventory or detail["evidence_digest"] != "sha256:"+inventory[name]:
                raise EvidenceRefused("connected-case original evidence differs")
        elif name in inventory:
            # Retained failed-case data must not create a false success. The
            # source phase can keep a separate bounded failure journal.
            raw=json.loads((root/name).read_bytes())
            if raw.get("qualified") is True:
                raise EvidenceRefused("blocked case cannot carry acceptance")
    for proof, filename in PROOF_FILE.items():
        digest=record["proofs"][proof]
        if digest is not None:
            if inventory.get(filename) is None or digest!="sha256:"+inventory[filename]:
                raise EvidenceRefused("reviewer cannot reproduce original proof")
    if candidate and any(x not in inventory for x in PROOF_FILE.values()):
        raise EvidenceRefused("complete candidate lacks independent originals")
    if candidate:
        original=json.loads((root/PROOF_FILE["independent_teardown_readback"]).read_bytes())
        if (original.get("independent_readback") is not True or
            original.get("qualified") is not False or
            original.get("independent_acceptance") is not False or
            not isinstance(original.get("fences"),dict) or
            not original["fences"] or
            set(original["fences"].values())!={"INDEPENDENT_GET_VERIFIED"}):
            raise EvidenceRefused("independent runtime destruction not observed")
    return {
        "schema":"infrastructure.int03c.seven-case-audit.v1",
        "run_id":manifest["run_id"],"case_count":len(CASES),
        "all_originals_rehashed":True,
        "candidate_structurally_complete":candidate,
        "external_immutability":"NOT_PROVEN_BY_LOCAL_SEAL",
        "independent_acceptance":False,"qualified":False,
        "nab03_qualified":False,
    }
