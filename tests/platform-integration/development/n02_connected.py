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
import subprocess
import sys
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


def execute_pinned_browser(run_id, profile_path, original_dir):
    """Run the *actual* pinned IAM Playwright producer in a supervised host.

    The operator owns the private estate ingress, Kratos recovery courier and
    synthetic credentials. No unreviewed script/command and no browser logs
    are accepted. A browser exit code is not evidence: checkpoint() reads
    the original bytes and re-observes current native CP health separately.
    """
    directory, state = dev.current(run_id)
    dev.verify_sources(directory, state)
    dev.require(state["phase"] == "TESTED" and state["tests"] is True,
                "N02_TESTED_RUNTIME_REQUIRED")
    source = directory / "sources" / "baobab-iam"
    executable = source / "tests" / "browser" / "n02_live.py"
    dev.require(executable.is_file() and not executable.is_symlink(),
                "N02_PINNED_BROWSER_PRODUCER_MISSING")
    dev.require(isinstance(profile_path, Path) and profile_path.is_absolute(),
                "N02_PRIVATE_PROFILE_REQUIRED")
    profile = dev.read(profile_path)
    dev.require(profile.get("environment") == "development"
                and profile.get("schema") == "baobab.iam.n02.browser-qualification.v1"
                and profile.get("run_id") == run_id
                and profile.get("iam_source_sha") == state["sources"]["baobab-iam"]
                and profile.get("shared_source_sha") == state["sources"]["shared"]
                and profile.get("cp_source_sha") == state["sources"]["baobab-cp"]
                and profile.get("infrastructure_harness_sha") == state["harness_sha"],
                "N02_PRIVATE_PROFILE_SOURCE_DRIFT")
    dev.require(isinstance(original_dir, Path) and original_dir.is_absolute()
                and original_dir.exists() and original_dir.is_dir()
                and not original_dir.is_symlink(), "N02_PRIVATE_OUTPUT_DIRECTORY_REQUIRED")
    info = original_dir.lstat()
    dev.require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                and not info.st_mode & 0o077,
                "N02_PRIVATE_OUTPUT_DIRECTORY_REQUIRED")
    dev.require(not any((original_dir / name).exists()
                        or (original_dir / name).is_symlink()
                        for name in ("browser-observation.json", "browser-observation.sha256",
                                     ".browser-observation.tmp",
                                     ".browser-observation.sha256.tmp")),
                "N02_ORIGINAL_ALREADY_PUBLISHED")
    budget = min(300, int(state["deadline"] - time.time()) - 15)
    dev.require(budget >= 30, "N02_BROWSER_LEASE_TOO_SHORT")
    env = dict(os.environ)
    env.update({"BAOBAB_ENVIRONMENT": "development",
                "BAOBAB_N02_PRIVATE_PROFILE": str(profile_path),
                "BAOBAB_N02_EVIDENCE_DIR": str(original_dir)})
    try:
        observed = subprocess.run(
            [sys.executable, "-B", str(executable)], cwd=source,
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False, timeout=budget,
        )
    except (OSError, subprocess.SubprocessError):
        raise dev.Refused("N02_PINNED_BROWSER_EXECUTION_UNAVAILABLE") from None
    dev.require(observed.returncode == 0, "N02_REAL_BROWSER_CASES_NOT_OBSERVED")
    return checkpoint(run_id, original_dir, max_wait_seconds=0)


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
