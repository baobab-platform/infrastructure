"""Exact INT-03C source preparation, independent of the held CMS lock.

This checks source identity only. A clean checkout, merged dependency, or
successful check cannot supply #49's topology approval, operators or custody.
The executing Infrastructure SHA is supplied in the reviewed run plan because
a commit cannot contain its own hash. It must descend from the merged baseline.
"""
import json
from pathlib import Path
import re
import subprocess

from connected_identity_evidence import EvidenceRefused

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
LOCK = BASE / "int03c-lock.json"
DEPENDENCIES = frozenset(("shared", "baobab-iam", "baobab-cp", "baobab-cms", "nabhold"))
SHA = re.compile(r"[0-9a-f]{40}\Z")


def unique_object(pairs):
    """Ambiguous duplicate source/authority fields cannot select a later value."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceRefused("duplicate INT-03C source field")
        result[key] = value
    return result


def read_lock():
    try:
        lock = json.loads(LOCK.read_text(), object_pairs_hook=unique_object)
    except (OSError, ValueError) as error:
        raise EvidenceRefused("INT-03C source lock unavailable or ambiguous") from error
    if (type(lock) is not dict or set(lock) != {
            "schema", "profile", "decision", "infrastructure_baseline", "sources",
            "topology_approval", "cms_activation", "qualified"} or
        lock["schema"] != "infrastructure.int03c.sources.v1" or
        lock["profile"] != "governed-connected-identity" or
        lock["decision"] != "shared:docs/architecture/int03c-governed-proof-bootstrap-decision.md" or
        lock["topology_approval"] != "REQUIRED_INFRASTRUCTURE_49" or
        lock["cms_activation"] != "HELD" or lock["qualified"] is not False or
        type(lock["infrastructure_baseline"]) is not str or
        not SHA.fullmatch(lock["infrastructure_baseline"]) or
        type(lock["sources"]) is not dict or set(lock["sources"]) != DEPENDENCIES or
        any(type(value) is not str or not SHA.fullmatch(value)
            for value in lock["sources"].values())):
        raise EvidenceRefused("closed non-authorising INT-03C source lock required")
    return lock


def git(*arguments):
    try:
        result = subprocess.run(["git", "-C", str(ROOT), *arguments],
                                capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise EvidenceRefused("immutable Infrastructure source unavailable") from None
    if result.returncode:
        raise EvidenceRefused("Infrastructure revision or merged baseline unavailable")
    return result.stdout.strip()


def source_pins(plan):
    """Refuse CMS-lock substitution, floating refs, dirty source and stale pins.

    Baseline ancestry deliberately fails closed in shallow checkouts missing
    the baseline. Operators must fetch the reviewed history, never bypass it.
    These checks perform no network requests or runtime mutation.
    """
    pins = plan.get("sources") if type(plan) is dict else None
    if (type(pins) is not dict or set(pins) != DEPENDENCIES | {"infrastructure"} or
        any(type(value) is not str or not SHA.fullmatch(value) for value in pins.values())):
        raise EvidenceRefused("complete immutable INT-03C source inventory required")
    if git("rev-parse", "HEAD") != pins["infrastructure"]:
        raise EvidenceRefused("Infrastructure revision differs")
    if git("status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none"):
        raise EvidenceRefused("operator must use clean exact Infrastructure source")
    lock = read_lock()
    if any(pins[key] != value for key, value in lock["sources"].items()):
        raise EvidenceRefused("governed INT-03C dependency lock differs")
    git("merge-base", "--is-ancestor", lock["infrastructure_baseline"], pins["infrastructure"])
    return dict(pins)
