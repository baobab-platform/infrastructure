# DEV-11 connected exporter and broker qualification — evidence custody

**Scope:** disposable development-only native telemetry and messaging.
**Authority:** ADR-Infra-0012 and ADR-Infra-0016; accepted EA v2.3 DEV-11.
**Status:** Implementation candidate, not passing runtime evidence.
Protected staging/production selection remains OFF. No automatic PR merge.

## Reuse existing observability infrastructure

`compose/otel/collector.yaml` intentionally remains the baseline debug-only
collector. `compose/otel/dev11-collector.yaml` is the explicit development
qualification profile: OTLP gRPC 4317 / HTTP 4318 → memory limiter → batch →
`otlphttp/jaeger` exporter. The opt-in `jaeger` Compose service is on the
existing private observability network with no published host query port.
Real SDK exporter failures never confer authority or alter the Trade/ERP
commit outcome.

`.github/workflows/dev11-otel-runtime.yml` uses official Python OTel SDK
to emit an actual two-span trace, then a **separate process** calls the Jaeger
v3 query API and checks actual decoded span IDs, parent edges, service
identity and no missing parents/cycles. It uploads only bounded numeric
observations; the private trace ID is deleted on teardown. This smoke
certifies the **exporter path only** (service
`dev11-telemetry-probe`), not any Baobab business effect.

## Separate real Trade/RabbitMQ/ERP profile

Trade #188's workflow `.github/workflows/dev11-rabbit-connected.yml`
reuses this repository's exact SHA-pinned
`tests/platform-integration/development/dev11_exported_trace.py` reader,
and `compose/otel/dev11-collector.yaml` as its immutable collector config.
It runs disposable real Trade native Medusa/PG17, RabbitMQ 4.3, ERP
application/PG17, and private Jaeger. Actual OTel spans originate from
a recorded Medusa source operation, the RabbitMQ publisher and a separately
running ERP consumer. All three services must be present in the
independently queried trace, not merely in a synthetic source JSON.

A test-only ERP process dies **after durable inbox commit and before broker
ACK**; a fresh production-path ERP consumer recovers RabbitMQ redelivery.
The independent broker-management probe must observe real ACK counters,
and ERP PG must contain one immutable receipt. Changed canonical payload and
forged HMAC messages must be rejected into the DLQ; mandatory unroutable
publishes must not be counted as published delivery.

The joined candidate manifests must contain the exact current
Infrastructure #72, Trade #188, ERP #125, CP, ZuriBeans, Nabhold and Thamani
source SHAs and GitHub run IDs. The independent
`dev11_evidence_join.py` rejects stale companion PR heads, missing
subscriber proof, unsigned/unverified zipped artifacts, skipped/failed
Playwright/a11y/visual/performance steps, and missing teardown.

## Explicit exclusions from acceptance

The present Trade connected test uses a *synthetic native Medusa outbox
event*, not an IAM/CP-qualified buyer commitment. Its ERP result is a
**durable inbox admission**, not an iDempiere sale/GL posting.
The production-path ERP inbox executor already supports CP-provided authority
per claim, native mapping and `POReference` reconciliation, but current
protected-authority iDempiere 13 real-effect and uncertain-outcome evidence
is still missing. The initial Keycloak/CP and BFF/Trade connected profiles
are also distinct from this exporter/broker component.

Therefore even a complete seven-run join MUST retain:
`l4_ops_01=BLOCKED`, `production_authorized=false` and
`protected_acceptance=false`. Do not generalize the exported broker
component's source-based trust to a full authenticated business vertical.

**Next acceptance-critical work:** run current-head workflows, correct
their real failures, configure real CP legal-actor authority in the ERP native
execution worker, provide running iDempiere 13 with a genuine authorised order,
prove broker/engine crash/replay and native financial consequence read-back,
then independently join those original traces and database receipts with
the estate-owned quality CI results.
