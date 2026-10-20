"""INT-03 handoff source/security tests. These do not assert live integration."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("int03_handoff", BASE / "handoff.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def template():
    # Explicit IAM-owned dormant shape. Fixture drift fails closed rather than
    # silently inheriting a newly added scope, mapper, role or grant type.
    return {"clientId": "nabhold-executive", "name": "Dormant", "description": "Fixture",
            "enabled": False, "publicClient": False, "bearerOnly": False,
            "serviceAccountsEnabled": False, "protocol": "openid-connect",
            "directAccessGrantsEnabled": False, "implicitFlowEnabled": False,
            "standardFlowEnabled": True, "authenticationFlowBindingOverrides": {},
            "attributes": {"pkce.code.challenge.method": "S256",
                           "oauth2.device.authorization.grant.enabled": "false",
                           "backchannel.logout.session.required": "true",
                           "backchannel.logout.revoke.offline.tokens": "false"},
            "defaultClientScopes": ["openid", "basic", "actor-type-human", "authority:self"],
            "optionalClientScopes": [], "redirectUris": [], "webOrigins": []}


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tls = tempfile.TemporaryDirectory()
        root = Path(cls.tls.name)
        # Genuine X.509 fixture so Node can independently validate it later.
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                        "-days", "1", "-subj", "/CN=Disposable INT03 test CA",
                        "-addext", "basicConstraints=critical,CA:TRUE",
                        "-keyout", str(root / "key"), "-out", str(root / "ca")],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.ca = (root / "ca").read_text()

    @classmethod
    def tearDownClass(cls):
        cls.tls.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.value = {"synthetic": True, "sources": {k: "a" * 40 for k in m.SOURCES},
                      "principal_id": "019a0915-a8c0-7000-8000-000000000001",
                      "username": m.USERNAME, "password": "disposable-$literal-password",
                      "ca_file": str(self.root / "ca")}
        self.private(self.root / "ca", self.ca)

    def private(self, path, text):
        path.write_text(text)
        path.chmod(0o600)
        return path

    def prepare(self, name="bundle"):
        return m.prepare(self.value, template(), self.ca, self.root / name)

    def test_private_complete_bundle_with_explicit_unverified_claims(self):
        bundle = self.prepare()
        self.assertEqual({p.name for p in bundle.iterdir()},
                         {"ca.pem", "integration.env", "client.json", "users.acl", "manifest.json"})
        for path in (bundle.parent, bundle):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        for path in bundle.iterdir():
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertIn("NABHOLD_OIDC_TRUST_PROXY='true'\n", (bundle / "integration.env").read_text())
        manifest = json.loads((bundle / "manifest.json").read_text())
        self.assertEqual(manifest["state"], "PREPARED_NOT_PROVISIONED")
        self.assertEqual(manifest["declared_sources"], self.value["sources"])
        for key in ("runtime_attested", "identity_verified", "acceptance_claimed",
                    "protected_staging_accepted", "production_authorized"):
            self.assertIs(manifest[key], False)
        self.assertNotIn(self.value["password"], json.dumps(manifest))
        self.assertNotIn(self.value["principal_id"], json.dumps(manifest))

    def test_new_client_does_not_mutate_or_activate_the_product_template(self):
        source = template()
        saved = copy.deepcopy(source)
        client = m.client_fixture(source, "c" * 64)
        self.assertEqual(source, saved)
        self.assertEqual(client["clientId"], "nabhold-int03")
        self.assertEqual(client["redirectUris"], ["https://nabhold.int03.test/api/auth/callback"])
        self.assertFalse(client["fullScopeAllowed"])
        self.assertEqual(client["defaultClientScopes"], m.SCOPES)
        self.assertFalse(client["serviceAccountsEnabled"])

    def test_template_drift_and_missing_subject_mapper_are_denied(self):
        for key, value in (("enabled", True), ("publicClient", True),
                           ("serviceAccountsEnabled", True), ("directAccessGrantsEnabled", True),
                           ("implicitFlowEnabled", True), ("bearerOnly", True),
                           ("standardFlowEnabled", False), ("protocol", "saml"),
                           ("redirectUris", ["https://example.test/*"]), ("webOrigins", ["*"]),
                           ("optionalClientScopes", ["context:resolve"]),
                           ("defaultClientScopes", ["openid", "actor-type-human", "authority:self"]),
                           ("protocolMappers", []), ("secret", "leaked"),
                           ("authenticationFlowBindingOverrides", {"browser": "bypass"}),
                           ("attributes", {"pkce.code.challenge.method": "plain"})):
            with self.subTest(key=key), self.assertRaises(m.Refused):
                m.client_fixture({**template(), key: value}, "c" * 64)

    def test_no_real_user_staging_or_floating_source_input(self):
        for key, value in (("synthetic", False), ("synthetic", 1), ("username", "real-director"),
                           ("principal_id", "00000000-0000-0000-0000-000000000000"),
                           ("principal_id", "unknown"), ("ca_file", "relative.pem"),
                           ("sources", {**self.value["sources"], "shared": "main"}),
                           ("sources", {**self.value["sources"], "shared": "a" * 40 + "\n"}),
                           ("sources", {**self.value["sources"], "unknown": "a" * 40}),
                           ("cp_origin", "https://protected.example.test"),
                           ("password", "short"), ("password", "secret-'injection-value"),
                           ("password", "secret-\nINJECTED=true")):
            with self.subTest(key=key), self.assertRaises((m.Refused, ValueError)):
                m.inputs({**self.value, key: value})

    def test_no_input_duplicates_unknown_keys_or_credential_echo(self):
        with self.assertRaises(m.Refused):
            m.document('{"password":"secret","password":"other"}')
        with self.assertRaises(m.Refused):
            m.document('{"sources":{"shared":"one","shared":"two"}}')
        plan = self.private(self.root / "plan", json.dumps({**self.value, "unknown": "private-secret"}))
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = m.main(["--inputs", str(plan), "--iam-template", str(self.root / "missing"),
                         "--output", str(self.root / "output")])
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "INT-03 handoff refused; no acceptance claimed\n")

    def test_private_reader_rejects_unsafe_inode_permissions_and_bounds(self):
        original = self.private(self.root / "input", "private")
        original.chmod(0o644)
        with self.assertRaises(m.Refused):
            m.read_file(original)
        original.chmod(0o600)
        os.symlink(original, self.root / "link")
        os.mkfifo(self.root / "fifo", 0o600)
        os.link(original, self.root / "hardlink")
        for path in (original, self.root / "link", self.root / "fifo", self.root):
            with self.subTest(path=path.name), self.assertRaises((m.Refused, OSError)):
                m.read_file(path)
        (self.root / "hardlink").unlink()
        original.write_text("x" * (m.LIMIT + 1))
        with self.assertRaises(m.Refused):
            m.read_file(original)
        original.write_bytes(b"\xff")
        with self.assertRaises(ValueError):
            m.read_file(original)

    def test_refuses_existing_destination_and_insecure_parent(self):
        destination = self.root / "bundle"
        destination.mkdir(mode=0o700)
        with self.assertRaises(m.Refused):
            self.prepare()
        destination.rmdir()
        destination.symlink_to(self.root / "absent")
        with self.assertRaises(m.Refused):
            self.prepare()
        destination.unlink()
        self.root.chmod(0o755)
        with self.assertRaises(m.Refused):
            self.prepare()
        self.root.chmod(0o700)

    def test_failed_write_or_sync_never_publishes_partial_secrets(self):
        for function in ("write_private", "sync_directory"):
            with self.subTest(function=function), patch.object(m, function, side_effect=OSError("failure")):
                with self.assertRaises(OSError):
                    self.prepare()
                self.assertFalse((self.root / "bundle").exists())

    def test_exhausted_staging_creation_removes_the_reserved_destination(self):
        # The destination has already been reserved when mkdtemp can fail.
        # ENOSPC/inode exhaustion must still leave the same path retryable.
        with patch.object(m.tempfile, "mkdtemp", side_effect=OSError("no inodes")):
            with self.assertRaises(OSError):
                self.prepare()
        self.assertFalse((self.root / "bundle").exists())
        self.assertTrue(self.prepare().is_dir())

    def test_public_trust_bundle_never_contains_a_private_key(self):
        for ca in ("not a PEM", self.ca + "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----",
                   self.ca + "\n'INJECTED=true"):
            with self.subTest(ca=ca[:12]), self.assertRaises(m.Refused):
                m.prepare(self.value, template(), ca, self.root / "bundle")

    def test_independent_runs_have_distinct_secrets_and_acl_prefixes(self):
        first, second = self.prepare("first"), self.prepare("second")
        one, two = [json.loads((b / "client.json").read_text())["secret"] for b in (first, second)]
        self.assertNotEqual(one, two)
        for b in (first, second):
            acl = (b / "users.acl").read_text()
            self.assertRegex(acl, r"~nabhold:bff:v1:int03-[0-9a-f]{16}:\*")
            self.assertIn("user default off\n", acl)
            self.assertNotIn("+@", acl)
            self.assertNotIn("+eval", acl)
            self.assertNotIn("+config", acl)
            self.assertNotIn(one, acl)
            self.assertNotIn(two, acl)
        self.assertNotEqual((first / "users.acl").read_text(), (second / "users.acl").read_text())

    def test_node_literal_dotenv_matches_consumer_paths_keys_and_tls_material(self):
        # Exercise the actual independent Node parser used by Nabhold; no
        # shell evaluation of dollars/backticks and no fake JSON/PEM escaping.
        self.assertIsNotNone(shutil.which("node"), "Node 24 is required for this interoperability test")
        bundle = self.prepare()
        script = """
const fs = require('node:fs'), {parseEnv} = require('node:util'), {X509Certificate} = require('node:crypto');
const e = parseEnv(fs.readFileSync(process.argv[1], 'utf8'));
const c = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const ok = e.NABHOLD_OIDC_CLIENT_SECRET === c.secret &&
  e.NABHOLD_INTEGRATION_PASSWORD === 'disposable-$literal-password' &&
  e.NODE_EXTRA_CA_CERTS === process.argv[3] && fs.existsSync(e.NODE_EXTRA_CA_CERTS) &&
  new X509Certificate(e.NABHOLD_BFF_REDIS_CA_PEM).ca &&
  Buffer.from(JSON.parse(e.NABHOLD_BFF_STORE_KEYS_JSON).run, 'base64').length === 32 &&
  ['R1','R2','R3'].every(k => e['NABHOLD_RELEASE_'+k] === 'false') &&
  e.NABHOLD_CONTENT_DEV_FALLBACK === 'false' && e.NABHOLD_DASHBOARD_PREVIEW === 'false';
process.exit(ok ? 0 : 1);
"""
        result = subprocess.run(["node", "-e", script, str(bundle / "integration.env"),
                                 str(bundle / "client.json"), str(bundle / "ca.pem")], capture_output=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))


if __name__ == "__main__":
    unittest.main()
