"""Durable native fixture orchestration tests; no live issuance is simulated as acceptance."""
from datetime import datetime, timezone, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cms_gate
import cms_iam_native as m
from cms_lifecycle import Refused

NOW = datetime(2026, 10, 22, 7, 0, tzinfo=timezone.utc)
IAM = "a"*40
SHARED = "b"*40

def gate(state="OPEN"):
    return cms_gate.receipt(state, ["CONNECTED_LANE_REQUIRED"], SHARED, "c"*64, "d"*64)

class FakeClient:
    def __init__(self, fail=None):
        self.calls=[]
        self.fail=fail
    def _binary(self, directory):
        path=Path(directory)/"native-iam-bridge"
        path.write_bytes(b"unit-test-binary")
        os.chmod(path,0o700)
        return str(path)

    def operate(self, journal, directory, action, name, *, timeout=65):
        self.calls.append((action,name))
        # An ambiguous POST is always recoverable by a second process.
        if (action,name)==self.fail:
            raise Refused("private native operation failed")
        if action=="create":
            private=Path(directory)/"secrets"/(name+".secret")
            private.write_text(("a" if name==m.NAMES[0] else "b")*40)
            os.chmod(private,0o600)
        return True

class Durable(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent=Path(self.tmp.name)
        os.chmod(self.parent,0o700)
        self.owner=self.parent/"cms-issuer"

    def new(self):
        m.start_owner(self.owner,gate=gate(),iam_sha=IAM,
                      deadline=NOW+timedelta(minutes=80))
        return m.load_journal(self.owner)

    def test_journal_precedes_any_creation(self):
        doc=self.new()
        self.assertEqual(doc["state"],"ARMED")
        self.assertEqual(doc["names"],list(m.NAMES))
        self.assertEqual(doc["iam_sha"],IAM)
        self.assertEqual((self.owner/"owner.json").stat().st_mode & 0o777,0o600)
        self.assertEqual((self.owner/"secrets").stat().st_mode & 0o777,0o700)
        with self.assertRaises(FileExistsError):
            self.new()

    def test_secret_pair_must_be_independent_and_private(self):
        self.new()
        first=self.owner/"secrets"/(m.NAMES[0]+".secret")
        second=self.owner/"secrets"/(m.NAMES[1]+".secret")
        first.write_text("a"*40)
        second.write_text("b"*40)
        os.chmod(first,0o600)
        os.chmod(second,0o600)
        self.assertTrue(m.verify_pair_secret_isolation(self.owner))
        second.write_text("a"*40)
        with self.assertRaises(Refused):
            m.verify_pair_secret_isolation(self.owner)
        second.write_text("b"*40)
        os.chmod(second,0o644)
        with self.assertRaises(Refused):
            m.verify_pair_secret_isolation(self.owner)

    def test_recovery_attempts_both_even_when_second_fails(self):
        self.new()
        f=FakeClient(fail=("destroy",m.NAMES[1]))
        self.assertFalse(m.recover(self.owner,f))
        self.assertEqual(f.calls,[("destroy",m.NAMES[1]),("destroy",m.NAMES[0])])
        self.assertEqual(m.load_journal(self.owner)["state"],"RECOVERY_INCOMPLETE")
        good=FakeClient()
        self.assertTrue(m.recover(self.owner,good))
        self.assertEqual(m.load_journal(self.owner)["state"],"CLOSED")
        self.assertTrue(m.recover(self.owner,good))
        self.assertEqual(len(good.calls),2)

    def test_invalid_journal_private_mode_denied(self):
        self.new()
        os.chmod(self.owner/"owner.json",0o644)
        with self.assertRaises(Refused):
            m.load_journal(self.owner)

    def test_non_private_parent_fails_before_write(self):
        os.chmod(self.parent,0o755)
        with self.assertRaises(Refused):
            self.new()
        self.assertFalse(self.owner.exists())

    def test_hold_aborts_before_journal_or_issuer_io(self):
        fake=FakeClient()
        with patch.object(m,"verify_gate",side_effect=Refused("HELD")):
            with self.assertRaises(Refused):
                m.provision_connected(self.owner,shared="ignored",iam="ignored",
                    lock={"sources":{"baobab-iam":IAM}},client=fake,
                    acceptors_stop=lambda:True,cp_cleanup=lambda:True,
                    now=lambda:NOW,monotonic=lambda:1.0)
        self.assertFalse(self.owner.exists())
        self.assertEqual(fake.calls,[])

    def test_revocation_cannot_target_foreign_identity_or_owner(self):
        self.new()
        f=FakeClient()
        with self.assertRaises(Refused):
            m.revoke_connected(None,m.load_journal(self.owner),self.owner,f,"product-client")
        bad=dict(m.load_journal(self.owner))
        bad["run_id"]="0"*32
        with self.assertRaises(Refused):
            m.revoke_connected(None,bad,self.owner,f,m.NAMES[0])
        self.assertEqual(f.calls,[])

    def test_issuer_client_receives_only_fixed_native_commands(self):
        self.new()
        client=m.NativeClient("/iam","/shared",hydra_admin="https://hydra.int03.test",
                              kratos_admin="http://kratos:4434",issuer="https://hydra.int03.test",
                              ca="/private/ca.pem")
        calls=[]
        def capture(argv,env,timeout):
            calls.append((argv,env,timeout))
            class Result:
                returncode=0
                stdout="INT03_NATIVE_DESTROYED_READBACK_VERIFIED\n"
            return Result()
        client.invoke=capture
        with patch.object(m,"clean_source"),patch.object(m,"current_sha",return_value=SHARED), \
             patch.object(client,"_binary",return_value="/private/native-iam-bridge"):
            self.assertTrue(client.operate(m.load_journal(self.owner),self.owner,
                                           "destroy",m.NAMES[0]))
        self.assertEqual(calls[0][0][0],"/private/native-iam-bridge")
        self.assertIn("--run-id",calls[0][0])
        self.assertEqual(calls[0][2],65)
        self.assertEqual(calls[0][1]["BAOBAB_INT03_NATIVE_DISPOSABLE"],"1")
        self.assertNotIn("secret",str(calls[0][1]))
        with self.assertRaises(Refused):
            client.operate(m.load_journal(self.owner),self.owner,"rotate",m.NAMES[0])

    def test_live_guard_registers_cleanup_before_first_post(self):
        f=FakeClient()
        closures=[]
        with patch.object(m,"verify_gate",return_value=gate()), \
             patch.object(m,"clean_source"), \
             patch.object(m,"current_sha",return_value=SHARED):
            lease,journal=m.provision_connected(self.owner,shared="/shared",
                  iam="/iam",lock={"sources":{"baobab-iam":IAM}},client=f,
                  acceptors_stop=lambda:closures.append("acceptors") or True,
                  cp_cleanup=lambda:closures.append("cp") or True,
                  now=lambda:NOW,monotonic=lambda:1.0)
            self.assertEqual([x[0] for x in f.calls],["create","create"])
            self.assertEqual(journal["state"],"PROVISIONED")
            self.assertEqual(lease.receipt()["qualified"],False)
            m.revoke_connected(lease,journal,self.owner,f,m.NAMES[0])
            self.assertEqual(f.calls[2],("revoke",m.NAMES[0]))
            self.assertEqual(lease.close(),{"acceptors":"VERIFIED","issuer":"VERIFIED",
                                            "cp":"VERIFIED","private":"VERIFIED"})
            self.assertEqual(closures,["acceptors","cp"])
            self.assertEqual(f.calls[-2:],[("destroy",m.NAMES[1]),("destroy",m.NAMES[0])])
            self.assertEqual(m.load_journal(self.owner)["state"],"CLOSED")
            self.assertFalse((self.owner/"native-iam-bridge").exists())

if __name__=="__main__":
    unittest.main()
