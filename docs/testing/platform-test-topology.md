# Platform test topology

Maps Baobab engines to the local dependency services provided by this
repository’s Compose stack. Use this when writing L2 dependency-integration
tests or L3 platform smoke flows.

## Local services (source of truth: `compose/compose.yaml`)

| Service | Role | Published (loopback) | Internal networks |
| --- | --- | --- | --- |
| etcd | APISIX config store | none | control |
| apisix | Edge / admin API | 9080, 9180 | edge, control, observability |
| postgresql | Control-plane and approved tenant DB boundaries | 5432 | data |
| rabbitmq | Commands and lifecycle events | 5672, 15672 | data |
| redis | Rebuildable projections | 6379 | data |
| otel-collector | Telemetry pipeline | 4317, 4318, 13133 | observability |

All published ports bind to `127.0.0.1` only. See the
[local platform runbook](../runbooks/local-platform.md).

## Engine → dependency matrix (local)

| Engine | Postgres | RabbitMQ | Redis | APISIX | Notes |
| --- | --- | --- | --- | --- | --- |
| baobab-cp | required | required | optional | consumer | Context, tenant, entitlements; primary Compose consumer today |
| baobab-iam | required | optional | optional | via gateway | Authn; may use own local Keycloak/Ory stack in parallel |
| baobab-trade | engine-owned or shared | required (outbox/events) | optional | via gateway | Medusa fulfillment; events into shared bus |
| baobab-erp | engine-owned (iDempiere) | events | — | via gateway | Inventory/shipment SoR; no shared DB with Trade |
| baobab-cms | engine-owned | optional | — | via gateway | Payload; document *templates* only |
| baobab-pulse | required (evidence) | consumer | optional | — | Intelligence; not SoR for ops state |
| baobab-regulations | required | consumer | — | — | PDP; decisions only |
| baobab-payments | required | events | optional | via gateway | Orchestration; settlement via external rails |
| baobab-subscriptions | required | events | optional | via gateway | Billing/entitlements metering |
| baobab-tms | required | events | optional | via gateway | Logistics orchestration (thin) |
| baobab-trade-docs | required | events | — | via gateway | Executable document instances |
| baobab-scf | required | events | optional | via gateway | Trade/SCF instruments |

“Engine-owned” means the engine may run its own database for its system of
record; it must not share tables with another engine. Cross-engine facts move
by API or versioned events from `shared`.

## Network expectations for L2 tests

- Prefer attaching test runners to the Compose networks (`data`, `control`)
  rather than only host-published ports when testing service-to-service paths.
- APISIX Admin remains on the control network and loopback; do not expose it
  broadly in CI.
- Health endpoints used by `scripts/verify-local.sh` are the minimum bar before
  any engine L2 suite starts.

## Critical-path flows (L3 candidates)

1. **Context fail-closed** — CP context resolve without valid tenant/capability fails closed.
2. **Workload identity** — IAM client credentials → CP accepts context for a known workload.
3. **Event spine** — Synthetic Trade (or fixture) lifecycle event published to RabbitMQ and consumable under the shared vhost.
4. **Regulations decision** — Fixture facts → PDP outcome (allow / hold / deny) without mutating other engines’ SoR.
5. **Gateway reachability** — Public-facing route through APISIX reaches a health or ready endpoint of a published engine image (when images exist).

Exact scripts and image pins for L3 belong in a later change under
`tests/platform/` (or a dedicated private harness repo).
