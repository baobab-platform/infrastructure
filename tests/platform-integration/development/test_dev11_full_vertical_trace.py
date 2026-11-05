"""Source-only regressions for the independent real-Jaeger + PG17 verifier.
Fixtures are NEVER classified as executed L4 evidence.
"""
from __future__ import annotations
import base64
import copy
import unittest
from dev11_full_vertical_trace import Blocked, project_original_export

TRACE = "1"*32
EVENT = "22222222-2222-4222-8222-222222222222"
def enc(raw):
    return base64.b64encode(bytes.fromhex(raw)).decode("ascii")
def span(number, service, name, parent=0, *, identity=False):
    sid = f"{number:016x}"
    attrs = [{"key":"messaging.message.id","value":{"stringValue":EVENT}}] if identity else []
    return {"service":service,
            "data":{"traceId":enc(TRACE),"spanId":enc(sid),
                    "name":name,"attributes":attrs,
                    **({"parentSpanId":enc(f"{parent:016x}")} if parent else {})}}
def original():
    operations = [
        span(1,"zuribeans-bff","baobab.zuribeans.bff.request"),
        span(2,"zuribeans-bff","baobab.zuribeans.bff.credentialed_http",1),
        span(3,"baobab-iam","baobab.iam.http",2),
        span(4,"baobab-iam","baobab.iam.issuer.client",3),
        span(5,"baobab-trade","baobab.trade.http",2),
        span(6,"baobab-trade","baobab.trade.cp.http",5),
        span(7,"baobab-cp","baobab.cp.http",6),
        span(8,"baobab-cp","baobab.cp.iam.introspect",7),
        span(9,"baobab-trade","baobab.trade.outbox.insert",5,identity=True),
        span(10,"baobab-trade-rabbit-publisher","baobab.trade.rabbit.publish",9,identity=True),
        span(11,"baobab-erp","baobab.erp.inbox.execute",9,identity=True),
        span(12,"baobab-erp","baobab.erp.jvm.create",11),
    ]
    groups = []
    for op in operations:
        groups.append({
            "resource":{"attributes":[
                {"key":"service.name","value":{"stringValue":op["service"]}}]},
            "scopeSpans":[{"spans":[op["data"]]}]})
    return {"result":{"resourceSpans":groups}}

class FullVerticalExportTests(unittest.TestCase):
    def test_connected_exported_graph_component_only(self):
        outcome = project_original_export(original(),TRACE,EVENT)
        self.assertTrue(outcome["same_persisted_event_id_in_three_exported_spans"])
        self.assertEqual(outcome["l4_ops_01"],"BLOCKED")
        self.assertEqual(outcome["observed_span_count"],12)

    def test_missing_bff_issuer_cp_trade_broker_erp_refused(self):
        for service in ["zuribeans-bff","baobab-iam","baobab-cp",
                        "baobab-trade","baobab-trade-rabbit-publisher","baobab-erp"]:
            data = original()
            data["result"]["resourceSpans"] = [
                item for item in data["result"]["resourceSpans"]
                if item["resource"]["attributes"][0]["value"]["stringValue"] != service]
            with self.subTest(service=service),self.assertRaises(Blocked):
                project_original_export(data, TRACE, EVENT)

    def test_missing_native_rpc_span_denies_engine_claim(self):
        data = original()
        data["result"]["resourceSpans"] = [
            group for group in data["result"]["resourceSpans"]
            if group["scopeSpans"][0]["spans"][0]["name"] != "baobab.erp.jvm.create"]
        with self.assertRaisesRegex(Blocked,"EXPORTED_SERVICE_OR_OPERATION_ABSENT"):
            project_original_export(data,TRACE,EVENT)

    def test_mismatched_event_and_orphaned_client_are_not_accepted(self):
        data = original()
        for group in data["result"]["resourceSpans"]:
            item = group["scopeSpans"][0]["spans"][0]
            if item["name"] == "baobab.erp.inbox.execute":
                item["attributes"][0]["value"]["stringValue"] = "wrong-event"
        with self.assertRaisesRegex(Blocked,"PERSISTED_EVENT_ID_SPAN_MISMATCH"):
            project_original_export(data,TRACE,EVENT)
        altered = original()
        altered["result"]["resourceSpans"][6]["scopeSpans"][0]["spans"][0][
            "parentSpanId"] = enc("eeeeeeeeeeeeeeee")
        with self.assertRaisesRegex(Blocked,"ORPHAN_OR_CYCLIC_EXPORTED_SPAN"):
            project_original_export(altered,TRACE,EVENT)

    def test_connected_but_incorrect_issuer_broker_parentage_is_refused(self):
        for pos, parent, code in [
            (2, 1, "BFF_IAM_ISSUER_CAUSAL_EDGE_ABSENT"),
            (3, 1, "IAM_ISSUER_CLIENT_CAUSAL_EDGE_ABSENT"),
            (7, 1, "CP_IAM_INTROSPECTION_CAUSAL_EDGE_ABSENT"),
            (8, 1, "TRADE_EVENT_PRODUCER_CAUSAL_EDGE_ABSENT"),
            (9, 5, "PERSISTED_OUTBOX_PUBLISHER_CAUSAL_EDGE_ABSENT"),
            (10, 5, "ORIGINAL_EVENT_BROKER_CONSUMER_EDGE_ABSENT"),
        ]:
            graph = original()
            graph["result"]["resourceSpans"][pos]["scopeSpans"][0]["spans"][0][
                "parentSpanId"] = enc(f"{parent:016x}")
            with self.subTest(index=pos), self.assertRaisesRegex(Blocked, code):
                project_original_export(graph, TRACE, EVENT)

    def test_exported_private_credentials_sql_and_customer_data_are_refused(self):
        for secret_name, secret_value in [
            ("http.request.header.authorization", "Bearer a.private.secret"),
            ("db.statement", "select * from private_customer"),
            ("enduser.id", "person-123"),
            ("url.full", "https://iam.example.test/oauth2/token?secret=private"),
            ("baobab.operation", "Bearer private.jwt.value"),
        ]:
            graph = original()
            graph["result"]["resourceSpans"][7]["scopeSpans"][0]["spans"][0][
                "attributes"].append({
                    "key": secret_name, "value": {"stringValue": secret_value}
                })
            with self.subTest(attribute=secret_name), self.assertRaisesRegex(
                Blocked, "EXPORTED_PRIVATE_ATTRIBUTE_REFUSED"
            ):
                project_original_export(graph, TRACE, EVENT)

    def test_source_only_aggregate_cannot_certify_native_l4(self):
        result = project_original_export(original(),TRACE,EVENT)
        self.assertFalse(result["protected_acceptance"])
        self.assertEqual(result["l4_ops_01"],"BLOCKED")

if __name__ == "__main__":
    unittest.main()
