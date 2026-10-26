"""DEV-14/15 native-only Compose overlay on the existing DEV-01 IAM/CP stack.

This is deliberately pure, with no Docker side effects. DEV-01 owns runtime
leases, immutable source/image receipts, actual token issuance, real CP
bootstrap, independent teardown and custody. Do not promote a Compose plan
or HTTP 200 health into an ENG-ONB acceptance case.
"""
from __future__ import annotations

import copy
import re

import engine_onboarding as onboard

IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
OWNERS = {
    "pulse-intelligence": "baobab-pulse",
    "payments-sandbox": "baobab-payments",
}
ALLOWED_KINDS = {
    "iam": ("iam", "baobab-iam"),
    "control-plane": ("control-plane", "baobab-cp"),
    "subject": ("engine", None),
}


def apply(profile: dict, base: dict, *, subject_image: str,
          images: dict, secrets: dict, labels: dict) -> dict:
    """Return an isolated native overlay, never mutate the caller's baseline."""
    key = profile.get("profile_key")
    onboard.require(key in OWNERS and profile.get("subject_engine") == OWNERS.get(key),
                    "DEV15_PROFILE_REFUSED")
    onboard.require(profile.get("mode") == "l4"
                    and profile.get("run_policy", {}).get("environment") == "development"
                    and profile.get("run_policy", {}).get("network") == "private"
                    and profile.get("run_policy", {}).get("synthetic_only") is True,
                    "DEV15_ENVIRONMENT_REFUSED")
    onboard.require(profile.get("run_policy", {}).get("expose_admin_ports") is False
                    and profile.get("run_policy", {}).get("cleanup") == "required",
                    "DEV15_NETWORK_POLICY_REFUSED")
    onboard.require(isinstance(subject_image, str) and IMAGE_ID.fullmatch(subject_image),
                    "DEV15_ACTUAL_IMAGE_ID_REQUIRED")
    onboard.require(isinstance(labels, dict)
                    and {"io.baobab.dev.namespace", "io.baobab.dev.run",
                         "io.baobab.dev.deadline"} <= set(labels),
                    "DEV15_RUNTIME_LEASE_LABELS_REQUIRED")
    onboard.require(isinstance(base, dict) and set(base.get("networks", {})) == {"lab"}
                    and base["networks"]["lab"].get("internal") is True
                    and "cp" in base.get("services", {})
                    and "hydra" in base["services"]
                    and "kratos" in base["services"],
                    "DEV15_DEV01_PRIVATE_STACK_REQUIRED")

    nodes = profile["services"]["required"]
    keys = {node["key"]: node for node in nodes}
    onboard.require({"iam", "control-plane", "subject"} <= set(keys)
                    and not (set(keys) - {"iam", "control-plane", "subject",
                                         "canonical-store", "semantic-projection"}),
                    "DEV15_SERVICE_SELECTION_REFUSED")
    for name, (kind, owner) in ALLOWED_KINDS.items():
        onboard.require(keys[name]["kind"] == kind
                        and (owner is None or keys[name]["owner"] == owner),
                        "DEV15_OWNERSHIP_REFUSED")
    onboard.require(keys["subject"]["owner"] == OWNERS[key], "DEV15_SUBJECT_OWNER_REFUSED")
    onboard.require(len({node["key"] for node in nodes}) == len(nodes),
                    "DEV15_DUPLICATE_SERVICE")
    onboard.require(not profile["services"]["optional"], "DEV15_OPTIONAL_SERVICES_NOT_QUALIFIED")

    subject_env: dict[str, str]
    services: dict = {}
    volumes: dict = {}
    depends = {"cp": {"condition": "service_started"}}

    if key == "pulse-intelligence":
        onboard.require(set(keys) == {"iam", "control-plane", "subject", "canonical-store",
                                      "semantic-projection"}
                        and keys["canonical-store"]["kind"] == "postgresql"
                        and keys["semantic-projection"]["kind"] == "qdrant"
                        and keys["canonical-store"]["owner"] == "baobab-pulse"
                        and keys["semantic-projection"]["owner"] == "baobab-pulse",
                        "DEV15_PULSE_NATIVE_GRAPH_REFUSED")
        postgres = images.get("postgres")
        qdrant = images.get("qdrant")
        passwd = secrets.get("pulse_db")
        onboard.require(
            isinstance(postgres, str) and onboard.IMAGE.fullmatch(postgres)
            and isinstance(qdrant, str) and onboard.IMAGE.fullmatch(qdrant)
            and isinstance(passwd, str) and re.fullmatch(r"[0-9a-f]{64}", passwd),
            "DEV15_NATIVE_STORE_IMAGE_OR_SECRET_REQUIRED",
        )
        services["pulse-db"] = {
            "image": postgres,
            "environment": {
                "POSTGRES_DB": "pulse", "POSTGRES_USER": "pulse",
                "POSTGRES_PASSWORD": passwd,
            },
            "volumes": ["dev15-pulse-data:/var/lib/postgresql/data"],
            "healthcheck": {
                "test": ["CMD", "pg_isready", "-U", "pulse", "-d", "pulse"],
                "interval": "3s", "timeout": "3s", "retries": 40,
            },
        }
        services["pulse-qdrant"] = {
            "image": qdrant,
            "volumes": ["dev15-pulse-qdrant:/qdrant/storage"],
        }
        volumes["dev15-pulse-data"] = {"labels": labels}
        volumes["dev15-pulse-qdrant"] = {"labels": labels}
        depends.update({
            "pulse-db": {"condition": "service_healthy"},
            "pulse-qdrant": {"condition": "service_started"},
        })
        subject_env = {
            "PULSE_ENVIRONMENT": "development",
            "BAOBAB_ENVIRONMENT": "development",
            "PULSE_DATABASE_URL": f"postgresql://pulse:{passwd}@pulse-db:5432/pulse",
            "PULSE_QDRANT_URL": "http://pulse-qdrant:6333",
            "PULSE_EMBEDDING_PROVIDER": "mock",
            "PULSE_EMBEDDING_DIMENSION": "16",
            "PULSE_QDRANT_COLLECTION_PREFIX": "dev15",
            "HAYSTACK_TELEMETRY_ENABLED": "false",
        }
    else:
        onboard.require(set(keys) == {"iam", "control-plane", "subject"},
                        "DEV15_PAYMENTS_NO_NATIVE_GRAPH_REFUSED")
        # Sandbox is process-local, moves no real money, and has no PSP key.
        # This is not a financial integration environment.
        subject_env = {
            "BAOBAB_ENVIRONMENT": "development",
            "PAYMENT_PROVIDER": "sandbox",
            "WORKLOAD_AUDIENCE": "baobab-payments",
            "WORKLOAD_ISSUER": "https://hydra.int03.test",
            "WORKLOAD_JWKS_URI": "https://hydra.int03.test/.well-known/jwks.json",
        }

    services["dev15-subject"] = {
        "image": subject_image,
        "environment": subject_env,
        "depends_on": depends,
    }
    result = copy.deepcopy(base)
    onboard.require(not set(result["services"]).intersection(services)
                    and not set(result.get("volumes", {})).intersection(volumes),
                    "DEV15_SERVICE_NAME_COLLISION")
    for service in services.values():
        service.update({
            "labels": labels, "restart": "no", "networks": ["lab"],
            "security_opt": ["no-new-privileges:true"],
        })
    result["services"].update(services)
    result.setdefault("volumes", {}).update(volumes)

    for service in services.values():
        onboard.require("ports" not in service and "privileged" not in service
                        and "network_mode" not in service and "build" not in service,
                        "DEV15_UNSAFE_NATIVE_COMPOSITION")
    return result
