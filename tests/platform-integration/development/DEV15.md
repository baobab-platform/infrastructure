# DEV-14/15 first-adopter source handoff

Date: 2026-10-26. Authority: Accepted EA v2.3, EA-DEV DEV-14/15, the
[Shared DEV-14 descriptor specification](https://github.com/baobab-platform/shared/blob/main/docs/architecture/ea-dev-reusable-engine-onboarding-2026-10-23.md).

## What is implemented

The DEV-14 source planner (Infrastructure #62) is merged. This second
increment checks the two real native owner repositories against the exact
Shared descriptor merge and owner capability declarations. Its
`dev15_source.py` loads an immutable reviewer-visible source lock, confirms
the checkout SHA and clean worktree, invokes Shared's canonical validator,
checks all nine ENG-ONB IDs and preserves every vendor-specific mandatory
scenario. Its result is deliberately **SOURCE_ONLY / BLOCKED** for all runtime
cases, even when every source contract passes.

- Pulse: `.baobab/development_adapter.py` can observe an actual native
  `/readyz` response and run native owner migrations against an explicitly
  supplied disposable development PostgreSQL. `Dockerfile.integration`
  builds the owner-native image with migrations and integration test code.
  Both seed and domain exercise still block without genuine governed tenants.
- Payments: `.baobab/development_adapter.py` is a host-side probe because
  the Rust distroless image does not embed Python. It observes the actual
  `/health/ready` endpoint. Payment mutations remain blocked, never
  fabricated. It does not claim PSP certification or real money movement.
- The first-adopter lock uses source commits, not mutable `main` branches.
  The adapter results are not a substitute for read-back of CP grants,
  independently-issued IAM tokens, actual request/denial effects, real
  database state or witnessed cleanup.

## CI

```sh
python3 -B -m unittest discover \
  -s tests/platform-integration/development -p 'test_dev15_source.py' -v

python3 -B tests/platform-integration/development/dev15_source.py \
  --shared-root .shared-dev15 \
  --pulse-root .dev15-pulse \
  --payments-root .dev15-payments \
  --output /tmp/dev15-source-inventory.json
```

The separate `dev15-first-adopters.yml` job obtains exact source checkouts
and validates owner-provenance and the negative case inventory. The generated
source inventory is a diagnostic, not a protected receipt. CI intentionally
does not convert missing runtime evidence into PASS or activate a provider.

## Remaining **real execution** critical path

1. Adopt the real DEV-15 IAM clients in the disposable Hydra issuer and
   current CP workload registry. Verify actual IAM token audience, issuer,
   scopes, revocation, and wrong-Tenant denial. Existing DEV-06 authorities
   cannot silently be re-labelled as DEV-15.
2. Compose the selected profile's native subject and backing services on a
   **private, TTL-bound**, digest-locked project through DEV-01's existing
   `prepare/up/test/evidence/down/recover` lifecycle. Use an owner adapter
   with least privilege; no CP store writes and no IAM issuer secrets.
3. Provision synthetic Organisations, Tenants, current capabilities and
   ordinary bindings through governed CP APIs. Independent read-back must
   confirm the actual actor, legal authority and provider/instance.
4. Execute every unchanged ENG-ONB-01..09 and native-specific case:
   Pulse canonical PostgreSQL + Qdrant hydration, real context/capability
   decision and revocation; Payments sandbox intent/authorise/capture/cancel/
   refund, current mandate and denied replay/cross-tenant, **simulated money
   only**. Use independent effect observation and fail closed on exceptions.
5. Retain source/OCI-image digests, per-case redacted receipts, runtime
   environment classification, lease/cleanup witness, and verify no owned
   resources or credentials survive. Do not state DEV-15 accepted until all
   mandatory cases and teardown genuinely pass.

## Lifecycle guardrails

Developer-only, synthetic-only, no exposed admin ports, no bypassed scope or
caller-supplied tenant identity. Component source evidence does **not** qualify
a certified provider, protected staging, external settlement, or production.
Keep historical DEV-06 receipts and the seven-case INT-03C and fourteen-case
NAB-03 inventories unchanged. If source validation fails, roll back the
matching owner/source lock; do not loosen the schema, run a local mock, or
declare missing mandatory cases skipped.
