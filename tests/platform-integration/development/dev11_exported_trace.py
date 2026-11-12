#!/usr/bin/env python3
"""DEV-11 independent observer of *exported* Jaeger v2 OTLP spans.

Uses a read-only query from a different process than the emitting workload.
Never accepts a producer-supplied 'PASS' or source assertion as runtime proof.
Prints only bounded service/count outcomes; raw spans never leave the lab.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
SERVICE = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
MAX_BYTES = 3_000_000


class TraceNotVerified(Exception):
    pass


def insist(condition, cause):
    if not condition:
        raise TraceNotVerified(cause)


def identifier(value, length):
    """OTLP JSON encodes fixed bytes as base64; some exporters emit hex."""
    if not isinstance(value, str):
        return ""
    if re.fullmatch(r"[0-9a-f]{" + str(length * 2) + r"}", value):
        return value
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, base64.binascii.Error):
        return ""
    return raw.hex() if len(raw) == length else ""


def service_name(resource):
    for item in resource.get("attributes", []):
        if isinstance(item, dict) and item.get("key") == "service.name":
            typed = item.get("value")
            if isinstance(typed, dict):
                return typed.get("stringValue")
    return None


def project(trace, trace_id, required, origin=None):
    insist(type(trace) is dict and isinstance(trace.get("result"), dict), "QUERY_FORMAT_INVALID")
    groups = trace["result"].get("resourceSpans")
    insist(isinstance(groups, list) and 0 < len(groups) <= 100, "RESOURCE_SPANS_INVALID")
    observed = {}
    for group in groups:
        insist(isinstance(group, dict), "RESOURCE_SPANS_INVALID")
        owner = service_name(group.get("resource", {}))
        insist(isinstance(owner, str) and SERVICE.fullmatch(owner), "SERVICE_IDENTITY_INVALID")
        scopes = group.get("scopeSpans", [])
        insist(isinstance(scopes, list) and len(scopes) <= 100, "RESOURCE_SPANS_INVALID")
        for scope in scopes:
            for span in scope.get("spans", []):
                insist(len(observed) < 10000 and isinstance(span, dict), "SPAN_COUNT_INVALID")
                tid = identifier(span.get("traceId"), 16)
                sid = identifier(span.get("spanId"), 8)
                parent = identifier(span.get("parentSpanId"), 8) if span.get("parentSpanId") else ""
                insist(tid == trace_id and sid and sid != "0" * 16 and
                       parent != sid, "SPAN_IDENTITY_INVALID")
                insist(sid not in observed, "DUPLICATE_SPAN")
                links = span.get("links", [])
                insist(isinstance(links, list) and len(links) <= 64, "SPAN_LINKS_INVALID")
                observed[sid] = {"service": owner, "parent": parent, "links": links}
                if origin is not None:
                    observed[sid]["span"] = span

    parents = 0
    outside_links = 0
    roots = 0
    for sid, span in observed.items():
        parent = span["parent"]
        if parent:
            insist(parent in observed, "MISSING_EXPORTED_PARENT")
            parents += 1
        else:
            roots += 1
        chain = {sid}
        while parent:
            insist(parent not in chain, "CYCLIC_EXPORTED_TRACE")
            chain.add(parent)
            parent = observed[parent]["parent"]
        for link in span["links"]:
            tid = identifier(link.get("traceId"), 16)
            linked = identifier(link.get("spanId"), 8)
            insist(tid and linked and tid != "0" * 32 and
                   linked != "0" * 16, "SPAN_LINKS_INVALID")
            if tid != trace_id:
                outside_links += 1
            else:
                insist(linked in observed, "MISSING_EXPORTED_LINK")

    services = sorted(set(s["service"] for s in observed.values()))
    insist(set(required).issubset(set(services)), "REQUIRED_NATIVE_SERVICES_ABSENT")
    insist(parents > 0 and roots > 0, "EXPORTED_LINEAGE_INCOMPLETE")
    report = {
        "schema": "infrastructure.dev11.exported-observation.v1",
        "type": "READ_ONLY_JAEGER_V3_QUERY",
        "exported_lineage_observed": True,
        "observed_services": services,
        "observed_spans": len(observed),
        "parent_edges": parents,
        "cross_trace_links": outside_links,
        # A trace export is NOT proof of native IAM/CP authority or ERP effect.
        "native_source_attested": False,
        "consumer_business_effect_qualified": False,
        "l4_ops_01": "BLOCKED",
        "protected_acceptance": False,
        "production_authorized": False,
    }


    if origin is not None:
        report["native_buyer_trace"] = verify_native_buyer(observed, trace_id, origin)
    return report


def verify_native_buyer(observed, trace_id, receipt):
    """Join independent Trade SQL identity to actual exported spans."""
    origin = receipt.get("business_origin", {})
    insist(receipt.get("schema") == "baobab.trade.dev11.native-origin.v1"
           and receipt.get("classification") == "SOURCE_SQL_READBACK_ONLY"
           and receipt.get("reason") == "NATIVE_ORIGIN_SQL_CONFIRMED"
           and all(receipt.get(key) is True for key in (
               "native_origin_qualified", "native_order_readback", "enforced_b2b_commit",
               "exact_commit_transaction", "spend_commit_same_transaction")),
           "NATIVE_SQL_ORIGIN_NOT_QUALIFIED")
    event = origin.get("event_id", "")
    anchor = re.fullmatch(r"00-([0-9a-f]{32})-([0-9a-f]{16})-01", origin.get("traceparent", ""))
    insist(anchor and anchor[1] == trace_id
           and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,199}", event)
           and re.fullmatch(r"[0-9]{1,10}", origin.get("transaction_id", ""))
           and re.fullmatch(r"[a-f0-9]{64}", origin.get("persisted_envelope_digest", "")),
           "NATIVE_SQL_ORIGIN_IDENTITY_INVALID")

    def attribute(sid, key):
        entries = [a["value"] for a in observed[sid]["span"].get("attributes", [])
                   if a.get("key") == key]
        return next(iter(entries[0].values()), None) if len(entries) == 1 else None

    def select(service, name, key=None, value=None):
        return [sid for sid, row in observed.items()
                if row["service"] == service and row["span"].get("name") == name
                and (key is None or attribute(sid, key) == value)
                and row["span"].get("status", {}).get("code") not in (2, "STATUS_CODE_ERROR")]

    def ancestors(sid):
        chain = set()
        while sid:
            chain.add(sid)
            sid = observed[sid]["parent"]
        return chain

    def linked(sid, predecessor):
        return any(identifier(link.get("traceId"), 16) == trace_id
                   and identifier(link.get("spanId"), 8) == predecessor
                   for link in observed[sid]["links"])

    root = [sid for sid in select("zuribeans-bff", "baobab.zuribeans.bff.request",
                                  "baobab.route", "buyer-commit") if not observed[sid]["parent"]
            and attribute(sid, "http.response.status_class") == "2xx"]
    outbox = select("baobab-trade", "baobab.trade.outbox.insert", "messaging.message.id", event)
    insist(len(root) == 1 and outbox == [anchor[2]] and root[0] in ancestors(anchor[2]),
           "NATIVE_BUYER_ROOT_OR_OUTBOX_NOT_OBSERVED")
    trade_http = select("baobab-trade", "baobab.trade.http")
    insist(any(sid in ancestors(anchor[2]) and root[0] in ancestors(sid)
               for sid in trade_http), "NATIVE_BUYER_TRADE_HTTP_NOT_OBSERVED")
    principal = select("baobab-cp", "baobab.cp.buyer.principal.resolve")
    issuer = select("baobab-cp", "baobab.cp.trade.price-issuer.resolve")
    seller = select("baobab-cp", "baobab.cp.trade.order-authority.resolve")
    introspection = select("baobab-cp", "baobab.cp.iam.introspect")
    insist(all(any(root[0] in ancestors(sid) for sid in stage)
               for stage in (principal, issuer, seller)),
           "NATIVE_BUYER_CP_AUTHORITY_NOT_OBSERVED")
    insist(any(row["service"] == "baobab-iam"
               and row["span"].get("kind") in (2, "SPAN_KIND_SERVER")
               and row["span"].get("status", {}).get("code") not in (2, "STATUS_CODE_ERROR")
               and row["parent"] in introspection
               and any(cp in ancestors(row["parent"]) for cp in principal)
               and root[0] in ancestors(sid)
               for sid, row in observed.items()),
           "NATIVE_BUYER_IAM_INTROSPECTION_NOT_OBSERVED")

    publisher = select("baobab-trade-rabbit-publisher", "baobab.trade.rabbit.publish",
                       "messaging.message.id", event)
    admit = select("baobab-erp", "baobab.erp.inbox.admit", "messaging.message.id", event)
    worker = select("baobab-erp", "baobab.erp.inbox.execute", "messaging.message.id", event)
    native = select("baobab-erp", "baobab.erp.jvm.create") + select("baobab-erp", "baobab.erp.jvm.lookup")
    insist(any(linked(sid, anchor[2]) and attribute(sid, "baobab.outbox.result") == "PUBLISHED"
               for sid in publisher)
           and any(linked(sid, anchor[2]) and attribute(sid, "baobab.erp.event_outcome") == "ADMITTED"
                   for sid in admit)
           and any(linked(sid, anchor[2]) and attribute(sid, "baobab.erp.event_outcome") == "BUSINESS_PROCESSED"
                   and any(sid in ancestors(call) for call in native) for sid in worker),
           "NATIVE_BUYER_ASYNC_EVENT_PATH_NOT_OBSERVED")
    return {"event_id": event, "transaction_id": origin["transaction_id"],
            "persisted_envelope_digest": origin["persisted_envelope_digest"],
            "same_event_exported_path_observed": True}


def query(base_url, trace_id):
    insist(base_url in ("http://jaeger:16686", "http://127.0.0.1:16686"),
           "QUERY_ENDPOINT_NOT_ALLOWLISTED")
    request = urllib.request.Request(
        base_url + "/api/v3/traces/" + trace_id,
        headers={"Accept": "application/json", "User-Agent": "baobab-dev11-auditor"})
    with urllib.request.urlopen(request, timeout=10) as response:
        insist(response.status == 200, "QUERY_NOT_AVAILABLE")
        body = response.read(MAX_BYTES + 1)
    insist(len(body) <= MAX_BYTES, "TRACE_RESPONSE_TOO_LARGE")
    return json.loads(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--jaeger", default="http://jaeger:16686")
    parser.add_argument("--service", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--native-origin", type=Path)
    args = parser.parse_args()
    try:
        insist(bool(TRACE_ID.fullmatch(args.trace_id)) and args.trace_id != "0" * 32,
               "TRACE_ID_INVALID")
        insist(1 <= len(args.service) <= 12 and len(set(args.service)) == len(args.service)
               and all(SERVICE.fullmatch(s) for s in args.service),
               "SERVICE_REQUIREMENTS_INVALID")
        origin = None
        if args.native_origin:
            with args.native_origin.open("rb") as stream:
                payload = stream.read(8193)
            insist(len(payload) <= 8192, "NATIVE_SQL_ORIGIN_TOO_LARGE")
            origin = json.loads(payload)
            insist(type(origin) is dict, "NATIVE_SQL_ORIGIN_IDENTITY_INVALID")
        report = project(query(args.jaeger, args.trace_id), args.trace_id, args.service, origin)
        success = True
    except (TraceNotVerified, TimeoutError, OSError, urllib.error.URLError, ValueError,
            TypeError, KeyError, AttributeError) as error:
        cause = str(error) if isinstance(error, TraceNotVerified) else "QUERY_UNAVAILABLE"
        report = {
            "schema": "infrastructure.dev11.exported-observation.v1",
            "type": "READ_ONLY_JAEGER_V3_QUERY",
            "exported_lineage_observed": False,
            "reason": cause,
            "native_source_attested": False,
            "consumer_business_effect_qualified": False,
            "l4_ops_01": "BLOCKED",
            "protected_acceptance": False,
            "production_authorized": False,
        }
        success = False
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("DEV11_EXPORTED_LINEAGE=" + ("PASS" if success else "BLOCKED"))
    return 0 if success else 2


if __name__ == "__main__":
    sys.exit(main())
