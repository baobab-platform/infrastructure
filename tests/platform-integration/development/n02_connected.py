"""Development-only N02 browser/DEV-04 same-run checkpoint.

This does not launch a browser, register a BFF, certify IAM providers or make
an N02 acceptance decision. The real Playwright producer must finish against
the *currently live* owner-provisioned estate/CP/IAM run before destructive
INT-03C Principal deactivation. A private SHA-256 original and seven observed
cases are necessary, not sufficient, evidence.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

import dev

EXPECTED = frozenset({
    "N02_BROWSER_ORIGIN_CSRF_DENIAL",
    "N02_REAL_KRATOS_HYDRA_LOGIN",
    "N02_PKCE_STATE_CALLBACK_REPLAY_DENIAL",
    "N02_CP_ACTIVE_PRINCIPAL_SESSION",
    "N02_REAL_AAL2_STEP_UP",
    "N02_REAL_RECOVERY_NO_AUTO_GRANT",
    "N02_ALL_NATIVE_SESSIONS_LOGOUT",
})
SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def read_original(path):
    """Read one original inode exactly once; hash the same verified bytes."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        dev.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                    and info.st_nlink == 1 and not info.st_mode & 0o077
                    and 1 <= info.st_size <= 1_048_576,
                    "N02_PRIVATE_ORIGINAL_REQUIRED")
        raw = stream.read(1_048_577)
    dev.require(len(raw) <= 1_048_576, "N02_ORIGINAL_TOO_LARGE")
    try:
        data = json.loads(raw, object_pairs_hook=dev.unique)
    except (ValueError, TypeError, UnicodeDecodeError):
        raise dev.Refused("N02_ORIGINAL_MALFORMED") from None
    dev.require(isinstance(data, dict), "N02_ORIGINAL_NOT_OBJECT")
    return data, raw


def read_digest(path):
    """Read owner-private SHA sidecar without symlinks or debug leakage."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        meta = os.fstat(stream.fileno())
        dev.require(stat.S_ISREG(meta.st_mode) and meta.st_uid == os.getuid()
                    and meta.st_nlink == 1 and not meta.st_mode & 0o077
                    and 64 <= meta.st_size <= 65, "N02_PRIVATE_DIGEST_REQUIRED")
        text = stream.read(66).decode("ascii").strip()
    dev.require(DIGEST.fullmatch(text) is not None, "N02_DIGEST_INVALID")
    return text


def inspect_original(directory, state, root):
    """Check source/run provenance, never infer identity authorization."""
    dev.require(isinstance(root, Path) and root.is_absolute(),
                "N02_PRIVATE_ORIGINAL_DIRECTORY_REQUIRED")
    info = root.lstat()
    dev.require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                and not info.st_mode & 0o077, "N02_PRIVATE_ORIGINAL_DIRECTORY_REQUIRED")
    path = root / "browser-observation.json"
    sidecar = root / "browser-observation.sha256"
    observed, raw = read_original(path)
    digest = hashlib.sha256(raw).hexdigest()
    dev.require(read_digest(sidecar) == digest, "N02_ORIGINAL_DIGEST_MISMATCH")
    dev.require(set(observed) == {
        "schema", "classification", "source_sha", "shared_source_sha",
        "cp_source_sha", "infrastructure_harness_sha", "run_id",
        "cases", "provider_and_cp_independently_attested",
        "protected_accepted"}, "N02_ORIGINAL_SCHEMA_INVALID")
    dev.require(observed["schema"] == "baobab.iam.n02.browser-observation.v1"
                and observed["classification"] == "REAL_BROWSER_SYNTHETIC_DATA"
                and observed["run_id"] == state["run_id"]
                and observed["source_sha"] == state["sources"]["baobab-iam"]
                and observed["shared_source_sha"] == state["sources"]["shared"]
                and observed["cp_source_sha"] == state["sources"]["baobab-cp"]
                and observed["infrastructure_harness_sha"] == state["harness_sha"]
                and observed["provider_and_cp_independently_attested"] is False
                and observed["protected_accepted"] is False,
                "N02_SOURCE_OR_DEVELOPMENT_SCOPE_MISMATCH")
    cases = observed["cases"]
    dev.require(isinstance(cases, dict) and set(cases) == EXPECTED
                and all(value == "OBSERVED" for value in cases.values()),
                "N02_SEVEN_REAL_BROWSER_CASES_REQUIRED")
    return {
        "schema": "infrastructure.dev04.n02-browser-checkpoint.v1",
        "run_id": state["run_id"],
        "browser_sha256": digest,
        "source_sha": state["sources"]["baobab-iam"],
        "shared_source_sha": state["sources"]["shared"],
        "cp_source_sha": state["sources"]["baobab-cp"],
        "harness_sha": state["harness_sha"],
        "phase": "BEFORE_INT03C_DEACTIVATION",
        "classification": "ORIGINAL_BROWSER_RECONCILED_UNATTESTED",
        "provider_independently_attested": False,
        "protected_accepted": False,
    }


def checkpoint(run_id, root, max_wait_seconds=300):
    """Wait for live owner's original browser file while CP remains running.

    A missing or malformed original raises Refused; no PASS can be cached.
    No operator command, credential, URL or browser response is logged.
    """
    directory, state = dev.current(run_id)
    dev.verify_sources(directory, state)
    dev.require(state["phase"] == "TESTED" and state["tests"] is True
                and not state.get("int03c") and not state.get("n02_browser_checkpoint"),
                "N02_PRE_DEACTIVATION_CHECKPOINT_REQUIRED")
    dev.require(type(max_wait_seconds) is int and 0 <= max_wait_seconds <= 300,
                "N02_WAIT_BOUND_INVALID")
    end = min(time.monotonic() + max_wait_seconds,
              time.monotonic() + max(0, state["deadline"] - time.time() - 15))
    while True:
        directory, state = dev.current(run_id)
        try:
            receipt = inspect_original(directory, state, root)
            # Observe current CP/IAM runtime *after* real browser evidence,
            # before irreversible DEV-04 resource mutations.
            dev.compose(directory, state, "exec", "-T", "probe",
                        "python", "/native_probe.py", "health", timeout=20)
            state["n02_browser_checkpoint"] = receipt
            dev.persist(directory, state, "TESTED")
            return receipt
        except (FileNotFoundError, dev.Refused) as error:
            # Only absent original files can legitimately arrive later; a
            # malformed existing original is a real failure, not a retry.
            if not isinstance(error, FileNotFoundError):
                raise
            if time.monotonic() >= end:
                raise dev.Refused("N02_BROWSER_ORIGINAL_NOT_OBSERVED") from None
            time.sleep(2)
