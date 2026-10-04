# Platform L3 harness

Critical-path checks against the local infrastructure topology.

```bash
# From repository root (after make local-env or make ci-env)
make platform-l3

# Engine-template hooks only (no Docker stack required)
make platform-l3-engine-template
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `PLATFORM_CP_URL` | unset | If set, L3-04 probes CP readiness |
| `PLATFORM_IAM_URL` | unset | If set, L3-05 probes OIDC discovery |
| `ENGINE_TEMPLATE_DIR` | sibling `../engine-template` | L3-07 template hooks check |
| `REQUIRE_ENGINE_TEMPLATE` | unset | If `1`, L3-07 fails when template is missing |
| `EVIDENCE_DIR` | `tests/platform/evidence` | Evidence JSON output |

Requires `compose/.env` for full L3 (see `make local-env` / `make ci-env`).
The engine-template check alone does not need Compose.

## Checks

| ID | Description |
| --- | --- |
| L3-01 | Infrastructure smoke (`verify-local`) |
| L3-02 | RabbitMQ management ready |
| L3-03 | PostgreSQL readiness |
| L3-04 | Optional CP URL |
| L3-05 | Optional IAM OIDC discovery |
| L3-07 | Engine-template L2/L3 hooks |
| L3-06 | Evidence pack |

See [engine-template-hooks.md](./engine-template-hooks.md).

## Evidence

Each full run writes `evidence/l3-<timestamp>.json` with pass/fail per check.
