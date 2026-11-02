"""DEV-11 closed DAG and asynchronous trace-link source verifier.

This validates deliberately minimised run-owned projections, never raw spans.
It cannot independently attest execution, authority, or teardown.
"""
from __future__ import annotations

from dev11_assurance import (
    CASE, CAUSES, PROFILES, SHA, UUID, Refused, closed, require, traceparent,
)

VERSION = "infrastructure.dev11.graph.v1"
ROLES = frozenset(("bff", "issuer", "cp", "engine", "outbox", "consumer"))
REQUIRED_ROLES = frozenset(("bff", "issuer", "cp", "engine", "outbox"))
RESULTS = frozenset(("PASS", "FAIL", "BLOCKED", "NOT_RUN"))
SPAN_REF_KEYS = {"trace_id", "span_id"}
HEX32 = __import__("re").compile(r"[0-9a-f]{32}\\Z")
HEX16 = __import__("re").compile(r"[0-9a-f]{16}\\Z")


def ref(obj):
    item = closed(obj, SPAN_REF_KEYS)
    require(isinstance(item["trace_id"], str) and HEX32.fullmatch(item["trace_id"]) is not None)
    require(isinstance(item["span_id"], str) and HEX16.fullmatch(item["span_id"]) is not None)
    require(int(item["trace_id"], 16) != 0 and int(item["span_id"], 16) != 0)
    return (item["trace_id"], item["span_id"])


def verify_graph(obj):
    """Verify graph closure, event causation and privacy-safe result vocabulary."""
    doc = closed(obj, {
        "schema", "source_sha", "profile", "scenario", "correlation_id",
        "spans", "runtime_observed", "teardown_verified", "evidence_class",
    })
    require(doc["schema"] == VERSION)
    require(isinstance(doc["source_sha"], str) and SHA.fullmatch(doc["source_sha"]) is not None)
    require(isinstance(doc["profile"], str) and doc["profile"] in PROFILES)
    require(isinstance(doc["scenario"], str) and CASE.fullmatch(doc["scenario"]) is not None)
    require(isinstance(doc["correlation_id"], str)
            and UUID.fullmatch(doc["correlation_id"]) is not None)
    require(type(doc["runtime_observed"]) is bool and type(doc["teardown_verified"]) is bool)
    require(doc["evidence_class"] in ("SOURCE", "REAL_COMPONENT_SYNTHETIC_DATA"))
    spans = doc["spans"]
    require(isinstance(spans, list) and 5 <= len(spans) <= 64)
    indexed, edges, outcomes, causes, roles, metadata = {}, {}, [], set(), set(), {}
    for item in spans:
        row = closed(item, {
            "service_role", "traceparent", "parent", "links", "correlation_id",
            "boundary", "event_id", "result", "cause",
        })
        require(isinstance(row["service_role"], str) and row["service_role"] in ROLES)
        require(row["correlation_id"] == doc["correlation_id"])
        ident = traceparent(row["traceparent"])
        require(ident not in indexed)
        indexed[ident] = row
        roles.add(row["service_role"])
        require(isinstance(row["links"], list) and len(row["links"]) <= 8)
        links = [ref(x) for x in row["links"]]
        require(len(set(links)) == len(links))
        parent = None if row["parent"] is None else ref(row["parent"])
        if parent is not None:
            require(parent[0] == ident[0])  # W3C parent is same-trace; links may cross traces.
        require(ident != parent and ident not in links)
        edges[ident] = ([parent] if parent is not None else []) + links
        boundary = row["boundary"]
        require(boundary in ("HTTP", "EVENT_PUBLISH", "EVENT_CONSUME"))
        if boundary == "EVENT_PUBLISH":
            require(row["service_role"] == "outbox")
        if boundary == "EVENT_CONSUME":
            require(row["service_role"] == "consumer" and len(links) > 0)
        if boundary == "HTTP":
            require(row["event_id"] is None)
        else:
            require(isinstance(row["event_id"], str)
                    and UUID.fullmatch(row["event_id"]) is not None)
        metadata[ident] = (boundary, row["event_id"])
        require(row["result"] in RESULTS and row["cause"] in CAUSES)
        require((row["result"] == "PASS") == (row["cause"] == "NONE"))
        outcomes.append(row["result"])
        if row["cause"] != "NONE":
            causes.add(row["cause"])

    require(REQUIRED_ROLES <= roles)
    roots = [k for k, v in edges.items() if not v]
    require(len(roots) == 1 and indexed[roots[0]]["service_role"] == "bff")
    visited, active = set(), set()

    def walk(key):
        require(key in indexed)
        require(key not in active)  # cycles, including cycles made solely by async links
        if key in visited:
            return
        active.add(key)
        for predecessor in edges[key]:
            walk(predecessor)
        active.remove(key)
        visited.add(key)

    for key in indexed:
        walk(key)
    require(len(visited) == len(indexed))
    # Every span must be causally anchored at the BFF root.
    def ancestors(key):
        if key == roots[0]:
            return True
        return any(ancestors(parent) for parent in edges[key])

    require(all(ancestors(k) for k in indexed))
    for key, (boundary, event_id) in metadata.items():
        if boundary == "EVENT_CONSUME":
            require(any(metadata[link] == ("EVENT_PUBLISH", event_id)
                        for link in edges[key] if link in metadata
                        and link in edges[key][len(edges[key]) - len(indexed[key]["links"]):]))

    aggregate = ("FAIL" if "FAIL" in outcomes else
                 "BLOCKED" if "BLOCKED" in outcomes else
                 "NOT_RUN" if "NOT_RUN" in outcomes else "PASS")
    return {
        "schema": VERSION, "source_sha": doc["source_sha"],
        "profile": doc["profile"], "scenario": doc["scenario"],
        "result": aggregate, "trace_graph_valid": True,
        "span_count": len(spans), "cause_codes": sorted(causes),
        "runtime_observed": doc["runtime_observed"],
        "teardown_verified": doc["teardown_verified"],
        "runtime_qualified": False, "protected_acceptance": False,
        "production_authorized": False,
    }
