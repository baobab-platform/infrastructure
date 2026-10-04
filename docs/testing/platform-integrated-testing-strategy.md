# Platform integrated testing strategy

- **Status:** Phase A accepted; Phase B–D implementation guide + L3 harness landed
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
| L3 | Platform smoke / critical path | This repo (`tests/platform`) | Minimal multi-engine / infra flows | Nightly / release / dispatch | Structured evidence pack |
| L4 | Staging / design-partner | Ops + selected engines | Full topology, near-real corridors | Gated / manual | Runbooks + signed evidence |

## Design principles

1. **No shared databases between engines.** Integration tests use APIs and events only.
2. **Control plane owns context.** Multi-engine flows start from a resolved (or deliberately unresolved) CP context.
3. **Regulations is the PDP.** Tests assert decisions; other engines remain PEPs or fact providers.
4. **Local-first.** Developers and CI use the same Compose topology from this repository.
5. **Thin new engines** inherit L0–L2 from day one.
6. **Evidence over green checkmarks.** Failures must produce diagnosable artifacts consistent with Foundation gates.

## CI minute policy

- **Every PR:** Compose model validation only (cheap).
- **Full local smoke + L3:** `main`, weekly schedule, `workflow_dispatch` — not every PR.
- Local: `make local-verify` and `make platform-l3`.

## Phase status

| Phase | Status | Where |
| --- | --- | --- |
| A Foundations | Done | docs/testing, CI validate + optional smoke |
| B Contract spine | **Present in `shared`** (validators + `contract_lock.py` + consumer locks); ops guide here | [phase-b-c-d-implementation.md](./phase-b-c-d-implementation.md) |
| C CP/IAM L2 | **Present in engines** (`make test-integration`, `make integration-test`); infra topology hooks documented | same |
| D L3 harness | **Landed** | `tests/platform/`, `make platform-l3`, `.github/workflows/platform-l3.yml` |
| E Governance | Ongoing via ADR-Infra-0020+ | — |

## References

- [Local platform runbook](../runbooks/local-platform.md)
- [Platform test topology](./platform-test-topology.md)
- [Phase B–D implementation](./phase-b-c-d-implementation.md)
- ADR-Infra-0001, ADR-Infra-0020
