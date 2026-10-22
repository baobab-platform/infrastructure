"""Infrastructure-owned durable bridge to IAM's exact native Ory CMS port.

Source-only while Shared #354 registry activation is HELD. No named client
can be created by this module while HELD. A caller can attach a live executor
ONLY with independent accepting-runtime and CP cleanup callbacks. Neither a
synthetic test nor a successful provider POST is connected acceptance.

The journal precedes any provisioning attempt and allows owner-scoped issuer
revocation/deletion following Python crash or SIGKILL. Complete host recovery
still belongs to the independent Infrastructure supervisor.
"""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

import cms_gate
from cms_lifecycle import Lifecycle, Refused

BASE = Path(__file__).resolve().parent
NAMES = (cms_gate.CONSUMER, cms_gate.VALIDATOR)
RUN = re.compile(r"[0-9a-f]{32}\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")
SCHEMA = "infrastructure.int03.native-iam-owner.v1"
ACTION_MARKERS = {
    "create": "INT03_NATIVE_CREATED_READBACK_VERIFIED",
    "revoke": "INT03_NATIVE_REVOKED_READBACK_VERIFIED",
    "destroy": "INT03_NATIVE_DESTROYED_READBACK_VERIFIED",
}
MAX_JOURNAL = 8192


def current_sha(checkout):
    """Read the actual source revision, not a user-supplied claim."""
    p = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                       capture_output=True, text=True, timeout=10, check=False)
    if p.returncode or not SHA.fullmatch(p.stdout.strip()):
        raise Refused("exact source checkout missing")
    return p.stdout.strip()


def clean_source(checkout, expected):
    if current_sha(checkout) != expected:
        raise Refused("current native IAM source differs from immutable lock")
    p = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=all"],
                       capture_output=True, text=True, timeout=10, check=False)
    if p.returncode or p.stdout.strip():
        raise Refused("native IAM source checkout not clean")
    if not (Path(checkout) / "cmd/int03-cms-native/main.go").is_file():
        raise Refused("reviewed IAM native bridge not present at source pin")


def verify_gate(shared, cms_lock):
    """Use actual immutable Shared blobs and original gate, never custom JSON."""
    gate = cms_gate.evaluate(shared, cms_lock)
    if gate["gate"]["verdict"] != "OPEN":
        raise Refused("canonical Shared CMS fixture activation remains HELD or REFUSED")
    return gate


def private_dir(directory):
    d = Path(directory)
    st = d.lstat()
    if d.is_symlink() or not d.is_dir() or st.st_mode & 0o077:
        raise Refused("owner-private 0700 directory required")
    if st.st_uid != os.getuid():
        raise Refused("recovery directory owner differs")
    return d


def durable(path, document, *, exclusive=False):
    """Atomic crash-consistent JSON replacement, never credentials."""
    path = Path(path)
    private_dir(path.parent)
    raw = (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(raw) > MAX_JOURNAL:
        raise Refused("journal too large")
    temp = path.parent / ("." + path.name + "." + secrets.token_hex(8))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(temp, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if exclusive and path.exists():
            raise Refused("existing journal refused")
        os.replace(temp, path)
        fdir = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fdir)
        finally:
            os.close(fdir)
    finally:
        temp.unlink(missing_ok=True)


def load_journal(directory):
    directory = private_dir(directory)
    path = directory / "owner.json"
    if path.is_symlink() or path.stat().st_size > MAX_JOURNAL or path.stat().st_mode & 0o077:
        raise Refused("recovery journal boundary differs")
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA or
        not RUN.fullmatch(data.get("run_id", "")) or
        not SHA.fullmatch(data.get("iam_sha", "")) or
        not SHA.fullmatch(data.get("shared_sha", "")) or
        data.get("names") != list(NAMES) or data.get("state") not in
        ("ARMED", "PROVISIONING", "PROVISIONED", "REVOKING", "RECOVERY_INCOMPLETE", "CLOSED") or
        not isinstance(data.get("deadline"), str)):
        raise Refused("recovery journal invalid")
    try:
        d = datetime.fromisoformat(data["deadline"].replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError
    except ValueError:
        raise Refused("invalid immutable deadline") from None
    return data


def start_owner(directory, *, gate, iam_sha, deadline):
    """Write the journal before either POST, with no generated identity."""
    parent = private_dir(Path(directory).parent)
    target = parent / Path(directory).name
    target.mkdir(mode=0o700, exist_ok=False)
    try:
        (target / "secrets").mkdir(mode=0o700)
        data = {
            "schema": SCHEMA, "run_id": secrets.token_hex(16),
            "iam_sha": iam_sha, "shared_sha": gate["shared"]["commit"],
            "names": list(NAMES), "deadline": deadline.astimezone(timezone.utc).isoformat(),
            "state": "ARMED", "qualified": False, "identities_created": False,
        }
        durable(target / "owner.json", data, exclusive=True)
        return data
    except BaseException:
        # No issuer mutation can have taken place before journal creation.
        for entry in (target / "secrets",):
            if entry.exists():
                entry.rmdir()
        (target / "owner.json").unlink(missing_ok=True)
        target.rmdir()
        raise


class NativeClient:
    """Execute the maintained IAM Go bridge, never hand-build Hydra clients."""
    def __init__(self, iam, shared, *, hydra_admin, kratos_admin, issuer, ca, invoke=None):
        # The Go child changes cwd to IAM; resolve host paths first so the
        # immutable Shared checkout and CA cannot accidentally be reinterpreted.
        self.iam, self.shared = Path(iam).absolute(), Path(shared).absolute()
        self.hydra_admin, self.kratos_admin, self.issuer = hydra_admin, kratos_admin, issuer
        self.ca = Path(ca).absolute()
        self.invoke = invoke or self._invoke

    def _invoke(self, argv, env, timeout):
        # stderr may include provider transport secrets; never echo it.
        return subprocess.run(argv, cwd=str(self.iam), env=env,
                              text=True, capture_output=True,
                              timeout=timeout, check=False)

    def operate(self, journal, directory, action, name, *, timeout=65):
        if action not in ACTION_MARKERS or name not in NAMES:
            raise Refused("unregistered issuer operation")
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 90:
            raise Refused("bounded native operation timeout required")
        directory = private_dir(directory)
        clean_source(self.iam, journal["iam_sha"])
        if current_sha(self.shared) != journal["shared_sha"]:
            raise Refused("recovery cannot change Shared provenance")
        argv = ["go", "run", "./cmd/int03-cms-native",
                "--action", action, "--name", name,
                "--run-id", journal["run_id"], "--hydra-admin", self.hydra_admin,
                "--kratos-admin", self.kratos_admin, "--issuer", self.issuer,
                "--ca", str(self.ca), "--shared-checkout", str(self.shared),
                "--secrets-dir", str(directory / "secrets"),
                "--deadline", journal["deadline"]]
        env = os.environ.copy()
        env["BAOBAB_INT03_NATIVE_DISPOSABLE"] = "1"
        try:
            p = self.invoke(argv, env, timeout)
        except (subprocess.TimeoutExpired, OSError):
            raise Refused("native issuer operation interrupted or unavailable") from None
        if (p.returncode != 0 or p.stdout.strip() != ACTION_MARKERS[action] or
            len(p.stdout) > 128):
            raise Refused("native issuer operation/read-back refused")
        return True


def recover(directory, client):
    """Safe even when the registry was subsequently held or a POST was lost.

    Never deletes another run's client: IAM independently verifies the exact
    marker before revoke/delete. Recovery refuses a changed source or owner.
    """
    journal = load_journal(directory)
    if journal["state"] == "CLOSED":
        return True
    journal["state"] = "REVOKING"
    durable(Path(directory) / "owner.json", journal)
    failed = False
    # Reverse the creation order; attempt both, even if one fails.
    for name in reversed(NAMES):
        try:
            client.operate(journal, directory, "destroy", name, timeout=65)
        except Exception:
            failed = True
    if failed:
        journal["state"] = "RECOVERY_INCOMPLETE"
        durable(Path(directory) / "owner.json", journal)
        return False
    journal["state"] = "CLOSED"
    durable(Path(directory) / "owner.json", journal)
    # Secrets are removed *only after* issuer read-back proves deletion.
    for name in NAMES:
        secret = Path(directory) / "secrets" / (name + ".secret")
        if secret.is_symlink():
            raise Refused("secret path replaced")
        secret.unlink(missing_ok=True)
    return True


def provision_connected(directory, *, shared, iam, lock, client, acceptors_stop, cp_cleanup,
                        now=None, monotonic=None):
    """Create the IAM pair in the connected executor, fenced end-to-end.

    acceptors_stop/cp_cleanup are real, independently observing Infrastructure
    callbacks. No default/no-op implementation exists, and a failed cleanup
    cannot produce a PASS result. The issuer pair is always destroyed in finally.
    """
    gate = verify_gate(shared, lock)
    if any(not callable(callback) for callback in (acceptors_stop, cp_cleanup)):
        raise Refused("actual runtime and CP cleanup owners required")
    iam_sha = lock["sources"]["baobab-iam"]
    clean_source(iam, iam_sha)
    if current_sha(shared) != gate["shared"]["commit"]:
        raise Refused("Shared source moved after gate")
    clock = now or (lambda: datetime.now(timezone.utc))
    deadline = clock() + timedelta(minutes=80)
    lease = Lifecycle(gate, deadline, now=clock, monotonic=monotonic)
    journal = start_owner(directory, gate=gate, iam_sha=iam_sha, deadline=deadline)
    # Register before attempting the first issuer POST; the journal survives a
    # crashed process for the next executor's 'recover' command.
    lease.register_closure(
        acceptors=acceptors_stop,
        issuer=lambda: recover(directory, client),
        cp=cp_cleanup,
        private=lambda: load_journal(directory)["state"] == "CLOSED",
    )
    try:
        for name in NAMES:
            journal["state"] = "PROVISIONING"
            durable(Path(directory) / "owner.json", journal)
            lease.execute("iam-provision", lambda remaining, n=name:
                          client.operate(journal, directory, "create", n, timeout=min(remaining, 60)),
                          max_seconds=70)
        journal["state"] = "PROVISIONED"
        durable(Path(directory) / "owner.json", journal)
        # The connected owner now uses the two private credentials only inside
        # this active lease, and must establish CP/context/CMS proof separately.
        return lease, journal
    except BaseException:
        lease.close()
        raise



def revoke_connected(lease, journal, directory, client, name):
    """Deny future token issuance using IAM's native port plus issuer GET.

    A real connected negative must separately prove previously issued bearer
    tokens cannot reach accepting services; this provider-side change alone
    never claims token-revocation acceptance.
    """
    if name not in NAMES or load_journal(directory)["run_id"] != journal["run_id"]:
        raise Refused("revocation owner or identity differs")
    lease.require_active()
    return lease.execute("iam-revoke", lambda remaining:
        client.operate(journal, directory, "revoke", name, timeout=min(remaining, 60)),
        max_seconds=70)


def native_preflight(shared, iam, lock):
    """Safe integration entrypoint under the hold; no state or network writes."""
    gate = verify_gate(shared, lock)
    clean_source(iam, lock["sources"]["baobab-iam"])
    return {"gate":gate["gate"]["verdict"],"qualified":False}


def main(argv=None):
    """Private crash-recovery CLI; never an ungated independent provisioner."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split("\\n\\n", 1)[0])
    commands = parser.add_subparsers(dest="action", required=True)
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--shared", type=Path, required=True)
    preflight.add_argument("--iam", type=Path, required=True)
    rec = commands.add_parser("recover")
    rec.add_argument("--journal-dir", type=Path, required=True)
    rec.add_argument("--shared", type=Path, required=True)
    rec.add_argument("--iam", type=Path, required=True)
    rec.add_argument("--hydra-admin", required=True)
    rec.add_argument("--kratos-admin", required=True)
    rec.add_argument("--issuer", required=True)
    rec.add_argument("--ca", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "preflight":
            lock = json.loads((BASE / "cms-lock.json").read_text())
            result = cms_gate.evaluate(args.shared, lock)
            if result["gate"]["verdict"] == "HELD":
                print("INT03_NATIVE_HELD; identities_created=false; qualified=false")
                return 0
            if result["gate"]["verdict"] != "OPEN":
                raise Refused("registry refused")
            clean_source(args.iam, lock["sources"]["baobab-iam"])
            print("INT03_NATIVE_READY_UNQUALIFIED")
            return 0
        client = NativeClient(args.iam, args.shared, hydra_admin=args.hydra_admin,
                              kratos_admin=args.kratos_admin, issuer=args.issuer,
                              ca=args.ca)
        if recover(args.journal_dir, client):
            print("INT03_NATIVE_ISSUER_TEARDOWN_VERIFIED; qualified=false")
            return 0
        raise Refused("incomplete issuer recovery")
    except Exception:
        # No native provider stderr, private paths, credentials or URLs leave
        # this command. Failed cleanup retains its journal for retry.
        print("INT03_NATIVE_REFUSED_OR_RECOVERY_INCOMPLETE", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
