"""CMS-only separate-process witness tests; no live NAB-03 acceptance."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cms_component_custody as component
from cms_evidence import Refused
from cms_gate import CASES


class Docker:
    def __init__(self,fail=False):
        self.fail=fail
        self.projects=[]
    def verify(self,project):
        self.projects.append(project)
        if self.fail:
            raise Refused("Docker resource still present")
        return True


class ComponentCustody(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        os.chmod(self.root,0o700)
        self.parent=self.root/("cms-component-"+"a"*16)
        self.completed=self.parent/"completed"
        self.completed.mkdir(parents=True,mode=0o700)
        self.record=self.completed/"receipt.json"
        self.data={"schema":"infrastructure.int03.cms-component.v1",
                   "run_id":"a"*16, "component_outcome":"PASS",
                   "teardown":"PASS", "qualified":False,
                   "identities_created":False, "cases":dict.fromkeys(CASES,"BLOCKED")}
        self.write()

    def write(self):
        payload=(json.dumps(self.data,sort_keys=True)+"\n").encode()
        self.record.write_bytes(payload)
        os.chmod(self.record,0o600)
        (self.completed/"receipt.sha256").write_text(
            hashlib.sha256(payload).hexdigest()+"  receipt.json\n")

    def test_independent_docker_check_not_cleanup_return_value(self):
        inspector=Docker()
        result,raw=component.witness(self.record,docker=inspector)
        self.assertEqual(inspector.projects,["cms-int03-"+"a"*16])
        self.assertEqual(result["scope"],"CMS_PG17_COMPONENT_ONLY")
        self.assertEqual(result["cp_teardown"],"NOT_EXERCISED")
        self.assertEqual(result["iam_teardown"],"NOT_EXERCISED")
        self.assertFalse(result["qualified"])
        self.assertEqual(raw["cases"],dict.fromkeys(CASES,"BLOCKED"))

    def test_docker_survivors_fail_even_with_cleanup_pass_receipt(self):
        with self.assertRaises(Refused):
            component.witness(self.record,docker=Docker(fail=True))

    def test_tampered_receipt_refused(self):
        self.data["component_outcome"]="FAIL"
        self.write()
        with self.assertRaises(Refused):
            component.witness(self.record,docker=Docker())
        self.data["component_outcome"]="PASS"
        self.write()
        self.record.write_text('{"changed":true}')
        with self.assertRaises(Refused):
            component.witness(self.record,docker=Docker())

    def test_live_recovery_session_survival_blocks_witness(self):
        state=self.root/"runtime"
        state.mkdir(mode=0o700)
        session=state/"int03-cms-component-session.json"
        session.write_text("should trigger refusal")
        with patch.object(component,"STATE",state):
            with self.assertRaises(Refused):
                component.witness(self.record,docker=Docker())

    def test_unverified_private_leftover_blocks_witness(self):
        state=self.root/"runtime"
        state.mkdir(mode=0o700)
        leftover=state/("cms-int03-"+"a"*16)
        leftover.mkdir(mode=0o700)
        (leftover/"native-iam-bridge").write_text("leftover")
        with patch.object(component,"STATE",state):
            with self.assertRaises(Refused):
                component.witness(self.record,docker=Docker())


if __name__=="__main__":
    unittest.main()
