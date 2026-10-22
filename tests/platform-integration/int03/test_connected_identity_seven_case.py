"""Independent original-byte structure checks; never accepted live proof."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

import cms_evidence as custody
import connected_identity_seven_case as seven
from connected_identity_evidence import (AUTHORITY, CASES,
                                          EvidenceRefused, blocked_receipt)

PINS=dict.fromkeys(["infrastructure","shared","baobab-iam","baobab-cp",
                    "nabhold","baobab-cms"],"a"*40)
SMALL={k:PINS[k] for k in ("infrastructure","shared","baobab-iam","baobab-cp")}


class Candidate(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        os.chmod(self.root,0o700)
        self.names=[]

    def write(self,name,value):
        payload=custody.canonical(value)
        custody.exclusive(self.root/name,payload)
        self.names.append(name)
        return "sha256:"+hashlib.sha256(payload).hexdigest()

    def seal(self):
        custody.seal(self.root,self.names,run_id="b"*32,sources=PINS)

    def test_blocked_record_not_qualified(self):
        self.write("int03c-receipt.json",blocked_receipt(SMALL))
        self.seal()
        result=seven.verify_candidate(self.root,source_pins=PINS)
        self.assertFalse(result["candidate_structurally_complete"])
        self.assertFalse(result["qualified"])
        self.assertFalse(result["independent_acceptance"])

    def fill(self):
        record=blocked_receipt(SMALL)
        denied={
            "wrong_audience_denied":(401,"AUTH_TOKEN_REQUIRED"),
            "cross_tenant_denied":(403,"TENANT_CONTEXT_MISMATCH"),
            "revoked_credential_denied":(401,"AUTH_TOKEN_REQUIRED"),
            "deactivated_principal_denied":(403,"PRINCIPAL_NOT_ACTIVE"),
        }
        for case in CASES:
            status,code=denied.get(case,(None,"") if case=="independent_teardown"
                                   else (200,""))
            evidence={"schema":"infrastructure.int03c.case-original.v1",
                      "case":case,"status":status,"code":code,"qualified":False}
            h=self.write(case+".json",evidence)
            record["observations"][case]={
                "result":"OBSERVED","http_status":status,"code":code,
                "authority":AUTHORITY[case],"evidence_digest":h,
            }
        for name,file in seven.PROOF_FILE.items():
            proof={"schema":"infrastructure.int03c.proof-original.v1",
                   "kind":name,"qualified":False}
            if name=="independent_teardown_readback":
                proof.update({"independent_readback":True,
                              "independent_acceptance":False,
                              "fences":{"issuer":"INDEPENDENT_GET_VERIFIED",
                                        "cp":"INDEPENDENT_GET_VERIFIED",
                                        "runtime":"INDEPENDENT_GET_VERIFIED"}})
            record["proofs"][name]=self.write(file,proof)
        record["teardown"]="INDEPENDENTLY_OBSERVED_UNATTESTED"
        self.write("int03c-receipt.json",record)
        self.seal()
        return record

    def test_even_seven_complete_originals_cannot_sign_themselves(self):
        self.fill()
        result=seven.verify_candidate(self.root,source_pins=PINS)
        self.assertTrue(result["candidate_structurally_complete"])
        self.assertEqual(result["case_count"],7)
        self.assertFalse(result["qualified"])
        self.assertEqual(result["external_immutability"],
                         "NOT_PROVEN_BY_LOCAL_SEAL")

    def test_missing_or_changed_original_denied(self):
        self.fill()
        (self.root/"issuer-revocation.json").write_text('{"modified":true}')
        with self.assertRaises((EvidenceRefused,custody.Refused)):
            seven.verify_candidate(self.root,source_pins=PINS)

    def test_wrong_source_pins_cannot_reuse_complete_proof(self):
        self.fill()
        bad=dict(PINS,shared="c"*40)
        with self.assertRaises(EvidenceRefused):
            seven.verify_candidate(self.root,source_pins=bad)


if __name__=="__main__":
    unittest.main()
