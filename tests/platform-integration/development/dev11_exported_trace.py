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


def project(trace, trace_id, required):
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
    return {
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
    args = parser.parse_args()
    try:
        insist(bool(TRACE_ID.fullmatch(args.trace_id)) and args.trace_id != "0" * 32,
               "TRACE_ID_INVALID")
        insist(1 <= len(args.service) <= 12 and len(set(args.service)) == len(args.service)
               and all(SERVICE.fullmatch(s) for s in args.service),
               "SERVICE_REQUIREMENTS_INVALID")
        report = project(query(args.jaeger, args.trace_id), args.trace_id, args.service)
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
    from pathlib import Path
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("DEV11_EXPORTED_LINEAGE=" + ("PASS" if success else "BLOCKED"))
    return 0 if success else 2


if __name__ == "__main__":
    sys.exit(main())
