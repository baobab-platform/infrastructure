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
   # From an engine checkout, with sibling shared clone:
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
# Sibling clone of this repo as ../infrastructure
make dev-up-infra          # Postgres + RabbitMQ from infrastructure Compose
make dev-env-infra         # print DATABASE_URL / RABBITMQ_URL for .env
make test-integration      # go test with TEST_DATABASE_URL + SHARED_CONTRACTS_DIR
```

Expectations for L2:

- Prefer `dev-up-infra` over CP’s standalone `docker-compose.yml` when proving
  behaviour against the **platform** dependency stack.
- Fail closed on missing context / invalid tenant fixtures.
- Do not require APISIX for pure store/API unit paths; include gateway only
  when testing edge-facing routes.

### IAM (`baobab-iam`)

Already wired:

```bash
make integration-test      # tests/integration/run.sh against bootstrapped stack
# Ory path: tests/ory-foundation/run.sh (provider-neutral migration)
```

L2 additions relative to infrastructure:

- IAM may keep its own Keycloak/Ory compose for provider fidelity.
- For **platform bus** tests (events to RabbitMQ vhost `nabhold`), attach to
  infrastructure’s RabbitMQ rather than inventing a second broker.
- Workload client-credentials → token claims required by CP
  (`context:resolve`, `aud=baobab-control-plane`) remain IAM’s responsibility;
  L3 only asserts the token is usable once both stacks are up.

### Checklist for engine authors

- [ ] `contracts.lock.yaml` present and valid against Shared main
- [ ] `make test` (L0) green without external deps
- [ ] `make test-integration` / `integration-test` documented and runnable
      against infrastructure Compose where Postgres/RabbitMQ are shared
- [ ] No shared database tables with other engines

## Phase D — L3 multi-engine harness (this repository)

Location: `tests/platform/`

### Goals

1. Bring up infrastructure Compose (same as local-verify).
2. Run **infra-owned** critical-path checks that do not require published
   engine images yet (bus readiness, schema presence hooks, evidence pack).
3. Provide extension points for CP/IAM/Trade once images or local binaries
   are available (`PLATFORM_CP_URL`, `PLATFORM_IAM_URL`, …).
4. Emit a machine-readable evidence pack under `tests/platform/evidence/`.

### Non-goals

- Running full engine test suites inside this repo.
- Applying Terraform or talking to AWS.
- Holding application secrets.

### Cadence (minute-aware)

Same policy as local-smoke: **main / schedule / workflow_dispatch**, not every
PR. Developers run `make platform-l3` locally.

### Critical-path checks (v0)

| ID | Check | Depends on engines? |
| --- | --- | --- |
| L3-01 | Compose stack healthy (reuse verify-local) | No |
| L3-02 | RabbitMQ management ready; default vhost reachable | No |
| L3-03 | Postgres accepts connection with compose credentials | No |
| L3-04 | Optional: CP health/ready if `PLATFORM_CP_URL` set | Yes |
| L3-05 | Optional: IAM OIDC discovery if `PLATFORM_IAM_URL` set | Yes |
| L3-06 | Write evidence JSON | No |

When CP and IAM are running against this topology, set the optional URLs to
exercise cross-engine reachability without embedding their code here.
