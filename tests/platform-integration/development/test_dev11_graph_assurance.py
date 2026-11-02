"""Synthetic DEV-11 DAG and async-link negatives; not runtime qualification."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dev11_assurance import Refused
from dev11_graph_assurance import VERSION, verify_graph

CORRELATION = "a1234567-89ab-cdef-0123-456789abcdef"
EVENT = "e1234567-89ab-cdef-0123-456789abcdef"


def make_graph():
    trace_a, trace_b = "a" * 32, "b" * 32
    def key(trace, span):
        return {"trace_id": trace, "span_id": f"{span:016x}"}
    def row(role, trace, span, parent, boundary="HTTP", event=None, links=None):
        return {"service_role": role, "traceparent": f"00-{trace}-{span:016x}-01",
                "parent": parent, "links": links or [], "correlation_id": CORRELATION,
                "boundary": boundary, "event_id": event, "result": "PASS", "cause": "NONE"}
    spans = [
        row("bff", trace_a, 1, None),
        row("issuer", trace_a, 2, key(trace_a, 1)),
        row("cp", trace_a, 3, key(trace_a, 2)),
        row("engine", trace_a, 4, key(trace_a, 3)),
        row("outbox", trace_a, 5, key(trace_a, 4), "EVENT_PUBLISH", EVENT),
        row("consumer", trace_b, 1, None, "EVENT_CONSUME", EVENT, [key(trace_a, 5)]),
    ]
    return {"schema": VERSION, "source_sha": "c" * 40,
            "profile": "DEV-07", "scenario": "DEV11-ASYNC-01",
            "correlation_id": CORRELATION, "spans": spans,
            "runtime_observed": True, "teardown_verified": True,
            "evidence_class": "REAL_COMPONENT_SYNTHETIC_DATA"}


class Dev11GraphTests(unittest.TestCase):
    def test_async_link_valid_structure_not_runtime_success(self):
        result = verify_graph(make_graph())
        self.assertEqual(result["span_count"], 6)
        self.assertTrue(result["trace_graph_valid"])
        self.assertEqual(result["result"], "PASS")
        self.assertFalse(result["runtime_qualified"])
        self.assertNotIn("spans", result)
        self.assertNotIn("correlation_id", result)

    def test_valid_branch(self):
        graph = make_graph()
        # The extra engine branch follows CP but must not impersonate an async consumer.
        extra = copy.deepcopy(graph["spans"][3])
        extra["traceparent"] = "00-" + "a" * 32 + "-" + f"{9:016x}" + "-01"
        graph["spans"].append(extra)
        self.assertEqual(verify_graph(graph)["span_count"], 7)

    def test_missing_broken_and_cross_trace_parents_fail_closed(self):
        for edit in (
            lambda x: x["spans"][2]["parent"].update(span_id="f" * 16),
            lambda x: x["spans"][2]["parent"].update(trace_id="b" * 32),
            lambda x: x["spans"][1].update(parent=None),
            lambda x: x["spans"].pop(0),
            lambda x: x["spans"][3]["parent"].update(span_id=f"{4:016x}"),
        ):
            graph = make_graph()
            edit(graph)
            with self.assertRaises(Refused):
                verify_graph(graph)

    def test_wrong_event_source_or_identity_fails(self):
        for edit in (
            lambda x: x["spans"][-1].update(event_id=CORRELATION),
            lambda x: x["spans"][-1].update(links=[{"trace_id":"a"*32,"span_id":f"{4:016x}"}]),
            lambda x: x["spans"][-1].update(links=[]),
            lambda x: x["spans"][-2].update(boundary="HTTP", event_id=None),
        ):
            graph = make_graph()
            edit(graph)
            with self.assertRaises(Refused):
                verify_graph(graph)

    def test_secret_and_unbounded_fields_rejected(self):
        for edit in (
            lambda x: x.update(headers={"authorization": "Bearer secret"}),
            lambda x: x["spans"][0].update(url="/customer/example@example.com"),
            lambda x: x["spans"][2].update(error_message="password=secret"),
            lambda x: x["spans"][0].update(traceparent=x["spans"][0]["traceparent"]+"\nX"),
            lambda x: x["spans"][-1].update(links=[{"trace_id":"a"*32,"span_id":f"{5:016x}"}]*9),
        ):
            graph = make_graph()
            edit(graph)
            with self.assertRaises(Refused) as err:
                verify_graph(graph)
            self.assertNotIn("secret", str(err.exception))

    def test_negative_result_stays_negative(self):
        for outcome,cause in (("FAIL","INCORRECT_RESULT"),
                              ("BLOCKED","AUTHORITY_UNQUALIFIED"),
                              ("NOT_RUN","NOT_EXECUTED")):
            graph = make_graph()
            graph["spans"][-1].update(result=outcome,cause=cause)
            report = verify_graph(graph)
            self.assertEqual(report["result"], outcome)
            self.assertFalse(report["runtime_qualified"])

    def test_no_self_links_or_duplicate_nodes(self):
        for edit in (
            lambda x: x["spans"][-1]["links"].append({"trace_id":"b"*32,"span_id":f"{1:016x}"}),
            lambda x: x["spans"].append(copy.deepcopy(x["spans"][0])),
            lambda x: x["spans"][-1]["links"].append(copy.deepcopy(x["spans"][-1]["links"][0])),
        ):
            graph = make_graph()
            edit(graph)
            with self.assertRaises(Refused):
                verify_graph(graph)

    def test_validation_does_not_accept_self_reported_runtime(self):
        graph = make_graph()
        graph["runtime_observed"] = True
        graph["teardown_verified"] = True
        self.assertFalse(verify_graph(graph)["runtime_qualified"])


if __name__ == "__main__":
    unittest.main()
