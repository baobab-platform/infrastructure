#!/usr/bin/env python3
"""DEV-15 private native-engine health witness, not an authority qualifier.

Runs INSIDE the disposable DEV-01 probe namespace, never from public host
ports. The HTTP response must match the native owner's declared development
mode, not simply return 200. Any malformed or wrong-mode response blocks.
"""
import json
import sys
import urllib.error
import urllib.request

PROFILES = {
    "pulse-intelligence": ("http://dev15-subject:8000/readyz", 4096),
    "payments-sandbox": ("http://dev15-subject:8080/health/ready", 4096),
}


def observed(profile: str) -> bool:
    if profile not in PROFILES:
        return False
    url, limit = PROFILES[profile]
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status != 200:
                return False
            payload = response.read(limit + 1)
            if len(payload) > limit:
                return False
            doc = json.loads(payload)
    except (OSError, ValueError, urllib.error.URLError):
        return False
    if not isinstance(doc, dict):
        return False
    if profile == "pulse-intelligence":
        checks = doc.get("dependencies")
        return (doc.get("status") == "ready" and isinstance(checks, dict)
                and checks.get("database") is True
                and checks.get("semantic_retrieval") is True)
    return (doc.get("status") == "READY"
            and doc.get("environment") == "development"
            and doc.get("payment_provider") == {"kind": "SANDBOX", "simulated": True}
            and doc.get("real_payments") == "NOT_CONFIGURED"
            and doc.get("store") == "in-memory"
            and isinstance(doc.get("checks"), dict)
            and doc["checks"].get("payment_provider") == "UP"
            and doc["checks"].get("store") == "UP")


def main() -> int:
    profile = sys.argv[1] if len(sys.argv) == 2 else ""
    passed = observed(profile)
    print(json.dumps({
        "schema": "infrastructure.dev15.native-component-health.v1",
        "profile_key": profile if profile in PROFILES else "UNKNOWN",
        "result": "PASS" if passed else "BLOCKED",
        "observed": passed,
        "eng_onb_runtime_qualified": False,
        "iam_cp_operation_executed": False,
        "protected_acceptance": False,
        "production_authorized": False,
    }, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
