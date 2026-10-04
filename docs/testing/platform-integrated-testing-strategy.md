# Platform integrated testing strategy

- **Status:** Accepted for implementation (Phase A landed in this change)
- **Owner:** Platform / infrastructure
- **Related:** ADR-Infra-0001, ADR-Infra-0020, ADR-Infra-0021, ADR-Infra-0022
- **Date:** 2026-10-04

## Purpose

Prove that Baobab’s multi-engine system works together under a realistic local
(and later staging) topology, while preserving engine ownership boundaries,
event/contract contracts from `shared`, and the existing Foundation evidence
culture.

This repository owns the **local dependency topology** and the **L2/L3
infrastructure side** of integrated testing. Application engines own their L0
unit tests and L2 consumer-side integration tests against this topology.

## Testing layers

| Layer | Name | Owner | Scope | Cadence | Evidence |
| --- | --- | --- | --- | --- | --- |
| L0 | Unit / component | Each engine repo | Pure logic, adapters with fakes | Every PR | Unit reports |
| L1 | Contract | `shared` + consumers | Schema / event / API contracts | PR + main | Contract results + lock drift |
| L2 | Dependency integration | Engine + this repo | Engine against real Postgres / RabbitMQ / Redis / APISIX from Compose | PR (optional) / nightly | Pass/fail + logs |
| L3 | Platform smoke / critical path | This repo (+ thin harness) | Minimal multi-engine flows | Nightly / release | Structured evidence pack |
| L4 | Staging / design-partner | Ops + selected engines | Full topology, near-real corridors | Gated / manual | Runbooks + signed evidence |

## Design principles

1. **No shared databases between engines.** Integration tests use APIs and events only.
2. **Control plane owns context.** Multi-engine flows start from a resolved (or deliberately unresolved) CP context.
3. **Regulations is the PDP.** Tests assert decisions; other engines remain PEPs or fact providers.
4. **Local-first.** Developers and CI use the same Compose topology from this repository.
5. **Thin new engines** (`baobab-tms`, `baobab-trade-docs`, `baobab-scf`) inherit L0–L2 from day one.
6. **Evidence over green checkmarks.** Failures must produce diagnosable artifacts consistent with Foundation gates.

## Phase plan

### Phase A — Foundations (this change)

- Document this strategy and the platform test topology.
- Expand Infrastructure CI from `compose config` only to **up + smoke** against the local stack.
- Provide a CI-safe path to generate `compose/.env` without committing secrets.
- Keep Terraform / Kubernetes deferred; Compose remains the integration base.

### Phase B — Contract spine

- Treat `shared` contracts as the integration surface.
- Every engine that emits or consumes events or calls CP/IAM must validate against locked schemas.
- Fail on contract lock drift (pattern already used in `baobab-cp`).

### Phase C — Per-engine dependency integration (L2)

- Each engine offers `make test-integration` (or equivalent CI job).
- Prefer joining the shared Compose network from this repo over ad-hoc testcontainers where networking and APISIX behaviour matter.
- Start with `baobab-cp` and `baobab-iam` (critical path for all others).

### Phase D — Platform critical-path smoke (L3)

- Thin harness (this repo under `tests/platform/` or a dedicated private test repo) that:
  1. Brings up infrastructure Compose.
  2. Starts minimal CP + IAM (later Trade) via overlays or published images.
  3. Runs a small set of scripted flows (context resolve fail-closed, workload credentials → context, synthetic Trade event on RabbitMQ, Regulations fixture decision).
  4. Emits a machine-readable evidence artifact.
- Run on schedule and release tags, not every PR.

### Phase E — Governance and promotion

- Align with ADR-Infra-0020/0021/0022: infrastructure and application promotions stay separate; tests gate each.
- Required checks: Foundation + contract + unit on engine PRs; platform smoke on main/release.
- Preserve evidence packs for auditability.

## What this repository will and will not own

**Owns**

- Local Compose topology and its health/smoke verification.
- Documentation of which services each engine is expected to use locally.
- CI jobs that prove the dependency stack starts and answers health checks.
- Optional future L3 harness that only orchestrates published engine images + this topology.

**Does not own**

- Engine unit tests or business-logic integration tests.
- Canonical API/event schemas (those live in `shared`).
- Production cluster or Terraform apply in application CI.
- Tenant or digital-estate end-to-end UI tests.

## Near-term backlog

1. Land Phase A (this PR).
2. Contract test + lock enforcement on highest-traffic boundaries (CP context, identity events, Trade outbox).
3. CP + IAM L2 tests against this Compose stack.
4. First L3 critical-path smoke (CP ↔ IAM ↔ RabbitMQ).
5. Encode the same hooks in `engine-template` so new engines start correctly.

## References

- [Local platform runbook](../runbooks/local-platform.md)
- [Platform test topology](./platform-test-topology.md)
- ADR-Infra-0001 (environment provisioner boundary)
- ADR-Infra-0020 (CI/CD infrastructure change governance)
