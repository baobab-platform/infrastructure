# Platform integrated testing strategy

- **Status:** Phase A–D implemented on `main`; Phase E matrix drafted; L4 staging foundation is the next infrastructure increment
- **Owner:** Platform / infrastructure
- **Related:** ADR-Infra-0001, ADR-Infra-0020, ADR-Infra-0021, ADR-Infra-0022
- **Date:** 2026-10-04

## Purpose

Prove that Baobab’s multi-engine system works together under a realistic local
(and later staging) topology, while preserving engine ownership boundaries,
contracts from `shared`, and Foundation evidence culture.

## Testing layers

| Layer | Name | Owner | Cadence |
| --- | --- | --- | --- |
| L0 | Unit | Each engine | Every PR |
| L1 | Contract | `shared` + consumers | PR + main |
| L2 | Dependency integration | Engine + this repo | PR optional / nightly |
| L3 | Platform critical path | This repo | Nightly / release / dispatch |
| L4 | Staging | Ops + engines | Gated / manual |

## Design principles

1. No shared databases between engines.
2. Control plane owns context.
3. Regulations is the PDP.
4. Local-first Compose topology.
5. Thin new engines inherit L0–L2 from day one.
6. Evidence over green checkmarks.

## CI minute policy

- **Every PR:** Compose model validation only.
- **Full smoke + L3:** main, schedule, `workflow_dispatch`.

## Phase status

| Phase | Status |
| --- | --- |
| A Foundations | Implemented; Phase A reconciliation included in this corrective change |
| B Contract spine | Documented; enforce on engines ongoing |
| C CP/IAM L2 | Present in engines; topology documented |
| D L3 harness | Implemented on `main`; v0.3.0 includes L3-08..10 |
| E Governance | [required-checks-matrix.md](./required-checks-matrix.md) |
| L4 Staging | MP2-C production-shaped AWS staging foundation next |

## References

- [Phase B–D implementation](./phase-b-c-d-implementation.md)
- [Required checks matrix](./required-checks-matrix.md)
- [Platform test topology](./platform-test-topology.md)
- [Local platform runbook](../runbooks/local-platform.md)
