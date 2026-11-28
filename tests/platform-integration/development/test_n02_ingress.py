"""Native N02 ingress contract tests: no actual provider, TLS or deployment."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import n02_ingress as ingress

IAM = "a" * 40
SHARED = "b" * 40
CP = "c" * 40
INFRA = "d" * 40
RUN = "e" * 32
ORIGIN = "https://iam-n02.private.example.test"


def profile():
    return {
        "schema": "baobab.iam.n02.browser-qualification.v1",
        "environment": "development",
        "run_id": RUN,
        "iam_source_sha": IAM,
        "shared_source_sha": SHARED,
        "cp_source_sha": CP,
        "infrastructure_harness_sha": INFRA,
        "require_aal2": True,
        "bff_origin": ORIGIN,
        "kratos_origin": ORIGIN,
        "hydra_origin": "https://hydra.private.example.test",
    }


class NativeIngressSourceTest(unittest.TestCase):
    def render(self, doc=None):
        with patch.dict(os.environ, {"BAOBAB_ENVIRONMENT": "development"}):
            return ingress.render(doc if doc is not None else profile())

    def test_exact_first_party_origin_and_all_three_route_owners(self):
        result = self.render().decode()
        assert "server_name iam-n02.private.example.test;" in result
        self.assertIn("ssl_reject_handshake on;", result)
        self.assertIn("location ^~ /auth/", result)
        self.assertIn("location ^~ /self-service/", result)
        self.assertIn("location = /sessions/whoami", result)
        self.assertIn("proxy_pass https://127.0.0.1:9443;", result)
        self.assertIn("proxy_pass https://127.0.0.1:9444;", result)
        self.assertIn("proxy_pass http://127.0.0.1:3000;", result)
        self.assertEqual(result.count("proxy_ssl_verify on;"), 3)
        self.assertIn("proxy_ssl_trusted_certificate /run/n02-private/upstream-roots.pem;", result)
        self.assertIn("location ^~ /admin/ { return 404; }", result)
        self.assertIn("location ^~ /internal/ { return 404; }", result)
        self.assertIn("location ^~ /oauth2/ { return 404; }", result)
        self.assertNotIn(ingress.MARKER, result)
        self.assertNotIn("proxy_ssl_verify off", result)
        self.assertNotIn("proxy_pass http://127.0.0.1:9443", result)
        self.assertNotIn("proxy_set_header Host $http_host;", result)

    def test_no_unreviewed_origin_environment_source_or_assurance(self):
        cases = (
            ("different-kratos", {"kratos_origin": "https://kratos.private.example.test"}),
            ("hydra-collision", {"hydra_origin": ORIGIN}),
            ("plaintext", {"bff_origin": "http://iam-n02.private.example.test",
                           "kratos_origin": "http://iam-n02.private.example.test"}),
            ("redirect-in-host", {"bff_origin": ORIGIN + "/evil", "kratos_origin": ORIGIN + "/evil"}),
            ("userinfo", {"bff_origin": "https://attacker@iam-n02.private.example.test",
                          "kratos_origin": "https://attacker@iam-n02.private.example.test"}),
            ("unreviewed-sha", {"iam_source_sha": "main"}),
            ("unbounded-run", {"run_id": "not-a-run"}),
            ("relaxed-assurance", {"require_aal2": False}),
            ("protected", {"environment": "production"}),
            ("header-injection", {"bff_origin": "https://a.test\r\nHost:evil.test",
                                  "kratos_origin": "https://a.test\r\nHost:evil.test"}),
        )
        for label, changed in cases:
            with self.subTest(label=label):
                with self.assertRaises(ingress.Refused):
                    self.render({**profile(), **changed})

    def test_protected_runtime_cannot_render_by_flag(self):
        for env in ("staging", "production", "local", ""):
            with patch.dict(os.environ, {"BAOBAB_ENVIRONMENT": env}):
                with self.assertRaises(ingress.Refused):
                    ingress.render(profile())

    def test_owner_private_no_follow_once_and_original_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.chmod(0o700)
            content = self.render()
            digest = ingress.publish_private(temp, content)
            dest = root / "nginx.conf"
            self.assertEqual(digest, hashlib.sha256(content).hexdigest())
            self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o600)
            self.assertEqual(dest.read_bytes(), content)
            with self.assertRaises(FileExistsError):
                ingress.publish_private(temp, content)
            self.assertEqual(hashlib.sha256(dest.read_bytes()).hexdigest(), digest)

    def test_world_readable_output_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp).chmod(0o755)
            with self.assertRaises(ingress.Refused):
                ingress.publish_private(temp, self.render())


if __name__ == "__main__":
    unittest.main()
