"""Fail-closed lifecycle guard for disposable, registry-authorised CMS proof runs.

This is a reusable control, NOT an issuer/CP implementation or a connected
qualification receipt. All operations must use bounded live adapters owned by
the Infrastructure runner. The registry gate must be OPEN; HELD never provisions.
A monotonic clock enforces the original absolute deadline even if wall time moves.
"""
from datetime import datetime, timezone
import math
import threading
import time

from cms_gate import CASES, CONSUMER, VALIDATOR

MAX_RUN_SECONDS = 90 * 60
MAX_TOKEN_SECONDS = 60
# Cleanup is registered *before* any possible create, including failed POSTs.
CLOSURE_ORDER = ("acceptors", "issuer", "cp", "private")


class Refused(RuntimeError):
    """A lifecycle invariant failed; no acceptance can be issued."""


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise Refused("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class Lifecycle:
    """Supervise live operations without acquiring credentials or weakening gates.

    The caller supplies time-bounded network operations and separately verified
    cleanup adapters. A callback receives its *maximum* allowed duration;
    the callback must enforce the timeout on its network connection. This owner
    checks the deadline both before and after every call and always closes.
    """

    def __init__(self, gate, deadline, *, now=None, monotonic=None):
        now = now or (lambda: datetime.now(timezone.utc))
        monotonic = monotonic or time.monotonic
        created = utc(now())
        deadline = utc(deadline)
        window = (deadline - created).total_seconds()
        if not 60 < window <= MAX_RUN_SECONDS:
            raise Refused("deadline must be immutable and within 90 minutes")
        if not isinstance(gate, dict) or gate.get("schema") != "infrastructure.int03.cms-gate.v1":
            raise Refused("verified CMS gate receipt required")
        decision = gate.get("gate")
        if not isinstance(decision, dict) or decision.get("verdict") != "OPEN":
            raise Refused("canonical CMS registry activation is not OPEN")
        if gate.get("identities_created") is not False or gate.get("qualified") is not False:
            raise Refused("gate receipt must be pre-provision, never qualification")
        if gate.get("scenario") != "NAB-03" or gate.get("cases") != dict.fromkeys(CASES, "BLOCKED"):
            raise Refused("incomplete or privileged gate receipt")
        shared = gate.get("shared")
        if not isinstance(shared, dict) or not isinstance(shared.get("commit"), str) or len(shared["commit"]) != 40:
            raise Refused("pinned Shared provenance required")
        self.created = created
        self.deadline = deadline
        self._window = window
        self._clock = now
        self._mono = monotonic
        self._started = monotonic()
        self._closed = False
        self._closing = False
        self._close_hooks = {}
        self._cleanup_results = {}
        self._used = False
        self._lock = threading.RLock()
        self._watchdog = None
        self._case_results = dict.fromkeys(CASES, "BLOCKED")

    def remaining(self):
        # BOTH monotonic elapsed and the original UTC deadline bound activity.
        wall = (self.deadline - utc(self._clock())).total_seconds()
        elapsed = self._mono() - self._started
        if elapsed < 0:
            raise Refused("monotonic clock moved backwards")
        return min(wall, self._window - elapsed)

    def require_active(self, minimum=0):
        if self._closed or self._closing:
            raise Refused("run closed")
        left = self.remaining()
        if left <= minimum:
            raise Refused("run deadline reached or safety margin exhausted")
        return left

    def register_closure(self, *, acceptors, issuer, cp, private):
        """Register full-fence cleanup before the first possible side effect.

        Callbacks must destroy trust in both issuer and every accepting runtime;
        none may be silently skipped after another callback fails.
        """
        if self._used or self._close_hooks or self._closed:
            raise Refused("cleanup must be registered once before activity")
        hooks = dict(acceptors=acceptors, issuer=issuer, cp=cp, private=private)
        if any(not callable(hooks[name]) for name in CLOSURE_ORDER):
            raise Refused("all four closure owners must be callable")
        self._close_hooks = hooks
        # A separate wall-clock watchdog closes an idle run at the immutable
        # deadline; the caller must additionally use an external process-level
        # timeout and recovery after crash/SIGKILL.
        seconds = max(0, self.remaining())
        self._watchdog = threading.Timer(seconds, self.close)
        self._watchdog.daemon = True
        self._watchdog.start()

    def execute(self, operation, callback, *, max_seconds=30):
        """Perform one bounded action; never log callback results or credentials."""
        if not self._close_hooks or set(self._close_hooks) != set(CLOSURE_ORDER):
            raise Refused("full cleanup not registered")
        if not isinstance(operation, str) or not operation or not callable(callback):
            raise Refused("invalid operation")
        if not isinstance(max_seconds, (int, float)) or not math.isfinite(max_seconds) or max_seconds <= 0:
            raise Refused("invalid operation timeout")
        self._used = True
        try:
            limit = min(self.require_active(), float(max_seconds))
            result = callback(limit)
            self.require_active()
            return result
        except BaseException:
            self.close()
            raise

    def token_ceiling(self, minimum=5):
        """Maximum *lifetime* an actual issuer may grant from this instant.

        Runtime must independently read back issuer expiry and verify it is
        within both the ceiling and immutable deadline. This is not issuance.
        """
        remaining = self.require_active(minimum)
        ttl = min(MAX_TOKEN_SECONDS, math.floor(remaining))
        if ttl < minimum:
            raise Refused("insufficient run lifetime for a token")
        return ttl

    def verify_issued_token_window(self, issued_at, expires_at, requested_seconds):
        """Reject late or widened token responses before exposing to acceptors."""
        now = utc(self._clock())
        issued_at, expires_at = utc(issued_at), utc(expires_at)
        if (not isinstance(requested_seconds, int) or
            not 0 < requested_seconds <= MAX_TOKEN_SECONDS or
            issued_at > now or expires_at <= now or
            expires_at > self.deadline or
            (expires_at - issued_at).total_seconds() > requested_seconds):
            self.close()
            raise Refused("issuer token crossed absolute authorization window")
        self.require_active()

    def record_case(self, case, evidence_verified):
        """Record test progress, never infer it from fixture files or simulations."""
        self.require_active()
        if case not in self._case_results or evidence_verified is not True:
            raise Refused("unverified connected observation")
        # This is only engineering progress. A separate live executor must own
        # provenance and the eventual qualification evidence/attestation.
        self._case_results[case] = "OBSERVED_UNATTESTED"

    def close(self):
        """Attempt every fence, including after a partial failed provision."""
        with self._lock:
            if self._closed:
                return dict(self._cleanup_results)
            self._closing = True
            if self._watchdog is not None:
                self._watchdog.cancel()
            for name in CLOSURE_ORDER:
                hook = self._close_hooks.get(name)
                try:
                    verified = hook() if hook is not None else False
                    self._cleanup_results[name] = "VERIFIED" if verified is True else "UNVERIFIED"
                except Exception:
                    self._cleanup_results[name] = "FAILED"
            self._closed = True
            return dict(self._cleanup_results)

    def receipt(self):
        """Sanitized status; NEVER an actual NAB-03 qualification receipt."""
        return {
            "schema": "infrastructure.int03.cms-lifecycle-preparation.v1",
            "scope": [CONSUMER, VALIDATOR],
            "deadline": self.deadline.isoformat(),
            "closed": self._closed,
            "cleanup": dict(self._cleanup_results),
            "cases": dict(self._case_results),
            "qualified": False,
            "full_int03_acceptance": False,
            "connected_executor_attested": False,
        }

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False
