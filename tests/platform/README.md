# Platform L3 harness

Critical-path checks against the local infrastructure topology.

```bash
# From repository root (after make local-env or make ci-env)
make platform-l3
```

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `PLATFORM_CP_URL` | unset | If set, L3-04 probes CP readiness |
| `PLATFORM_IAM_URL` | unset | If set, L3-05 probes OIDC discovery |
| `EVIDENCE_DIR` | `tests/platform/evidence` | Where evidence JSON is written |

Requires `compose/.env` (see `make local-env` / `make ci-env`).

## Evidence

Each run writes `evidence/l3-<timestamp>.json` with pass/fail per check.
Failures leave Docker status in the log; evidence still records outcomes.
