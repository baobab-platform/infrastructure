#!/usr/bin/env python3
"""DEV-11 full-operation independent L4 observer, not a producer receipt.

The initial L4 cut demands one real BFF-origin trace, actual issuer/CP/Trade
HTTP and native event spans, a signed-broker consumer, an actual ERP->iDempiere
client call, and separate original PostgreSQL business-effect readback.
No stage can mark itself PASS. Native source IDs, traces and tokens are private.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from pathlib import Path

from dev11_exported_trace import identifier, query

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
TRACE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-01$")
# These are exported operation names, never caller-supplied service labels.
REQUIRED = {
    "zuribeans-bff": {
        "baobab.zuribeans.bff.request", "baobab.zuribeans.bff.credentialed_http"},
    "baobab-iam": {"baobab.iam.http", "baobab.iam.issuer.client"},
    "baobab-cp": {"baobab.cp.http", "baobab.cp.iam.introspect"},
    "baobab-trade": {
        "baobab.trade.http", "baobab.trade.cp.http", "baobab.trade.outbox.insert"},
    "baobab-trade-rabbit-publisher": {"baobab.trade.rabbit.publish"},
    "baobab-erp": {
        "baobab.erp.inbox.execute", "baobab.erp.jvm.create"},
}
EVENT_SPANS = {
    ("baobab-trade", "baobab.trade.outbox.insert"),
    ("baobab-trade-rabbit-publisher", "baobab.trade.rabbit.publish"),
    ("baobab-erp", "baobab.erp.inbox.execute"),
}
ALLOWED_EVENT_TYPE = "com.baobab-platform.trade.order.placed.v1"
SOURCE = "urn:baobab-platform:service:baobab-trade"

class Blocked(Exception):
    pass

def require(ok, cause):
    if not ok:
        raise Blocked(cause)

def attributes(values):
    require(isinstance(values, list) and len(values) <= 100, "EXPORTED_ATTRIBUTES_INVALID")
    result = {}
    for item in values:
        require(isinstance(item, dict) and type(item.get("key")) is str,
                "EXPORTED_ATTRIBUTES_INVALID")
        key = item["key"]
        require(key not in result and len(key) <= 128, "EXPORTED_ATTRIBUTES_INVALID")
        v = item.get("value")
        require(isinstance(v, dict), "EXPORTED_ATTRIBUTES_INVALID")
        if "stringValue" in v:
            require(type(v["stringValue"]) is str and len(v["stringValue"]) <= 512,
                    "EXPORTED_ATTRIBUTES_INVALID")
            result[key] = v["stringValue"]
    return result

def project_original_export(payload, trace_id, event_id):
    """Reject missing, duplicate or unexported parent/links on a queried OTLP graph."""
    require(type(payload) is dict and type(payload.get("result")) is dict,
            "JAEGER_RESPONSE_INVALID")
    groups = payload["result"].get("resourceSpans")
    require(type(groups) is list and 1 <= len(groups) <= 100, "JAEGER_RESPONSE_INVALID")
    spans = {}
    for group in groups:
        require(type(group) is dict and type(group.get("resource")) is dict,
                "JAEGER_RESPONSE_INVALID")
        service = attributes(group["resource"].get("attributes", [])).get("service.name")
        require(type(service) is str, "SERVICE_NAME_UNVERIFIED")
        for scope in group.get("scopeSpans", []):
            require(type(scope) is dict, "JAEGER_RESPONSE_INVALID")
            for raw in scope.get("spans", []):
                require(type(raw) is dict and len(spans) < 10000, "JAEGER_RESPONSE_INVALID")
                tid = identifier(raw.get("traceId"), 16)
                sid = identifier(raw.get("spanId"), 8)
                parent = identifier(raw.get("parentSpanId"), 8) if raw.get("parentSpanId") else ""
                require(tid == trace_id and sid and sid != "0"*16 and sid not in spans,
                        "EXPORTED_SPAN_INVALID")
                name = raw.get("name")
                require(type(name) is str and len(name) <= 128 and parent != sid,
                        "EXPORTED_SPAN_INVALID")
                links = raw.get("links", [])
                require(type(links) is list and len(links) <= 64, "EXPORTED_LINK_INVALID")
                spans[sid] = {"service": service, "name": name, "parent": parent,
                              "attributes": attributes(raw.get("attributes", [])),
                              "links": links}
    require(bool(spans), "NO_EXPORTED_SPANS")
    roots = [sid for sid, value in spans.items() if not value["parent"]]
    require(len(roots) == 1 and spans[roots[0]]["service"] == "zuribeans-bff" and
            spans[roots[0]]["name"] == "baobab.zuribeans.bff.request",
            "BFF_EXPORTED_ROOT_ABSENT")
    descendants = 0
    for sid, value in spans.items():
        visited = {sid}
        parent = value["parent"]
        while parent:
            require(parent in spans and parent not in visited,
                    "ORPHAN_OR_CYCLIC_EXPORTED_SPAN")
            visited.add(parent)
            parent = spans[parent]["parent"]
        require(roots[0] in visited, "BFF_TRACE_NOT_CAUSAL")
        descendants += len(visited) - 1
        for link in value["links"]:
            require(type(link) is dict, "EXPORTED_LINK_INVALID")
            tid = identifier(link.get("traceId"), 16)
            linked = identifier(link.get("spanId"), 8)
            require(tid and linked, "EXPORTED_LINK_INVALID")
            if tid == trace_id:
                require(linked in spans, "EXPORTED_LINK_UNOBSERVED")
    require(descendants > 0, "EXPORTED_GRAPH_NOT_CONNECTED")
    for service, names in REQUIRED.items():
        observed = {v["name"] for v in spans.values() if v["service"] == service}
        require(names <= observed, "EXPORTED_SERVICE_OR_OPERATION_ABSENT")
    observed_events = set()
    for span in spans.values():
        key = (span["service"], span["name"])
        if key in EVENT_SPANS:
            require(span["attributes"].get("messaging.message.id") == event_id,
                    "PERSISTED_EVENT_ID_SPAN_MISMATCH")
            observed_events.add(key)
    require(observed_events == EVENT_SPANS, "EVENT_SPAN_COVERAGE_INCOMPLETE")
    # Verify the correct business direction: BFF client -> Trade server,
    # Trade client -> CP server, and outbox -> publisher -> consumer -> JVM.
    def has_parent(child_service, child_name, parent_service):
        return any(
            value["service"] == child_service and value["name"] == child_name and
            value["parent"] in spans and spans[value["parent"]]["service"] == parent_service
            for value in spans.values())
    require(has_parent("baobab-trade", "baobab.trade.http", "zuribeans-bff"),
            "BFF_TRADE_CAUSAL_BOUNDARY_ABSENT")
    require(has_parent("baobab-cp", "baobab.cp.http", "baobab-trade"),
            "TRADE_CP_CAUSAL_BOUNDARY_ABSENT")
    require(has_parent("baobab-erp", "baobab.erp.jvm.create", "baobab-erp"),
            "ERP_NATIVE_JVM_CALL_NOT_EXPORTED")
    require(has_parent("baobab-erp", "baobab.erp.inbox.execute",
                       "baobab-trade-rabbit-publisher") or
            any(v["service"] == "baobab-erp" and
                v["name"] == "baobab.erp.inbox.execute" and
                v["parent"] in spans and
                spans[v["parent"]]["service"] == "baobab-trade"
                for v in spans.values()),
            "BROKER_CONSUMER_CAUSAL_BOUNDARY_ABSENT")
    return {
        "schema": "infrastructure.dev11.full-operation-otel.v1",
        "run_class": "INDEPENDENT_JAEGER_AND_POSTGRESQL_READBACK",
        "exported_bff_issuer_cp_trade_broker_erp_lineage": True,
        "same_persisted_event_id_in_three_exported_spans": True,
        "observed_services": sorted({v["service"] for v in spans.values()}),
        "observed_span_count": len(spans),
        "l4_ops_01": "BLOCKED",  # native business readback is a separate gate
        "protected_acceptance": False,
    }

def read_native_sources(trade, erp, cp, event_id):
    """Three independent READ ONLY PostgreSQL snapshots, never self-reported PASS."""
    with trade.transaction():
        trade.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        source = trade.execute(
            "SELECT envelope,tenant_id,event_type,idempotency_key,status "
            "FROM event_outbox WHERE event_id=%s AND deleted_at IS NULL",
            (event_id,)).fetchall()
        # The seller PEP must have produced an original immutable authority
        # receipt for THIS native commerce order, not a later CP assertion.
        seller = trade.execute(
            "SELECT r.decision_id::text AS seller_decision_id,"
            "r.context_id::text AS seller_context_id,r.market AS market,"
            "r.currency,r.tenant_id,r.responsible_legal_entity_id,"
            "r.operation_class,r.consumed_at "
            "FROM trade_order_commitment k "
            "JOIN trade_order_authority_receipt r ON r.receipt_id=k.receipt_id "
            "JOIN event_outbox o ON o.envelope->'data'->>'commerce_order_id'=k.order_id "
            "WHERE o.event_id=%s", (event_id,)).fetchall()
    require(len(source) == 1 and source[0]["status"] == "PUBLISHED" and
            source[0]["event_type"] == ALLOWED_EVENT_TYPE,
            "TRADE_ORIGINAL_EVENT_NOT_PUBLISHED")
    envelope = source[0]["envelope"]
    require(type(envelope) is dict and envelope.get("id") == event_id and
            envelope.get("source") == SOURCE and
            envelope.get("idempotencykey") == source[0]["idempotency_key"] and
            envelope.get("tenantid") == source[0]["tenant_id"],
            "TRADE_PERSISTED_ENVELOPE_CHANGED")
    matched = TRACE.fullmatch(envelope.get("traceparent", ""))
    require(matched is not None, "TRADE_PERSISTED_TRACEPARENT_UNAVAILABLE")
    order_id = envelope.get("data", {}).get("commerce_order_id")
    require(type(order_id) is str and len(order_id) > 8, "NATIVE_ORDER_ID_UNAVAILABLE")
    require(len(seller) == 1 and seller[0]["operation_class"] == "trade.order.commit" and
            seller[0]["tenant_id"] == source[0]["tenant_id"] and
            seller[0]["responsible_legal_entity_id"] == envelope["data"].get("legal_entity_id") and
            seller[0]["currency"] == envelope["data"].get("currency") and
            seller[0]["consumed_at"] is not None, "TRADE_SELLER_AUTHORITY_NOT_NATIVE")
    with erp.transaction():
        erp.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        inbox = erp.execute(
            "SELECT event_id::text,ce_source,tenant_id,payload_json,"
            "ce_idempotency_key,ce_correlation_id::text,ce_traceparent,status "
            "FROM baobab.event_inbox WHERE event_id=%s::uuid", (event_id,)).fetchall()
        effect = erp.execute(
            "SELECT e.source_event_id::text AS source_event_id,"
            "e.native_id AS executed_native_id,r.native_id AS mapped_native_id,"
            "o.c_order_id AS actual_native_id,"
            "o.ad_client_id AS actual_ad_client_id,"
            "o.ad_org_id AS actual_ad_org_id,"
            "r.native_uuid::text AS mapped_native_uuid,"
            "o.c_order_uu::text AS actual_native_uuid "
            "FROM baobab.order_execution e "
            "JOIN baobab.order_native_reference r "
            "ON r.tenant_id=e.tenant_id AND r.legal_entity_id=e.legal_entity_id "
            "AND r.commerce_order_id=e.commerce_order_id "
            "JOIN adempiere.c_order o ON o.c_order_uu::text=r.native_uuid::text "
            "WHERE e.tenant_id=%s AND e.commerce_order_id=%s",
            (source[0]["tenant_id"], order_id)).fetchall()
        audit = erp.execute(
            "SELECT a.decision_id::text,a.tenant_id,a.source_record_id "
            "FROM baobab_native.finance_authority_attribution a "
            "WHERE lower(a.source_table)='c_order' AND a.operation_class=%s "
            "AND a.tenant_id=%s AND a.source_record_id=%s",
            ("erp.sales-order.complete", source[0]["tenant_id"],
             effect[0]["actual_native_id"] if len(effect) == 1 else -1)).fetchall()
    require(len(inbox) == 1 and inbox[0]["event_id"] == event_id and
            inbox[0]["ce_source"] == SOURCE and inbox[0]["status"] == "processed" and
            inbox[0]["payload_json"] == envelope["data"] and
            inbox[0]["ce_idempotency_key"] == envelope["idempotencykey"] and
            inbox[0]["ce_correlation_id"] == envelope["correlationid"] and
            inbox[0]["ce_traceparent"] == envelope["traceparent"],
            "ERP_INBOX_EVENT_IDENTITY_CHANGED")
    # Independent native order IDs, UUIDs and source-event join must all agree.
    require(len(effect) == 1 and effect[0]["source_event_id"] == event_id and
            effect[0]["mapped_native_uuid"] == effect[0]["actual_native_uuid"] and
            effect[0]["executed_native_id"] == effect[0]["mapped_native_id"] ==
            effect[0]["actual_native_id"],
            "ERP_NATIVE_BUSINESS_EFFECT_NOT_JOINED")
    require(bool(audit), "ERP_NATIVE_JVM_ATTRIBUTION_ABSENT")
    with cp.transaction():
        cp.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        decisions = cp.execute(
            "SELECT decision_id::text,context_id::text,outcome,operation_class,"
            "tenant_id,market,currency,responsible_legal_entity_id,expires_at "
            "FROM registry.trade_order_authority_decision "
            "WHERE decision_id=%s::uuid", (seller[0]["seller_decision_id"],)).fetchall()
        require(len(decisions) == 1 and
                decisions[0]["outcome"] == "AUTHORIZED" and
                decisions[0]["operation_class"] == "trade.order.commit" and
                decisions[0]["context_id"] == seller[0]["seller_context_id"] and
                decisions[0]["tenant_id"] == source[0]["tenant_id"] and
                decisions[0]["market"] == seller[0]["market"] and
                decisions[0]["currency"] == seller[0]["currency"] and
                decisions[0]["responsible_legal_entity_id"] ==
                seller[0]["responsible_legal_entity_id"],
                "CP_NATIVE_SELLER_OPERATION_NOT_PROVEN")
        for row in audit:
            finance = cp.execute(
                "SELECT outcome,tenant_id FROM registry.erp_posting_authority_decision "
                "WHERE decision_id=%s::uuid", (row["decision_id"],)).fetchall()
            require(len(finance) == 1 and finance[0]["outcome"] == "AUTHORIZED" and
                    finance[0]["tenant_id"] == source[0]["tenant_id"],
                    "CP_IMMUTABLE_NATIVE_AUTHORITY_NOT_JOINED")

    # Use ERP's canonical two-database read-only verifier, rather than a
    # weaker local copy that accepts a matching decision ID without verifying
    # context lifetime, maker/checker, legal mandate or native order company.
    import importlib.util
    erp_source = Path(os.environ.get("DEV11_ERP_SOURCE", ""))
    verifier = erp_source / "scripts/dev11_verify_cp_native_lineage.py"
    require(verifier.is_file(), "ERP_NATIVE_AUTHORITY_VERIFIER_ABSENT")
    spec = importlib.util.spec_from_file_location("dev11_erp_authority_observer", verifier)
    require(spec is not None and spec.loader is not None,
            "ERP_NATIVE_AUTHORITY_VERIFIER_ABSENT")
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    with erp.transaction(), cp.transaction():
        erp.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cp.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        joined = owner.verify(
            erp, cp, tenant=source[0]["tenant_id"], order=order_id,
            entity=seller[0]["responsible_legal_entity_id"],
            market=seller[0]["market"],
            client=effect[0]["actual_ad_client_id"],
            org=effect[0]["actual_ad_org_id"],
            mapped_reference=True)
        require(joined["native_cp_lineage_qualified"],
                "CP_NATIVE_ERP_MANDATE_HISTORY_NOT_PROVEN")
    return matched.group(1)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--event-id", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--jaeger", default="http://127.0.0.1:16686")
    args = ap.parse_args()
    try:
        require(bool(UUID.fullmatch(args.event_id)), "ORIGINAL_EVENT_ID_INVALID")
        # Database roles must be read-only and independently provisioned.
        import psycopg
        from psycopg.rows import dict_row
        urls = [os.environ[k] for k in
                ("DEV11_TRADE_READONLY_URL", "DEV11_ERP_READONLY_URL", "DEV11_CP_READONLY_URL")]
        with psycopg.connect(urls[0], row_factory=dict_row) as trade, \
             psycopg.connect(urls[1], row_factory=dict_row) as erp, \
             psycopg.connect(urls[2], row_factory=dict_row) as cp:
            trace_id = read_native_sources(trade, erp, cp, args.event_id)
        result = project_original_export(query(args.jaeger, trace_id), trace_id, args.event_id)
        # A read-only CP and native-effect join is independently observed; it
        # does not certify the source provider or the legal facts it represents.
        result["independent_original_trade_erp_cp_native_join"] = True
        result["l4_ops_01"] = "BLOCKED"  # Full owner/estate custody stays separate.
        good = True
    except Exception as error:
        # psycopg driver failures and transport exceptions are closed too;
        # never publish private DB endpoint, SQL or provider exception text.
        code = str(error) if isinstance(error, Blocked) else "SOURCE_OR_EXPORT_UNAVAILABLE"
        result = {"schema":"infrastructure.dev11.full-operation-otel.v1",
                  "run_class":"INDEPENDENT_JAEGER_AND_POSTGRESQL_READBACK",
                  "source_and_exported_graph_verified":False, "reason":code,
                  "l4_ops_01":"BLOCKED", "protected_acceptance":False}
        good = False
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("DEV11_FULL_OPERATION_EXPORTED=" + ("COMPONENT_VERIFIED" if good else "BLOCKED"))
    return 0 if good else 2

if __name__ == "__main__":
    sys.exit(main())
