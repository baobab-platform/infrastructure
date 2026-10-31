"""N02/DEV-04 same-run checkpoint regressions (source-only, NOT acceptance)."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import dev
import n02_connected as join

RUN = "a" * 32
IAM = "b" * 40
SHARED = "c" * 40
CP = "d" * 40
INFRA = "e" * 40
ESTATE = "f" * 40


class N02CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.state = {
            "run_id": RUN, "phase": "TESTED", "tests": True,
            "sources": {"baobab-iam": IAM, "shared": SHARED, "baobab-cp": CP, "zuribeans": ESTATE},
            "harness_sha": INFRA, "deadline": time.time() + 300,
        }
        self.browser = {
            "schema": "baobab.iam.n02.browser-observation.v1",
            "classification": "REAL_BROWSER_SYNTHETIC_DATA",
            "run_id": RUN, "source_sha": IAM,
            "shared_source_sha": SHARED, "cp_source_sha": CP,
            "zuribeans_source_sha": ESTATE,
            "infrastructure_harness_sha": INFRA,
            "cases": {name: "OBSERVED" for name in join.EXPECTED},
            "provider_and_cp_independently_attested": False,
            "protected_accepted": False,
        }

    def original(self):
        payload = self.root / "browser-observation.json"
        dev.write(payload, self.browser)
        digest = self.root / "browser-observation.sha256"
        digest.write_text(hashlib.sha256(payload.read_bytes()).hexdigest() + "\n")
        digest.chmod(0o600)

    def test_reviewed_candidate_lock_is_opt_in_and_preserves_default(self):
        accepted = dev.load_lock("lock.json")
        candidate = dev.load_lock("n02-base-lock.json")
        self.assertEqual(candidate["profile"], accepted["profile"])
        self.assertEqual(candidate["images"], accepted["images"])
        self.assertEqual(candidate["authority"], "ADR-SHARED-043")
        self.assertIs(candidate["protected_acceptance"], False)
        self.assertTrue(candidate["synthetic_only"])
        self.assertNotEqual(candidate["sources"]["baobab-iam"],
                            accepted["sources"]["baobab-iam"])
        self.assertNotEqual(candidate["sources"]["shared"],
                            accepted["sources"]["shared"])
        self.assertRegex(candidate["sources"]["zuribeans"], r"^[a-f0-9]{40}$")
        self.assertEqual(candidate["sources"]["baobab-cp"],
                         "56d5167d03c06d4a0485dae4af16079ccf02579a")
        with self.assertRaises(dev.Refused):
            dev.load_lock("../../other-unsafe-lock.json")

    def test_private_original_current_run_binding_and_pre_deactivation(self):
        self.original()
        checkpoint = join.inspect_original(self.root, self.state, self.root)
        self.assertEqual(checkpoint["phase"], "BEFORE_INT03C_DEACTIVATION")
        self.assertEqual(checkpoint["run_id"], RUN)
        self.assertEqual(checkpoint["classification"], "ORIGINAL_BROWSER_RECONCILED_UNATTESTED")
        self.assertFalse(checkpoint["provider_independently_attested"])
        self.assertFalse(checkpoint["protected_accepted"])
        with (patch.object(dev, "current", return_value=(self.root, self.state)),
              patch.object(dev, "verify_sources"),
              patch.object(dev, "compose") as actual_live_health,
              patch.object(dev, "persist") as persisted):
            self.assertEqual(join.checkpoint(RUN, self.root, max_wait_seconds=0), checkpoint)
            actual_live_health.assert_called_once()
            persisted.assert_called_once()
        self.assertEqual(self.state["n02_browser_checkpoint"], checkpoint)

    def test_negative_absent_skipped_wrong_source_and_digest(self):
        for key, mutate in (
            ("run", lambda b: b.update(run_id="f" * 32)),
            ("cp", lambda b: b.update(cp_source_sha="f" * 40)),
            ("shared", lambda b: b.update(shared_source_sha="f" * 40)),
            ("estate", lambda b: b.update(zuribeans_source_sha="0" * 40)),
            ("iam", lambda b: b.update(source_sha="f" * 40)),
            ("harness", lambda b: b.update(infrastructure_harness_sha="f" * 40)),
            ("skip", lambda b: b["cases"].update({next(iter(join.EXPECTED)): "BLOCKED"})),
            ("protected", lambda b: b.update(protected_accepted=True)),
        ):
            with self.subTest(key=key):
                self.browser = dict(self.browser, cases=dict(self.browser["cases"]))
                mutate(self.browser)
                self.original()
                with self.assertRaises(dev.Refused):
                    join.inspect_original(self.root, self.state, self.root)
                self.browser = {**self.browser, "run_id": RUN, "source_sha": IAM,
                                "shared_source_sha": SHARED, "cp_source_sha": CP,
                                "zuribeans_source_sha": ESTATE,
                                "infrastructure_harness_sha": INFRA,
                                "protected_accepted": False,
                                "cases": {name: "OBSERVED" for name in join.EXPECTED}}
        self.original()
        (self.root / "browser-observation.sha256").write_text("f" * 64 + "\n")
        (self.root / "browser-observation.sha256").chmod(0o600)
        with self.assertRaises(dev.Refused):
            join.inspect_original(self.root, self.state, self.root)

    def test_runner_uses_pinned_checkout_and_does_not_trust_exit_alone(self):
        source = self.root / "sources" / "baobab-iam"
        actual = source / "tests" / "browser" / "n02_live.py"
        actual.parent.mkdir(parents=True)
        actual.write_text("raise SystemExit(1)\\n")
        profile_path = self.root / "profile.json"
        profile = {
            "schema": "baobab.iam.n02.browser-qualification.v1",
            "environment": "development", "run_id": RUN,
            "iam_source_sha": IAM, "shared_source_sha": SHARED,
            "cp_source_sha": CP, "zuribeans_source_sha": ESTATE,
            "infrastructure_harness_sha": INFRA,
        }
        dev.write(profile_path, profile)
        import types
        with (patch.dict(os.environ, {"BAOBAB_N02_CLIENT_REGISTRATION_PROFILE": "/private/n02-register.json"}),
              patch.object(dev, "current", return_value=(self.root, self.state)),
              patch.object(dev, "verify_sources"),
              patch.object(join, "run_client_controller") as clients,
              patch.object(join.subprocess, "run",
                           return_value=types.SimpleNamespace(returncode=0)) as launched,
              patch.object(join, "checkpoint", return_value={"phase": "BEFORE_INT03C_DEACTIVATION"}) as checked):
            got = join.execute_pinned_browser(RUN, profile_path, self.root)
            self.assertEqual(got["phase"], "BEFORE_INT03C_DEACTIVATION")
            launched.assert_called_once()
            self.assertEqual(clients.call_count, 2)
            self.assertEqual([call.args[-1] for call in clients.call_args_list], ["register", "verify"])
            self.assertEqual(launched.call_args.args[0][-1], str(actual))
            self.assertEqual(launched.call_args.kwargs["stdout"], join.subprocess.DEVNULL)
            self.assertEqual(launched.call_args.kwargs["stderr"], join.subprocess.DEVNULL)
            checked.assert_called_once()
        with (patch.dict(os.environ, {"BAOBAB_N02_CLIENT_REGISTRATION_PROFILE": "/private/n02-register.json"}),
              patch.object(dev, "current", return_value=(self.root, self.state)),
              patch.object(dev, "verify_sources"),
              patch.object(join, "run_client_controller"),
              patch.object(join.subprocess, "run",
                           return_value=types.SimpleNamespace(returncode=1)),
              patch.object(join, "checkpoint") as never_credit):
            with self.assertRaises(dev.Refused):
                join.execute_pinned_browser(RUN, profile_path, self.root)
            never_credit.assert_not_called()

    def test_runner_refuses_wrong_pins_without_running_browser(self):
        source = self.root / "sources" / "baobab-iam"
        actual = source / "tests" / "browser" / "n02_live.py"
        actual.parent.mkdir(parents=True)
        actual.write_text("raise SystemExit(0)\\n")
        profile_path = self.root / "profile.json"
        dev.write(profile_path, {
            "schema": "baobab.iam.n02.browser-qualification.v1",
            "environment": "development", "run_id": "f" * 32,
            "iam_source_sha": IAM, "shared_source_sha": SHARED,
            "cp_source_sha": CP, "zuribeans_source_sha": ESTATE,
            "infrastructure_harness_sha": INFRA,
        })
        with (patch.object(dev, "current", return_value=(self.root, self.state)),
              patch.object(dev, "verify_sources"),
              patch.object(join.subprocess, "run") as launched):
            with self.assertRaises(dev.Refused):
                join.execute_pinned_browser(RUN, profile_path, self.root)
            launched.assert_not_called()

    def test_original_client_registry_is_real_run_source_bound(self):
        payload = {
            "schema": "baobab.iam.n02.disposable-client-observation.v1",
            "classification": "REAL_HYDRA_ADMIN_CLIENTS_ONLY_UNATTESTED",
            "run_id": RUN, "phase": "REGISTER",
            "source": {
                "iam_source_sha": IAM, "cp_source_sha": CP,
                "shared_source_sha": SHARED, "zuribeans_source_sha": ESTATE,
                "infrastructure_harness_sha": INFRA,
            },
            "client_ids": list(join.REGISTRATION),
            "cp_principal_resolved": False,
            "browser_cases_observed": False,
            "protected_acceptance": False,
        }
        file = self.root / "n02-clients-register.json"
        dev.write(file, payload)
        digest = self.root / "n02-clients-register.sha256"
        digest.write_text(hashlib.sha256(file.read_bytes()).hexdigest() + "\\n")
        digest.chmod(0o600)
        with self.assertRaises(FileNotFoundError):
            join.client_original(self.root, self.state, self.root, "VERIFY")
        expected = hashlib.sha256(file.read_bytes()).hexdigest()
        self.assertEqual(join.client_original(self.root, self.state, self.root, "REGISTER"), expected)
        for changed in (
            ("source", {**payload["source"], "zuribeans_source_sha": "0" * 40}),
            ("run_id", "0" * 32),
            ("client_ids", [join.REGISTRATION[0]]),
            ("cp_principal_resolved", True),
        ):
            original = payload[changed[0]]
            payload[changed[0]] = changed[1]
            try:
                dev.write(file, payload)
                digest.write_text(hashlib.sha256(file.read_bytes()).hexdigest() + "\\n")
                digest.chmod(0o600)
                with self.assertRaises(dev.Refused):
                    join.client_original(self.root, self.state, self.root, "REGISTER")
            finally:
                payload[changed[0]] = original

    def test_native_hydra_controller_never_opens_admin_host_port(self):
        private = self.root / "owner"
        private.mkdir(mode=0o700)
        evidence = private / "originals"
        evidence.mkdir(mode=0o700)
        client = private / "n02-clients.json"
        dev.write(client, {
            "schema": "baobab.iam.n02.disposable-clients.v1",
            "environment": "development", "protected_acceptance": False,
            "run_id": RUN, "iam_source_sha": IAM, "cp_source_sha": CP,
            "shared_source_sha": SHARED, "zuribeans_source_sha": ESTATE,
            "infrastructure_harness_sha": INFRA,
            "browser_secret_file": str(private / "browser.secret"),
            "cp_reader_secret_file": str(private / "reader.secret"),
        })
        script = self.root / "sources/baobab-iam/scripts/n02_development_clients.py"
        script.parent.mkdir(parents=True)
        script.write_text("print('never fixture success')\n")
        for name in ("browser.secret", "reader.secret"):
            (private / name).write_text("x" * 48)
            (private / name).chmod(0o600)
        state = dict(self.state,
            environment="development", uid=os.getuid(), gid=os.getgid(),
            lock_file="n02-base-lock.json")
        hydra = "a" * 64
        import types
        expected_container = [{
            "Config": {"Labels": {"io.baobab.dev.run": RUN}},
            "NetworkSettings": {"Networks": {"dev01_private": {}}},
            "HostConfig": {"PortBindings": None, "Privileged": False},
        }]
        def inspector(args, **kwargs):
            if args[:2] == ["docker", "inspect"]:
                return json.dumps(expected_container)
            if args[:3] == ["docker", "network", "inspect"]:
                return json.dumps([{"Internal": True}])
            self.fail("unexpected Docker source call")
        with (patch.object(dev, "current", return_value=(self.root, state)),
              patch.object(dev, "verify_sources"),
              patch.object(dev, "compose", return_value=hydra),
              patch.object(dev, "call", side_effect=inspector),
              patch.object(dev, "load_lock", return_value={
                  "images": {"probe": "python@sha256:" + "f" * 64}
              }),
              patch.object(join, "client_original", return_value="3" * 64),
              patch.object(join.subprocess, "run",
                           return_value=types.SimpleNamespace(returncode=0)) as launched):
            self.assertEqual(join.run_client_controller(
                RUN, client, evidence, "register"), "3" * 64)
            cmd = launched.call_args.args[0]
            self.assertEqual(cmd[:3], ["docker", "run", "--rm"])
            self.assertIn("container:" + hydra, cmd)
            self.assertIn("BAOBAB_ENVIRONMENT=development", cmd)
            self.assertIn("--cap-drop", cmd)
            self.assertIn("--read-only", cmd)
            self.assertNotIn("-p", cmd)
            self.assertNotIn("--publish", cmd)
            self.assertIn("n02_development_clients.py", " ".join(cmd))

    def test_native_hydra_controller_refuses_foreign_source_before_docker(self):
        private = self.root / "owner"
        private.mkdir(mode=0o700)
        doc = private / "n02-clients.json"
        dev.write(doc, {
            "schema": "baobab.iam.n02.disposable-clients.v1",
            "environment": "development", "protected_acceptance": False,
            "run_id": RUN, "iam_source_sha": "0" * 40,
        })
        script = self.root / "sources/baobab-iam/scripts/n02_development_clients.py"
        script.parent.mkdir(parents=True)
        script.write_text("print('never')\n")
        with (patch.object(dev, "current", return_value=(self.root, self.state)),
              patch.object(dev, "verify_sources"),
              patch.object(join.subprocess, "run") as launch):
            with self.assertRaises(dev.Refused):
                join.run_client_controller(RUN, doc, private, "register")
            launch.assert_not_called()

    def test_nonce_reservation_precedes_private_client_and_browser_profiles(self):
        import ci_int03c as runner
        with (patch.dict(os.environ, {
                "BAOBAB_ENVIRONMENT": "development",
                "BAOBAB_N02_JOIN": "development",
                "BAOBAB_N02_RESERVE_ONLY": "true",
            }, clear=True),
              patch.object(dev, "prepare", return_value=RUN) as prepared,
              patch.object(dev, "up") as up,
              patch.object(dev, "qualify_int03c") as qualify):
            self.assertEqual(runner.main(), 0)
            prepared.assert_called_once_with(lock_name="n02-base-lock.json")
            up.assert_not_called()
            qualify.assert_not_called()
        # The resume command must never silently prepare a DIFFERENT run
        # after the owner has sealed credentials to a reserved nonce.
        with (patch.dict(os.environ, {
                "BAOBAB_ENVIRONMENT": "development",
                "BAOBAB_N02_JOIN": "development",
            }, clear=True),
              patch.object(dev, "prepare") as prepared):
            with self.assertRaises(dev.Refused):
                runner.main()
            prepared.assert_not_called()

    def test_resume_refuses_wrong_disposable_source_without_mutation(self):
        import ci_int03c as runner
        state = dict(self.state, phase="PREPARED", lock_file="lock.json")
        with (patch.dict(os.environ, {
                "BAOBAB_ENVIRONMENT": "development",
                "BAOBAB_N02_JOIN": "development",
                "BAOBAB_N02_PREPARED_RUN_ID": RUN,
            }, clear=True),
              patch.object(dev, "current", return_value=(self.root, state)),
              patch.object(dev, "up") as up,
              patch.object(dev, "qualify_int03c") as qualify):
            with self.assertRaises(dev.Refused):
                runner.main()
            up.assert_not_called()
            qualify.assert_not_called()

    def test_absent_real_browser_fails_without_false_positive(self):
        with (patch.object(dev, "current", return_value=(self.root, self.state)),
              patch.object(dev, "verify_sources"),
              patch.object(dev, "compose") as observed,
              patch.object(dev, "persist") as persisted):
            with self.assertRaises(dev.Refused):
                join.checkpoint(RUN, self.root, max_wait_seconds=0)
            observed.assert_not_called()
            persisted.assert_not_called()


if __name__ == "__main__":
    unittest.main()
