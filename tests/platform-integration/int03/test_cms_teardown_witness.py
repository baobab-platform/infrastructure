"""Unit proofs for source-level independent teardown invariants only."""
import os
from pathlib import Path
import tempfile
import unittest

import cms_teardown_witness as witness
from cms_evidence import Refused


class Docker:
    def __init__(self, leftover=False):
        self.leftover=leftover
        self.calls=[]
    def verify(self,project):
        self.calls.append(project)
        if self.leftover:
            raise Refused("labelled network survived")
        return True


class Authorities:
    def __init__(self,issuer=True,cp=True):
        self.issuer=issuer
        self.cp=cp
        self.calls=[]
    def verify_issuer(self):
        self.calls.append("issuer")
        if not self.issuer:
            raise Refused("issuer survived")
        return True
    def verify_cp(self,paths):
        self.calls.append(("cp",paths))
        if not self.cp:
            raise Refused("active grant survived")
        return True


class Witness(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name)
        os.chmod(self.parent,0o700)
        self.project="cms-int03-"+"a"*16
        self.raw={"schema":"infrastructure.int03.teardown-owner.v1",
                  "project":self.project,"run_id":"a"*16,
                  "iam_sha":"b"*40,"shared_sha":"c"*40,
                  "cp_resources":["/v1/tenants/abc123","/v1/admin/grants/agr123"],
                  "private_leaf":self.project,
                  "prior_digests":dict.fromkeys(["issuer_create","cp_create","runtime_start"],"sha256:"+"e"*64),
                  "issuer_clients":list(witness.NAMES)}
        self.owner=witness.Owner.from_record(self.raw,parent=self.parent)

    def test_all_four_separate_observations_required(self):
        docker=Docker()
        authority=Authorities()
        result=witness.independent_inspection(self.owner,docker,authority)
        self.assertFalse(result["qualified"])
        self.assertFalse(result["independent_acceptance"])
        self.assertEqual(len(result["fences"]),4)
        self.assertEqual(docker.calls,[self.project])
        self.assertEqual(authority.calls[0],"issuer")
        self.assertEqual(authority.calls[1][0],"cp")

    def test_prior_creation_requires_real_sealed_matching_bytes(self):
        import hashlib
        import json
        import cms_evidence as custody
        bundle=self.parent/"retained"
        bundle.mkdir(mode=0o700)
        names={"issuer_create":"issuer-create.json",
               "cp_create":"cp-create.json",
               "runtime_start":"runtime-start.json"}
        for kind,name in names.items():
            payload=(json.dumps({"schema":"runtime.evidence.v1",
                                 "phase":kind,"qualified":False})+"\\n").encode()
            dest=bundle/name
            dest.write_bytes(payload)
            os.chmod(dest,0o600)
            self.raw["prior_digests"][kind]="sha256:"+hashlib.sha256(payload).hexdigest()
        self.owner=witness.Owner.from_record(self.raw,parent=self.parent)
        pins=dict.fromkeys(["shared","baobab-cms","baobab-iam","baobab-cp",
                            "nabhold","infrastructure"],"d"*40)
        pins["shared"]=self.owner.shared_sha
        pins["baobab-iam"]=self.owner.iam_sha
        custody.seal(bundle,list(names.values()),run_id=self.owner.run_id,sources=pins)
        self.assertTrue(witness.verify_prior_creation_custody(self.owner,bundle))
        (bundle/"issuer-create.json").write_text('{"qualified":false,"changed":true}')
        with self.assertRaises(Refused):
            witness.verify_prior_creation_custody(self.owner,bundle)

    def test_each_failed_fence_blocks_complete_teardown(self):
        for d,a in ((Docker(True),Authorities()),(Docker(),Authorities(False,True)),
                    (Docker(),Authorities(True,False))):
            with self.assertRaises(Refused):
                witness.independent_inspection(self.owner,d,a)
        private=self.parent/self.project
        private.mkdir(mode=0o700)
        (private/"leftover.secret").write_text("should never be retained")
        with self.assertRaises(Refused):
            witness.independent_inspection(self.owner,Docker(),Authorities())

    def test_descriptor_denies_missing_cp_authority_or_wrong_client(self):
        for edit in ({"cp_resources":[]},
                     {"prior_digests":{}},
                     {"issuer_clients":[witness.NAMES[0]]},
                     {"project":"other-workload"},
                     {"private_leaf":"../escape"},
                     {"run_id":"unbounded-run"}):
            raw=dict(self.raw,**edit)
            with self.assertRaises(Refused):
                witness.Owner.from_record(raw,parent=self.parent)

    def test_docker_label_queries_are_exact_and_zero_or_fail(self):
        observed=[]
        def run(cmd):
            observed.append(cmd)
            return ""
        self.assertTrue(witness.DockerReadback(run).verify(self.project))
        self.assertEqual(len(observed),5)
        self.assertTrue(all(
            cmd[-1]=="label=com.docker.compose.project="+self.project for cmd in observed[:3]))
        self.assertTrue(all(cmd[0:3]==["docker","image","ls"] for cmd in observed[3:]))
        def foreign(cmd):
            if "network" in cmd:
                return "network-survives"
            return ""
        with self.assertRaises(Refused):
            witness.DockerReadback(foreign).verify(self.project)

    def test_remaining_private_binary_blocks_even_without_credentials(self):
        private=self.parent/self.project
        private.mkdir(mode=0o700)
        (private/"native-iam-bridge").write_bytes(b"compiled")
        with self.assertRaises(Refused):
            witness.verify_private(private)
        (private/"native-iam-bridge").unlink()
        self.assertTrue(witness.verify_private(private))


if __name__=="__main__":
    unittest.main()
