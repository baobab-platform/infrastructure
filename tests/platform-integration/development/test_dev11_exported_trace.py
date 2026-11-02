"""Read-only exported-trace DAG tests; no self-declared success accepted."""
import base64
import unittest

from dev11_exported_trace import TraceNotVerified, project

TRACE = "1" * 32

def raw(hex_value):
    return base64.b64encode(bytes.fromhex(hex_value)).decode("ascii")

def node(service, sid, parent="", *, trace=TRACE, links=()):
    return {
        "resource": {"attributes": [
            {"key": "service.name", "value": {"stringValue": service}}]},
        "scopeSpans": [{"spans": [{
            "traceId": raw(trace), "spanId": raw(sid),
            "parentSpanId": raw(parent) if parent else "",
            "name": "dev11.native.operation",
            "links": list(links),
        }]}],
    }

class ExportedLineageTests(unittest.TestCase):
    def good(self):
        return {"result": {"resourceSpans": [
            node("zuribeans", "1" * 16),
            node("baobab-cp", "2" * 16, "1" * 16),
            node("baobab-trade", "3" * 16, "2" * 16),
        ]}}

    def test_all_exported_spans_present(self):
        result = project(self.good(), TRACE,
                         ["zuribeans", "baobab-cp", "baobab-trade"])
        self.assertTrue(result["exported_lineage_observed"])
        self.assertEqual(result["parent_edges"], 2)
        self.assertFalse(result["native_source_attested"])
        self.assertFalse(result["consumer_business_effect_qualified"])
        self.assertEqual(result["l4_ops_01"], "BLOCKED")

    def test_missing_native_service_denied(self):
        with self.assertRaisesRegex(TraceNotVerified, "REQUIRED_NATIVE_SERVICES_ABSENT"):
            project(self.good(), TRACE, ["baobab-erp"])

    def test_missing_exported_parent_denied(self):
        doc = self.good()
        del doc["result"]["resourceSpans"][0]
        with self.assertRaisesRegex(TraceNotVerified, "MISSING_EXPORTED_PARENT"):
            project(doc, TRACE, ["baobab-cp"])

    def test_forged_trace_id_denied(self):
        doc = self.good()
        doc["result"]["resourceSpans"][1]["scopeSpans"][0]["spans"][0]["traceId"] = raw("2" * 32)
        with self.assertRaisesRegex(TraceNotVerified, "SPAN_IDENTITY_INVALID"):
            project(doc, TRACE, ["baobab-cp"])

    def test_duplicate_span_denied(self):
        doc = self.good()
        doc["result"]["resourceSpans"].append(
            node("baobab-erp", "3" * 16, "2" * 16))
        with self.assertRaisesRegex(TraceNotVerified, "DUPLICATE_SPAN"):
            project(doc, TRACE, ["baobab-erp"])

    def test_broken_same_trace_link_denied(self):
        doc = self.good()
        doc["result"]["resourceSpans"][2]["scopeSpans"][0]["spans"][0]["links"] = [
            {"traceId": raw(TRACE), "spanId": raw("a" * 16)}]
        with self.assertRaisesRegex(TraceNotVerified, "MISSING_EXPORTED_LINK"):
            project(doc, TRACE, ["baobab-trade"])

    def test_cross_trace_link_counted_not_automatically_accepted(self):
        doc = self.good()
        doc["result"]["resourceSpans"][2]["scopeSpans"][0]["spans"][0]["links"] = [
            {"traceId": raw("a" * 32), "spanId": raw("a" * 16)}]
        result = project(doc, TRACE, ["baobab-trade"])
        self.assertEqual(result["cross_trace_links"], 1)
        self.assertEqual(result["l4_ops_01"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
