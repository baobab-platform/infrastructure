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

class NativeBuyerLineageTests(unittest.TestCase):
    def test_matches_exact_outbox_event_and_refuses_substituted_erp_delivery(self):
        event_id = "trade-order-event-1"
        origin = {
            "schema": "baobab.trade.dev11.native-origin.v1",
            "classification": "SOURCE_SQL_READBACK_ONLY",
            "reason": "NATIVE_ORIGIN_SQL_CONFIRMED",
            "native_origin_qualified": True, "native_order_readback": True,
            "enforced_b2b_commit": True, "exact_commit_transaction": True,
            "spend_commit_same_transaction": True,
            "business_origin": {
                "event_id": event_id, "transaction_id": "101",
                "persisted_envelope_digest": "b" * 64,
                "traceparent": f"00-{TRACE}-{'5' * 16}-01",
            },
        }
        groups = []

        def emit(service, sid, name, parent="", link=False, **attributes):
            links = [{"traceId": raw(TRACE), "spanId": raw("5" * 16)}] if link else []
            group = node(service, sid * 16, parent * 16, links=links)
            groups.append(group)
            span = group["scopeSpans"][0]["spans"][0]
            span["name"] = name
            span["kind"] = "SPAN_KIND_SERVER"
            span["attributes"] = [{"key": k, "value": {"stringValue": v}} for k, v in attributes.items()]
            return span

        message = {"messaging.message.id": event_id}
        emit("zuribeans-bff", "1", "baobab.zuribeans.bff.request",
             **{"baobab.route": "buyer-commit", "http.response.status_class": "2xx"})
        emit("baobab-iam", "2", "iam", "1")
        emit("baobab-trade", "3", "baobab.trade.http", "1")
        emit("baobab-cp", "4", "cp", "3")
        emit("baobab-trade", "5", "baobab.trade.outbox.insert", "3", **message)
        emit("baobab-trade-rabbit-publisher", "6", "baobab.trade.rabbit.publish", "5",
             link=True, **message, **{"baobab.outbox.result": "PUBLISHED"})
        admission = emit("baobab-erp", "7", "baobab.erp.inbox.admit", "5",
                         link=True, **message, **{"baobab.erp.event_outcome": "ADMITTED"})
        emit("baobab-erp", "8", "baobab.erp.inbox.execute", "5",
             link=True, **message, **{"baobab.erp.event_outcome": "BUSINESS_PROCESSED"})
        emit("baobab-erp", "9", "baobab.erp.jvm.create", "8")
        trace = {"result": {"resourceSpans": groups}}
        result = project(trace, TRACE, ["baobab-erp"], origin)
        self.assertEqual(result["native_buyer_trace"]["event_id"], event_id)
        self.assertFalse(result["consumer_business_effect_qualified"])

        admission["attributes"][0]["value"]["stringValue"] = "different-event"
        with self.assertRaisesRegex(TraceNotVerified, "NATIVE_BUYER_ASYNC_EVENT_PATH_NOT_OBSERVED"):
            project(trace, TRACE, ["baobab-erp"], origin)

if __name__ == "__main__":
    unittest.main()
