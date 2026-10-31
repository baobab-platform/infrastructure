"""N02 first-party Kratos overlay source assertions; never live login."""
import unittest

import n02_kratos

OLD = """serve:
  public:
    base_url: https://kratos.baobab-dev.test/
selfservice:
  default_browser_return_url: https://rp.baobab-dev.test/
  allowed_return_urls:
    - https://rp.baobab-dev.test
  flows:
    login:
      ui_url: https://rp.baobab-dev.test/login
    recovery:
      ui_url: https://rp.baobab-dev.test/recovery
    error:
      ui_url: https://rp.baobab-dev.test/error
"""

ORIGIN = "https://n02.zuribeans.private.example.test"


class KratosNativeFirstPartyTests(unittest.TestCase):
    def test_exact_login_recovery_and_cookie_origin(self):
        result = n02_kratos.overlay(OLD, ORIGIN)
        self.assertIn("base_url: " + ORIGIN + "/", result)
        self.assertIn("ui_url: " + ORIGIN + "/identity/kratos/login", result)
        self.assertIn("ui_url: " + ORIGIN + "/identity/kratos/recovery", result)
        self.assertIn("default_browser_return_url: " +
                      ORIGIN + "/identity/native-qualification", result)
        self.assertNotIn("rp.baobab-dev.test", result)
        self.assertNotIn("kratos.baobab-dev.test", result)

    def test_unsafe_fqdn_and_stale_kratos_baseline_refuse(self):
        for origin in ("http://n02.zuribeans.private.example.test",
                       "https://evil@private.example.test",
                       "https://private.example.test:443",
                       "https://private.example.test/path",
                       "https://private.example.test\nX-Forwarded-Host:evil",
                       "https://127.0.0.1"):
            with self.subTest(origin=origin):
                with self.assertRaises(n02_kratos.Refused):
                    n02_kratos.overlay(OLD, origin)
        with self.assertRaises(n02_kratos.Refused):
            n02_kratos.overlay("selfservice: {}", ORIGIN)


if __name__ == "__main__":
    unittest.main()
