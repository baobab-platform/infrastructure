"""Fail-closed correlation of confidential BFF checkout with an independent Trade SQL read.

The native read is produced by a separate ephemeral Python/psycopg process,
using Trade's reviewed dev11_native_business_origin SQL against PostgreSQL.
This module neither authorises a buyer nor converts SQL evidence to DEV-07,
DEV-11, ERP, or protected-environment acceptance.
"""
from __future__ import annotations

import re

_ORDER = re.compile(r"order_[A-Za-z0-9_-]{6,128}\Z")
_KEY = re.compile(r"[A-Za-z0-9._:-]{16,128}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z", re.I)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_HEAD = re.compile(r"[0-9a-f]{40}\Z")
_XID = re.compile(r"[0-9]{1,10}\Z")
_TRACE = re.compile(r"00-(?!0{32})[0-9a-f]{32}-(?!0{16})[0-9a-f]{16}-0[01]\Z")


class CheckoutWitnessRefused(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise CheckoutWitnessRefused(code)


def verify_checkout(bff: object, origin: object, *, trade_sha: str,
                    image_id: str, run_id: str) -> dict[str, object]:
    """Only source-backed facts, requiring one original outbox and one native XID."""
    require(isinstance(bff, dict) and set(bff) == {
        "order_id", "idempotency_key", "traceparent", "csrf_refused",
        "same_order_replayed", "native_sql_readback_observed",
    }, "DEV07_BFF_ORIGINAL_OBSERVATION_INVALID")
    require(isinstance(origin, dict), "DEV07_INDEPENDENT_SQL_RESULT_ABSENT")
    require(isinstance(run_id, str) and bool(re.fullmatch(r"[0-9a-f]{32}", run_id))
            and isinstance(trade_sha, str) and _HEAD.fullmatch(trade_sha) is not None
            and isinstance(image_id, str) and image_id.startswith("sha256:")
            and _SHA.fullmatch(image_id[7:]) is not None,
            "DEV07_WITNESS_SOURCE_CUSTODY_INVALID")
    order = bff["order_id"]
    idem = bff["idempotency_key"]
    carrier = bff["traceparent"]
    require(isinstance(order, str) and _ORDER.fullmatch(order) is not None
            and isinstance(idem, str) and _KEY.fullmatch(idem) is not None
            and isinstance(carrier, str) and _TRACE.fullmatch(carrier) is not None
            and bff["csrf_refused"] is True
            and bff["same_order_replayed"] is True
            and bff["native_sql_readback_observed"] is False,
            "DEV07_BFF_COMMIT_AND_REPLAY_NOT_OBSERVED")
    require(origin.get("schema") == "baobab.trade.dev11.native-origin.v1"
            and origin.get("classification") == "SOURCE_SQL_READBACK_ONLY"
            and origin.get("native_origin_qualified") is True
            and origin.get("reason") == "NATIVE_ORIGIN_SQL_CONFIRMED"
            and origin.get("native_order_readback") is True
            and origin.get("enforced_b2b_commit") is True
            and origin.get("exact_commit_transaction") is True
            and origin.get("spend_commit_same_transaction") is True
            and origin.get("current_iam_cp_authority_qualified") is False
            and origin.get("native_erp_business_effect_qualified") is False
            and origin.get("l4_ops_01") == "BLOCKED"
            and origin.get("production_authorized") is False,
            "DEV07_INDEPENDENT_NATIVE_SQL_NOT_QUALIFIED")
    fact = origin.get("business_origin")
    require(isinstance(fact, dict) and set(fact) == {
        "event_id", "order_id", "transaction_id", "persisted_envelope_digest",
        "traceparent",
    }, "DEV07_ORIGINAL_EVENT_PROVENANCE_MISSING")
    trace = fact["traceparent"]
    xid = fact["transaction_id"]
    require(fact["order_id"] == order
            and isinstance(fact["event_id"], str)
            and _UUID.fullmatch(fact["event_id"]) is not None
            and isinstance(xid, str) and _XID.fullmatch(xid) is not None
            and isinstance(fact["persisted_envelope_digest"], str)
            and _SHA.fullmatch(fact["persisted_envelope_digest"]) is not None
            and isinstance(trace, str) and _TRACE.fullmatch(trace) is not None
            and carrier.split("-")[1] == trace.split("-")[1],
            "DEV07_BFF_AND_ORIGINAL_EVENT_NOT_CAUSALLY_BOUND")
    return {
        "schema": "infrastructure.dev07.checkout-native-witness.v1",
        "run_id": run_id,
        "trade_source_sha": trade_sha,
        "observer_image_id": image_id,
        "order_id": order,
        "original_event_id": fact["event_id"],
        "native_transaction_id": xid,
        "original_envelope_digest": fact["persisted_envelope_digest"],
        "trace_id": trace.split("-")[1],
        "csrf_denied": True,
        "idempotent_replay_same_order": True,
        "native_order_seller_buyer_spend_outbox_same_xid": True,
        "evidence_class": "INDEPENDENT_DISPOSABLE_POSTGRES_SQL",
        "current_iam_cp_authority_independently_qualified": False,
        "erp_effect_qualified": False,
        "dev07_accepted": False,
        "l4_ops_01": "BLOCKED",
        "protected_acceptance": False,
        "production_authorized": False,
    }
