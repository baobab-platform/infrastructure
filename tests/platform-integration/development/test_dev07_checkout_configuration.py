"""Only config rejection tests; secrets and source approvals are never minted."""
import base64
import copy
import unittest
from dev07_checkout_configuration import (
    SCHEMA, PrivateCheckoutConfigurationDenied, validate_private_checkout_configuration,
)


class CheckoutPrivateConfigTests(unittest.TestCase):
    def setUp(self):
        self.run = "a" * 32
        self.value = {
            "schema": SCHEMA, "run_id": self.run,
            "issuer_endpoint": "https://price.baobab-dev.test/v1/trade/cart-final-charges",
            "issuer_public_key_pem":
                "-----BEGIN PUBLIC KEY-----\n" + "MCowBQYDK2VwAyEAGb9ECWmEzf6FQbrBZ9w7lshQhqowtrbLDFw4rXAxZuE=" + "\n-----END PUBLIC KEY-----\n",
            "price_provider_audience": "baobab-price-issuer",
        }
        for n in ("trade", "market", "tenant", "price_provider"):
            self.value[{"trade":"trade_workload_client_id","market":"market_workload_client_id","tenant":"tenant_workload_client_id","price_provider":"price_provider_client_id"}[n]] = "client." + n + ".development"
            self.value[{"trade":"trade_workload_client_secret","market":"market_workload_client_secret","tenant":"tenant_workload_client_secret","price_provider":"price_provider_client_secret"}[n]] = "X" * 32

    def test_only_allowlisted_environment_keys_derived(self):
        environment = validate_private_checkout_configuration(self.value, self.run)
        self.assertEqual(len(environment), 11)
        self.assertIn("BAOBAB_NATIVE_PRICE_ISSUER_ENDPOINT", environment)
        self.assertNotIn("BAOBAB_TRADE_A_ORDER_AUTHORITY_ENABLED", environment)
        self.assertNotIn("BAOBAB_NATIVE_BUYER_COMMIT_ENABLED", environment)

    def test_no_arbitrary_toggle_or_extra_credential(self):
        wrong = copy.deepcopy(self.value)
        wrong["skip_cp_check"] = True
        with self.assertRaises(PrivateCheckoutConfigurationDenied):
            validate_private_checkout_configuration(wrong, self.run)

    def test_wrong_run_denied(self):
        with self.assertRaises(PrivateCheckoutConfigurationDenied):
            validate_private_checkout_configuration(self.value, "b" * 32)

    def test_nonprivate_or_non_https_price_issuer_denied(self):
        for url in ("http://price.baobab-dev.test/v1/trade/cart-final-charges",
                    "https://example.com/v1/trade/cart-final-charges",
                    "https://price.baobab-dev.test/other",
                    "https://user:secret@price.baobab-dev.test/v1/trade/cart-final-charges",
                    "https://price.baobab-dev.test/v1/trade/cart-final-charges?mode=skip"):
            with self.subTest(url=url):
                wrong = copy.deepcopy(self.value); wrong["issuer_endpoint"] = url
                with self.assertRaises(PrivateCheckoutConfigurationDenied):
                    validate_private_checkout_configuration(wrong, self.run)

    def test_wrong_endpoint_types_fail_closed(self):
        for value in (None, 0, {}, [], True):
            with self.subTest(value=value):
                wrong = copy.deepcopy(self.value)
                wrong["issuer_endpoint"] = value
                with self.assertRaises(PrivateCheckoutConfigurationDenied):
                    validate_private_checkout_configuration(wrong, self.run)

    def test_only_ed25519_spki_is_accepted(self):
        valid = base64.b64decode(self.value["issuer_public_key_pem"].splitlines()[1])
        for der in (b"\0" * 135, valid[:8] + b"\x6e" + valid[9:],
                    valid[:-1], valid + b"\0"):
            with self.subTest(der_length=len(der)):
                wrong = copy.deepcopy(self.value)
                wrong["issuer_public_key_pem"] = (
                    "-----BEGIN PUBLIC KEY-----\n" + base64.b64encode(der).decode()
                    + "\n-----END PUBLIC KEY-----\n")
                with self.assertRaisesRegex(PrivateCheckoutConfigurationDenied, "ED25519"):
                    validate_private_checkout_configuration(wrong, self.run)

    def test_url_parser_cannot_strip_controls(self):
        for endpoint in (" " + self.value["issuer_endpoint"],
                         self.value["issuer_endpoint"].replace("price", "pri\nce"),
                         self.value["issuer_endpoint"] + "\t"):
            wrong = copy.deepcopy(self.value)
            wrong["issuer_endpoint"] = endpoint
            with self.assertRaisesRegex(PrivateCheckoutConfigurationDenied, "ENDPOINT"):
                validate_private_checkout_configuration(wrong, self.run)

    def test_short_secret_denied(self):
        wrong = copy.deepcopy(self.value)
        wrong["trade_workload_client_secret"] = "short"
        with self.assertRaises(PrivateCheckoutConfigurationDenied):
            validate_private_checkout_configuration(wrong, self.run)


if __name__ == "__main__":
    unittest.main()
