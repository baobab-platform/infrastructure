# Required checks matrix (Phase E)

Aligned with ADR-Infra-0020 and the [platform integrated testing strategy](./platform-integrated-testing-strategy.md).

**Date:** 2026-10-04  
**Status:** Draft operational policy for free-tier + Foundation coexistence

## Per-PR (engine repositories)

| Check | Required | Notes |
| --- | --- | --- |
| L0 unit (`make test` or language equivalent) | Yes | Engine-owned |
| L1 contract / consumer lock (`contract_lock.py check --mode enforce`) | Yes when engine has `contracts.lock.yaml` | Pin must match Shared |
| Foundation Repository Gates | Yes where enabled | Existing org policy |
| Full platform L3 | **No** | Too expensive for free tier |

## Per-PR (infrastructure)

| Check | Required | Notes |
| --- | --- | --- |
| Compose config validate | Yes | `docker compose config` |
| Full local smoke / L3 | **No** on PR | Opt-in on main / schedule / dispatch |

## Main / release / scheduled

| Check | Required | Notes |
| --- | --- | --- |
| Infrastructure local smoke (`make local-verify`) | Yes when minutes allow | |
| Platform L3 (`make platform-l3`) | Yes when minutes allow | Evidence artifact retained |
| Engine L2 against Compose | Recommended nightly | Engine CI or dispatch |

## Evidence

- L3 writes `tests/platform/evidence/l3-<timestamp>.json`
- Workflow should upload the evidence directory as a CI artifact (already in `platform-l3.yml` when present)

## Private repos

Making `baobab-cp` / `shared` private may require billing for Actions. Until then, keep minute-aware gating and prefer local `make platform-l3`.
