"""Closed, run-private credentials for an externally approved DEV-07 issuer.

Never creates a CP approval, IAM Principal, budget or price. These settings only
allow the actual current-authority sources to be contacted, and Trade refuses
to commit if any of them deny the purchase.
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

SCHEMA = "infrastructure.dev07.checkout-private-configuration.v1"
CREDENTIALS = (
    "trade_workload_client_id", "trade_workload_client_secret",
    "market_workload_client_id", "market_workload_client_secret",
    "tenant_workload_client_id", "tenant_workload_client_secret",
    "price_provider_client_id", "price_provider_client_secret",
)
FIELDS = frozenset((*CREDENTIALS, "schema", "run_id", "issuer_endpoint",
                    "issuer_public_key_pem", "price_provider_audience"))


class PrivateCheckoutConfigurationDenied(ValueError):
    pass


def require(ok, name):
    if not ok:
        raise PrivateCheckoutConfigurationDenied(name)


def validate_private_checkout_configuration(value: object, run_id: str) -> dict[str, str]:
    require(isinstance(value, dict) and set(value) == FIELDS
            and value.get("schema") == SCHEMA and value.get("run_id") == run_id
            and isinstance(run_id, str)
            and re.fullmatch(r"[0-9a-f]{32}", run_id) is not None,
            "DEV07_CHECKOUT_PRIVATE_CONFIG_SCOPE_INVALID")
    try:
        url = urlsplit(value["issuer_endpoint"])
        host = url.hostname
        port = url.port
    except (TypeError, ValueError):
        raise PrivateCheckoutConfigurationDenied("DEV07_CHECKOUT_PRICE_ISSUER_ENDPOINT_DENIED") from None
    require(url.scheme == "https" and host is not None
            and host.endswith(".baobab-dev.test")
            and host != ".baobab-dev.test"
            and port in (None, 443)
            and url.path == "/v1/trade/cart-final-charges"
            and not url.username and not url.password and not url.fragment
            and not url.query and not url.netloc.endswith(".")
            and not url.path.endswith("/"),
            "DEV07_CHECKOUT_PRICE_ISSUER_ENDPOINT_DENIED")
    pem = value["issuer_public_key_pem"]
    require(isinstance(pem, str) and 100 <= len(pem) <= 2000
            and pem.startswith("-----BEGIN PUBLIC KEY-----\n")
            and pem.rstrip("\n").endswith("-----END PUBLIC KEY-----")
            and len(pem.split("-----END PUBLIC KEY-----")) == 2
            and re.fullmatch(r"[A-Za-z0-9+/=\r\n]+",
                    pem.split("-----BEGIN PUBLIC KEY-----\n", 1)[1].split("-----END PUBLIC KEY-----", 1)[0]) is not None,
            "DEV07_CHECKOUT_ED25519_PUBLIC_KEY_REQUIRED")
    audience = value["price_provider_audience"]
    require(isinstance(audience, str) and
            re.fullmatch(r"[A-Za-z0-9._:/-]{8,200}", audience) is not None,
            "DEV07_CHECKOUT_PROVIDER_AUDIENCE_INVALID")
    for key in CREDENTIALS:
        token = value[key]
        pattern = r"[A-Za-z0-9._:-]{8,200}" if key.endswith("_id") else r"[A-Za-z0-9._~+/=-]{24,512}"
        require(isinstance(token, str) and re.fullmatch(pattern, token) is not None,
                "DEV07_CHECKOUT_WORKLOAD_CREDENTIAL_INVALID")
    return {
        "BAOBAB_NATIVE_PRICE_ISSUER_ENDPOINT": value["issuer_endpoint"],
        "BAOBAB_NATIVE_PRICE_ISSUER_PUBLIC_KEY_PEM": pem,
        "BAOBAB_NATIVE_PRICE_PROVIDER_AUDIENCE": audience,
        "BAOBAB_IAM_WORKLOAD_CLIENT_ID": value["trade_workload_client_id"],
        "BAOBAB_IAM_WORKLOAD_CLIENT_SECRET": value["trade_workload_client_secret"],
        "BAOBAB_NATIVE_BUYER_MARKET_CLIENT_ID": value["market_workload_client_id"],
        "BAOBAB_NATIVE_BUYER_MARKET_CLIENT_SECRET": value["market_workload_client_secret"],
        "BAOBAB_NATIVE_BUYER_TENANT_CLIENT_ID": value["tenant_workload_client_id"],
        "BAOBAB_NATIVE_BUYER_TENANT_CLIENT_SECRET": value["tenant_workload_client_secret"],
        "BAOBAB_NATIVE_PRICE_PROVIDER_CLIENT_ID": value["price_provider_client_id"],
        "BAOBAB_NATIVE_PRICE_PROVIDER_CLIENT_SECRET": value["price_provider_client_secret"],
    }
