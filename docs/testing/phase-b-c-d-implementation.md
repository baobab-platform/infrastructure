# Phase B–D implementation guide

Companion to [platform-integrated-testing-strategy.md](./platform-integrated-testing-strategy.md).

**Date:** 2026-10-04

## Phase B — Contract spine (status: largely present in `shared`)

The contract spine lives in `baobab-platform/shared`:

| Mechanism | Location |
| --- | --- |
| Canonical schemas | `shared/contracts/**` |
| Consumer lock check | `shared/scripts/contract_lock.py` |
| Engine locks | `baobab-cp`, `baobab-iam`, … `contracts.lock.yaml` |

Operational rule: enforce lock on engine PRs that consume Shared; re-pin via explicit PR.

```bash
python3 ../shared/scripts/contract_lock.py check \
  --repository-root . --shared-repo ../shared --mode enforce
```

## Phase C — CP / IAM L2

```bash
# baobab-cp
make dev-up-infra && make test-integration

# baobab-iam
make integration-test
```

Prefer infrastructure Compose over a second dependency stack. See engine-template
`docs/testing/platform-l2-l3.md` once merged.

## Phase D — L3 multi-engine harness

Location: `tests/platform/` · version **0.3.0**

| ID | Check |
| --- | --- |
| L3-01 | verify-local smoke |
| L3-02 | RabbitMQ ready |
| L3-03 | PostgreSQL ready |
| L3-04 | Optional CP |
| L3-05 | Optional IAM OIDC |
| L3-06 | Engine-template hooks |
| L3-08 | RabbitMQ publish/get fixture |
| L3-09 | Optional Regulations |
| L3-10 | APISIX admin |
| L3-11 | Evidence pack |

Cadence: main / schedule / workflow_dispatch — not every PR.

## Phase E — Governance

See [required-checks-matrix.md](./required-checks-matrix.md).
