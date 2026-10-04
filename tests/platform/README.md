# Platform L3 harness

Critical-path checks against the local infrastructure topology.

```bash
make platform-l3
make platform-l3-engine-template   # L3-06 only, no Docker
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `PLATFORM_CP_URL` | unset | L3-04 CP readiness |
| `PLATFORM_IAM_URL` | unset | L3-05 OIDC discovery |
| `PLATFORM_REGULATIONS_URL` | unset | L3-09 Regulations probe |
| `ENGINE_TEMPLATE_DIR` | sibling `../engine-template` | L3-06 template hooks |
| `REQUIRE_ENGINE_TEMPLATE` | unset | Fail L3-06 if template missing |
| `EVIDENCE_DIR` | `tests/platform/evidence` | Evidence JSON |

Requires `compose/.env` for full L3.

## Checks (v0.3.0)

| ID | Description |
| --- | --- |
| L3-01 | Infrastructure smoke (`verify-local`) |
| L3-02 | RabbitMQ management ready |
| L3-03 | PostgreSQL readiness |
| L3-04 | Optional CP (`skip` if unset) |
| L3-05 | Optional IAM OIDC (`skip` if unset) |
| L3-06 | Engine-template hooks |
| L3-08 | RabbitMQ publish/get fixture |
| L3-09 | Optional Regulations (`skip` if unset) |
| L3-10 | APISIX admin routes |
| L3-11 | Evidence pack (last) |

See [engine-template-hooks.md](./engine-template-hooks.md) and [required-checks-matrix.md](../../docs/testing/required-checks-matrix.md).
