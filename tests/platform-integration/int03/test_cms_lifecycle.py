"""Contract tests for pre-gate immutable CMS fixture lifecycle.

Fake callbacks below prove only guard behaviour, never live IAM/CP/CMS.
"""
from datetime import datetime, timedelta, timezone
import unittest

import cms_gate
from cms_lifecycle import Lifecycle, Refused, MAX_RUN_SECONDS


NOW = datetime(2026, 10, 22, 8, 0, tzinfo=timezone.utc)


def gate(state="OPEN"):
    return cms_gate.receipt(state, ["CONNECTED_LANE_REQUIRED"], "a" * 40, "b" * 64, "c" * 64)


class Clock:
    def __init__(self):
        self.elapsed = 0

    def now(self):
        return NOW + timedelta(seconds=self.elapsed)

    def mono(self):
        return float(self.elapsed)


def new_lifecycle(clock=None, verdict="OPEN", seconds=100):
    clock = clock or Clock()
    return Lifecycle(gate(verdict), NOW + timedelta(seconds=seconds),
                     now=clock.now, monotonic=clock.mono), clock


def hooks(owner, labels):
    owner.register_closure(**{name: lambda name=name: labels.append(name) or True
                             for name in ("acceptors", "issuer", "cp", "private")})


class Preflight(unittest.TestCase):
    def test_held_and_refused_gates_cannot_provision(self):
        for verdict in ("HELD", "REFUSED"):
            with self.assertRaisesRegex(Refused, "not OPEN"):
                new_lifecycle(verdict=verdict)
        for invalid in ({}, {"schema": "infrastructure.int03.cms-gate.v1"}):
            with self.assertRaises(Refused):
                Lifecycle(invalid, NOW + timedelta(seconds=80), now=lambda: NOW)

    def test_requires_exact_blocked_cases_and_source(self):
        for key, value in (("cases", {}), ("qualified", True), ("identities_created", True),
                           ("scenario", "different"), ("shared", {"commit": "short"})):
            data = gate()
            data[key] = value
            with self.assertRaises(Refused):
                Lifecycle(data, NOW + timedelta(seconds=90), now=lambda: NOW)

    def test_deadline_absolute_and_bounded(self):
        for seconds in (0, 60, 5401, -1):
            with self.assertRaises(Refused):
                new_lifecycle(seconds=seconds)
        owner, clock = new_lifecycle(seconds=MAX_RUN_SECONDS)
        clock.elapsed = 5400
        with self.assertRaises(Refused):
            owner.require_active()

    def test_timezone_awareness_required(self):
        with self.assertRaises(Refused):
            Lifecycle(gate(), datetime(2026, 10, 22, 9), now=lambda: NOW)


class Closing(unittest.TestCase):
    def test_register_before_mutation_once(self):
        o, _ = new_lifecycle()
        with self.assertRaises(Refused):
            o.execute("provision", lambda _: True)
        with self.assertRaises(Refused):
            o.register_closure(acceptors=lambda: True, issuer=lambda: True,
                               cp=lambda: True, private=None)
        labels = []
        hooks(o, labels)
        with self.assertRaises(Refused):
            hooks(o, labels)
        self.assertEqual(o.execute("provision", lambda limit: limit > 0), True)
        self.assertEqual(o.close(), {name: "VERIFIED" for name in labels})
        self.assertEqual(labels, ["acceptors", "issuer", "cp", "private"])
        self.assertIs(o.receipt()["qualified"], False)
        with self.assertRaises(Refused):
            o.execute("late", lambda _: True)
        self.assertEqual(len(labels), 4)

    def test_failed_post_does_not_skip_fences(self):
        o, _ = new_lifecycle()
        labels = []
        hooks(o, labels)
        with self.assertRaisesRegex(ValueError, "post failed"):
            o.execute("provision", lambda limit: (_ for _ in ()).throw(ValueError("post failed")))
        self.assertEqual(labels, ["acceptors", "issuer", "cp", "private"])

    def test_every_cleanup_attempted_even_if_some_fail(self):
        o, _ = new_lifecycle()
        labels = []
        def failed():
            labels.append("issuer")
            raise RuntimeError("destroy failed")
        o.register_closure(acceptors=lambda: labels.append("acceptors") or False,
                           issuer=failed, cp=lambda: labels.append("cp") or True,
                           private=lambda: labels.append("private") or True)
        self.assertEqual(o.close(), {
            "acceptors": "UNVERIFIED", "issuer": "FAILED",
            "cp": "VERIFIED", "private": "VERIFIED",
        })
        self.assertEqual(labels, ["acceptors", "issuer", "cp", "private"])

    def test_context_manager_closes_even_if_caller_fails(self):
        o, _ = new_lifecycle()
        labels = []
        hooks(o, labels)
        with self.assertRaises(RuntimeError):
            with o:
                raise RuntimeError("unexpected")
        self.assertEqual(len(labels), 4)


class TokenAndCases(unittest.TestCase):
    def test_token_cannot_outlive_run(self):
        o, clock = new_lifecycle(seconds=80)
        labels = []
        hooks(o, labels)
        self.assertEqual(o.token_ceiling(), 60)
        clock.elapsed = 40
        self.assertEqual(o.token_ceiling(), 40)
        o.verify_issued_token_window(clock.now() - timedelta(seconds=1),
                                    clock.now() + timedelta(seconds=30), 60)
        with self.assertRaisesRegex(Refused, "crossed absolute"):
            o.verify_issued_token_window(clock.now(),
                                         NOW + timedelta(seconds=81), 60)
        self.assertEqual(len(labels), 4)

    def test_unverified_or_partial_scenarios_never_qualify(self):
        o, _ = new_lifecycle()
        with self.assertRaises(Refused):
            o.record_case("published-home-nav-footer", False)
        with self.assertRaises(Refused):
            o.record_case("invented", True)
        o.record_case("published-home-nav-footer", True)
        r = o.receipt()
        self.assertEqual(len(r["cases"]), 14)
        self.assertEqual(r["cases"]["published-home-nav-footer"], "OBSERVED_UNATTESTED")
        self.assertEqual(r["cases"]["teardown"], "BLOCKED")
        self.assertFalse(r["qualified"])


if __name__ == "__main__":
    unittest.main()
