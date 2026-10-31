"""N02 real Kratos browser-origin/UI config overlay; development-only.

The accepted DEV-04 Kratos config stays untouched. A single first-party
Secure host-only cookie is required: Kratos public and native Go BFF must
both be reached at the exact ZuriBeans HTTPS origin. A protected service,
unreviewed return URL, mock login, or default RP UI is never permitted.
"""
from __future__ import annotations

import re
import urllib.parse

FIRST_PARTY = re.compile(
    r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\Z"
)


class Refused(ValueError):
    pass


def overlay(source: str, first_party: str) -> str:
    if (not isinstance(source, str) or not isinstance(first_party, str)
            or FIRST_PARTY.fullmatch(first_party) is None):
        raise Refused("N02_KRATOS_REVIEWED_HTTPS_ORIGIN_REQUIRED")
    base = "https://rp.baobab-dev.test"
    public = "https://kratos.baobab-dev.test/"
    required = {
        "    base_url: " + public: 1,
        "  default_browser_return_url: " + base + "/": 1,
        "      ui_url: " + base + "/login": 1,
        "      ui_url: " + base + "/recovery": 1,
        "    - " + base: 1,
    }
    if any(source.count(fragment) < count for fragment, count in required.items()):
        raise Refused("N02_KRATOS_BASELINE_PROFILE_DRIFT")
    result = source.replace(public, first_party + "/")
    result = result.replace(base, first_party)
    result = result.replace(
        "ui_url: " + first_party + "/login",
        "ui_url: " + first_party + "/identity/kratos/login",
    )
    result = result.replace(
        "ui_url: " + first_party + "/recovery",
        "ui_url: " + first_party + "/identity/kratos/recovery",
    )
    result = result.replace(
        "default_browser_return_url: " + first_party + "/",
        "default_browser_return_url: " + first_party + "/identity/native-qualification",
    )
    # Only the exact current first-party host may be used for browser flows.
    # Enrollment, other methods and verifier flows not implemented on this
    # owner estate remain unavailable rather than being secretly mapped to RP.
    if (base in result or public in result
            or "    base_url: " + first_party + "/" not in result
            or "ui_url: " + first_party + "/identity/kratos/login" not in result
            or "ui_url: " + first_party + "/identity/kratos/recovery" not in result
            or "    - " + first_party not in result):
        raise Refused("N02_KRATOS_ORIGIN_OR_UI_DRIFT")
    return result


__all__ = ["overlay", "Refused"]
