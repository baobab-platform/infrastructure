"""Independent teardown source tests; fake transport never qualifies live."""
import os
from pathlib import Path
import tempfile
import unittest

import cms_evidence as custody
from connected_identity_teardown import Owner, witness, ORIGINALS


class Docker:
    def __init__(self, survivor=False):
        self.survivor=survivor
        self.calls=0
    def verify(self,project):
        self.calls+=1
        if self.survivor:
            raise custody.Refused("owned runtime still running")
        return True


class TeardownTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        os.chmod(self.root,0o700)
        self.run_id="a"*32
        self.sources=dict.fromkeys(["infrastructure","shared","baobab-cms",
                                    "baobab-iam","baobab-cp","nabhold"],"b"*40)
        descriptor={
            "run_id":self.run_id,
            "docker_project":"l4-"+self.run_id[:16],
            "clients":["int03c-native-owner","int03c-native-checker"],
            "cp_resources":["/v1/tenants/tn_owned","/v1/admin/grants/agr_owned"],
            "shared_sha":"b"*40,"iam_sha":"b"*40,"cp_sha":"b"*40,
            "private_leaf":self.run_id,
        }
        self.descriptor=descriptor
        self.owner=Owner.read(descriptor,parent=self.root)
        self.originals=self.root/"originals"
        self.originals.mkdir(mode=0o700)
        for name in ORIGINALS:
            custody.exclusive(self.originals/name,
                              custody.canonical({"schema":"synthetic.proof.v1",
                                                 "kind":name,"qualified":False}))
        custody.seal(self.originals,list(ORIGINALS),
                     run_id=self.run_id,sources=self.sources)

    def check(self,**replace):
        values=dict(issuer_lookup=lambda x:404,
                    cp_lookup=lambda p:(404,None),
                    principal_lookup=lambda:"INACTIVE",
                    docker=Docker(),prior_custody=self.originals)
        values.update(replace)
        return witness(self.owner,**values)

    def test_every_independent_fence_required(self):
        result=self.check()
        self.assertTrue(result["independent_readback"])
        self.assertFalse(result["qualified"])
        self.assertFalse(result["independent_acceptance"])
        self.assertEqual(len(result["fences"]),5)

    def test_active_issuer_or_cp_or_principal_denied(self):
        for kwargs in (
            {"issuer_lookup":lambda name:200},
            {"cp_lookup":lambda path:(200,{"status":"ACTIVE"})},
            {"principal_lookup":lambda:"ACTIVE"},
            {"docker":Docker(survivor=True)},
            {"principal_lookup":None},
        ):
            with self.assertRaises((custody.Refused,TypeError)):
                self.check(**kwargs)

    def test_missing_prior_create_original_denied(self):
        (self.originals/"cp-create.json").unlink()
        with self.assertRaises(custody.Refused):
            self.check()

    def test_unreviewed_clients_and_cms_identity_never_adopted(self):
        for broken in (
            dict(self.descriptor,clients=["baobab-int03-cms-consumer",
                                          "baobab-int03-cms-validator"]),
            dict(self.descriptor,run_id="invalid-run"),
            dict(self.descriptor,private_leaf="../elsewhere"),
        ):
            with self.assertRaises(custody.Refused):
                Owner.read(broken,parent=self.root)

    def test_private_runtime_secret_blocks_complete_teardown(self):
        runtime=self.root/self.run_id
        runtime.mkdir(mode=0o700)
        (runtime/"owner.token").write_text("private")
        with self.assertRaises(custody.Refused):
            self.check()


if __name__=="__main__":
    unittest.main()
