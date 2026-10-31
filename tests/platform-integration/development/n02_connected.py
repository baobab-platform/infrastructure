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
        "cp_source_sha", "zuribeans_source_sha", "infrastructure_harness_sha", "run_id",
        "cases", "provider_and_cp_independently_attested",
        "protected_accepted"}, "N02_ORIGINAL_SCHEMA_INVALID")
    dev.require(observed["schema"] == "baobab.iam.n02.browser-observation.v1"
                and observed["classification"] == "REAL_BROWSER_SYNTHETIC_DATA"
                and observed["run_id"] == state["run_id"]
                and observed["source_sha"] == state["sources"]["baobab-iam"]
                and observed["shared_source_sha"] == state["sources"]["shared"]
                and observed["cp_source_sha"] == state["sources"]["baobab-cp"]
                and observed["zuribeans_source_sha"] == state["sources"]["zuribeans"]
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
        "zuribeans_source_sha": state["sources"]["zuribeans"],
        "harness_sha": state["harness_sha"],
        "phase": "BEFORE_INT03C_DEACTIVATION",
        "classification": "ORIGINAL_BROWSER_RECONCILED_UNATTESTED",
        "provider_independently_attested": False,
        "protected_accepted": False,
    }


def seal_first_party_origin(run_id, profile_path):
    """Bind Kratos's public base/browser UI to reviewed estate origin BEFORE up.

    Never let runtime deploy a Kratos cookie for an unrelated host or use
    old DEV-04 RP UI routes as a misleading N02 interactive success.
    """
    import n02_ingress
    directory, state = dev.current(run_id)
    dev.verify_sources(directory, state)
    dev.require(state["phase"] == "PREPARED"
                and state.get("lock_file") == "n02-base-lock.json"
                and not state.get("n02_estate_origin"),
                "N02_EXACT_PREPARED_FIRST_PARTY_REQUIRED")
    dev.require(isinstance(profile_path, Path)
                and profile_path.is_absolute() and not profile_path.is_symlink()
                and profile_path.is_relative_to(directory),
                "N02_PRIVATE_FIRST_PARTY_PROFILE_REQUIRED")
    data = dev.read(profile_path)
    fqdn = n02_ingress.reviewed_name(data)
    dev.require(data.get("run_id") == run_id
                and data.get("iam_source_sha") == state["sources"]["baobab-iam"]
                and data.get("cp_source_sha") == state["sources"]["baobab-cp"]
                and data.get("shared_source_sha") == state["sources"]["shared"]
                and data.get("zuribeans_source_sha") == state["sources"]["zuribeans"]
                and data.get("infrastructure_harness_sha") == state["harness_sha"],
                "N02_FIRST_PARTY_ALL_SOURCE_PINS_REQUIRED")
    state["n02_estate_origin"] = "https://" + fqdn
    state["n02_private_profile_sha256"] = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    dev.persist(directory, state, "PREPARED")


REGISTRATION = (
    "baobab-dev-zuribeans-native-browser-bff",
    "baobab-dev-zuribeans-cp-principal-validator",
)


def client_original(directory, state, root, phase):
    """Verify actual Hydra client registration/teardown original, not a fixture."""
    observed, raw = read_original(root / ("n02-clients-" + phase.lower() + ".json"))
    dev.require(read_digest(root / ("n02-clients-" + phase.lower() + ".sha256")) ==
                hashlib.sha256(raw).hexdigest(), "N02_CLIENT_ORIGINAL_DIGEST_MISMATCH")
    dev.require(set(observed) == {
        "schema", "classification", "run_id", "phase", "source", "client_ids",
        "cp_principal_resolved", "browser_cases_observed", "protected_acceptance"
    } and observed["schema"] == "baobab.iam.n02.disposable-client-observation.v1"
        and observed["classification"] == (
            "REAL_HYDRA_ADMIN_CLIENTS_ONLY_UNATTESTED"
            if phase.lower() in {"register", "verify"}
            else "HYDRA_CLIENT_CUSTODY_RECONCILED_UNATTESTED"
        )
        and observed["run_id"] == state["run_id"]
        and observed["phase"] == phase.upper()
        and observed["client_ids"] == list(REGISTRATION)
        and observed["cp_principal_resolved"] is False
        and observed["browser_cases_observed"] is False
        and observed["protected_acceptance"] is False,
        "N02_REAL_HYDRA_CLIENT_REGISTRATION_NOT_OBSERVED")
    keys = {
        "iam_source_sha": "baobab-iam", "cp_source_sha": "baobab-cp",
        "shared_source_sha": "shared", "zuribeans_source_sha": "zuribeans",
    }
    s = observed["source"]
    dev.require(isinstance(s, dict) and set(s) == set(keys) | {
        "infrastructure_harness_sha"
    } and all(s[proof] == state["sources"][repo] for proof, repo in keys.items())
        and s["infrastructure_harness_sha"] == state["harness_sha"],
        "N02_HYDRA_REGISTRATION_SOURCE_DRIFT")
    return hashlib.sha256(raw).hexdigest()


def run_client_controller(run_id, profile_path, original_dir, operation):
    """Invoke ONLY immutable pinned IAM owner client controller, never a shell."""
    dev.require(operation in {"register", "verify", "recover"}, "N02_CLIENT_OPERATION_REFUSED")
    directory, state = dev.current(run_id)
    dev.verify_sources(directory, state)
    script = directory / "sources/baobab-iam/scripts/n02_development_clients.py"
    dev.require(script.is_file() and not script.is_symlink(),
                "N02_IMMUTABLE_CLIENT_CONTROLLER_REQUIRED")
    dev.require(isinstance(profile_path, Path) and profile_path.is_absolute()
                and not profile_path.is_symlink(),
                "N02_PRIVATE_CLIENT_PROFILE_REQUIRED")
    data = dev.read(profile_path)
    dev.require(data.get("schema") == "baobab.iam.n02.disposable-clients.v1"
                and data.get("environment") == "development"
                and data.get("protected_acceptance") is False
                and data.get("run_id") == run_id
                and data.get("iam_source_sha") == state["sources"]["baobab-iam"]
                and data.get("cp_source_sha") == state["sources"]["baobab-cp"]
                and data.get("shared_source_sha") == state["sources"]["shared"]
                and data.get("zuribeans_source_sha") == state["sources"]["zuribeans"]
                and data.get("infrastructure_harness_sha") == state["harness_sha"],
                "N02_REGISTRATION_PROFILE_SOURCE_DRIFT")
    # The Hydra Admin API remains private in its run-owned network
    # namespace. No host publish/SSH tunnel or issuer Admin ingress is needed.
    # All owner-only profiles, certs and originals must reside beneath
    # the already-guarded run directory, and the immutable IAM source is
    # mounted separately read-only. Docker container:hydra shares *only*
    # that run's loopback, never another tenant or external network.
    import adapter
    private_root = profile_path.parent.resolve(strict=True)
    dev.require(private_root == profile_path.parent
                and private_root.is_relative_to(directory)
                and original_dir.is_relative_to(private_root)
                and not original_dir.is_symlink()
                and state["environment"] == "development",
                "N02_RUN_OWNED_PRIVATE_CUSTODY_REQUIRED")
    for key in ("browser_secret_file", "cp_reader_secret_file", "admin_ca_file"):
        raw = data.get(key)
        if raw is None and key == "admin_ca_file":
            continue
        dev.require(isinstance(raw, str) and Path(raw).is_absolute()
                    and Path(raw).is_relative_to(private_root)
                    and not Path(raw).is_symlink(),
                    "N02_CLIENT_SECRETS_MUST_STAY_IN_RUN")
    private_mode = private_root.lstat()
    dev.require(stat.S_ISDIR(private_mode.st_mode)
                and private_mode.st_uid == os.getuid()
                and not private_mode.st_mode & 0o077,
                "N02_PRIVATE_ROOT_REQUIRED")
    hydra_id = dev.compose(directory, state, "ps", "-q", "hydra")
    dev.require(bool(re.fullmatch(r"[a-f0-9]{12,64}", hydra_id)),
                "N02_OWNED_HYDRA_CONTAINER_REQUIRED")
    container = json.loads(dev.call(["docker", "inspect", hydra_id], state=state))[0]
    networks = container["NetworkSettings"]["Networks"]
    dev.require(container["Config"]["Labels"].get("io.baobab.dev.run") == run_id
                and not container["HostConfig"]["PortBindings"]
                and not container["HostConfig"]["Privileged"]
                and len(networks) == 1,
                "N02_HYDRA_NETWORK_NAMESPACE_UNTRUSTED")
    network = json.loads(dev.call(
        ["docker", "network", "inspect", next(iter(networks))], state=state))[0]
    dev.require(network["Internal"] is True,
                "N02_HYDRA_PROVIDER_NETWORK_NOT_PRIVATE")
    image = dev.load_lock(state["lock_file"])["images"]["probe"]
    # Official immutable Python probe image: script verifies the actual IAM
    # clean detached checkout itself. Absent git/runtime dependencies => HELD.
    argv = [
        "docker", "run", "--rm", "--read-only", "--network",
        "container:" + hydra_id, "--user", f"{state['uid']}:{state['gid']}",
        "--env", "BAOBAB_ENVIRONMENT=development",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "64", "--memory", "256m",
        "--label", "io.baobab.dev.run=" + run_id,
        "--label", "io.baobab.dev.namespace=" + dev.NAMESPACE,
        "--mount", "type=bind,src=" + adapter.host(script.parents[1]) +
                   ",dst=" + str(script.parents[1]) + ",readonly",
        "--mount", "type=bind,src=" + adapter.host(private_root) +
                   ",dst=" + str(private_root),
        "--entrypoint", "python", image, "-B", str(script), operation,
        "--profile", str(profile_path), "--evidence-dir", str(original_dir),
    ]
    env = dict(os.environ, BAOBAB_ENVIRONMENT="development")
    require_no_stdout = subprocess.run(
        argv, cwd=directory, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False, timeout=min(60, max(1, int(state["deadline"] - time.time() - 10))),
    )
    dev.require(require_no_stdout.returncode == 0, "N02_REAL_HYDRA_CLIENT_LIFECYCLE_HELD")
    return client_original(directory, state, original_dir, operation)


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
                and profile.get("zuribeans_source_sha") == state["sources"]["zuribeans"]
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
    # Registration is actually performed by the *pinned IAM owner source*
    # against the runtime's private Hydra Admin API before Chromium starts.
    # An issued OAuth client ID alone never grants a CP Principal.
    client_profile = os.environ.get("BAOBAB_N02_CLIENT_REGISTRATION_PROFILE")
    dev.require(bool(client_profile), "N02_OWNER_CLIENT_REGISTRATION_PROFILE_REQUIRED")
    run_client_controller(run_id, Path(client_profile), original_dir, "register")
    run_client_controller(run_id, Path(client_profile), original_dir, "verify")
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
