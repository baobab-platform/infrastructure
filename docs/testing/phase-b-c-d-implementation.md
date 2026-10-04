# Phase B–D implementation guide

Companion to [platform-integrated-testing-strategy.md](./platform-integrated-testing-strategy.md).

**Date:** 2026-10-04

## Phase B — Contract spine (status: largely present in `shared`)

The contract spine is **not invented here**. It already lives in
`baobab-platform/shared`:

| Mechanism | Location | Role |
| --- | --- | --- |
| Canonical schemas / AsyncAPI / policies | `shared/contracts/**` | Source of truth |
| Producer validators | `shared/scripts/validate-*.py` / `validate-*.rb` | Schema + example conformance |
| Consumer lock schema | `shared/.baobab/contract-consumer-lock.schema.json` | EA-01 lock shape |
| Consumer lock check / drift | `shared/scripts/contract_lock.py` | Pin validity, incompatible drift |
| Engine locks | `baobab-cp/contracts.lock.yaml`, `baobab-iam/contracts.lock.yaml`, … | Explicit consumption |
| Foundation gates | `shared/.github/workflows/foundation-*.yml` | Org-wide enforcement |

### What Phase B adds operationally

1. **Treat highest-traffic boundaries as required consumer locks**
   - CP context / control-plane contracts (already extensive in CP lock)
   - Identity + identity-events (IAM)
   - Trade outbox / capability events (when Trade publishes)
2. **Run consumer lock check before merging engine PRs** that change types
   derived from Shared:
   ```bash
   python3 ../shared/scripts/contract_lock.py check \
     --repository-root . \
     --shared-repo ../shared \
     --mode enforce
   ```
3. **Drift is informational, not a hard fail** (`contract_lock.py drift`) until
   the consumer deliberately re-pins via PR.

Infrastructure does not host canonical contracts. It only documents the spine
and provides the dependency topology engines test against.

## Phase C — CP / IAM L2 against this topology

### Control plane (`baobab-cp`)

Already wired:

```bash
make dev-up-infra
make dev-env-infra
make test-integration
```

### IAM (`baobab-iam`)

Already wired:

```bash
make integration-test
```

### Engine template

New engines should inherit L2/L3 expectations from `engine-template`.
Infrastructure L3-07 validates the template still exposes those hooks:
see [../../tests/platform/engine-template-hooks.md](../../tests/platform/engine-template-hooks.md).

```bash
make platform-l3-engine-template
# or
ENGINE_TEMPLATE_DIR=../engine-template make platform-l3
```

## Phase D — L3 multi-engine harness

Location: `tests/platform/`

### Critical-path checks

| ID | Check |
| --- | --- |
| L3-01 | Compose stack healthy (verify-local) |
| L3-02 | RabbitMQ management ready |
| L3-03 | Postgres readiness |
| L3-04 | Optional CP if `PLATFORM_CP_URL` set |
| L3-05 | Optional IAM OIDC if `PLATFORM_IAM_URL` set |
| L3-07 | Engine-template L2/L3 hooks |
| L3-06 | Evidence JSON |

### Cadence

Minute-aware: main / schedule / workflow_dispatch — not every PR.
