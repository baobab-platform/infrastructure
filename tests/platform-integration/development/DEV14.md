# DEV-14 reusable engine onboarding — source planner

**Scope:** source inspection and deterministic dependency planning only. The
engine-specific execution adapter and connected DEV-15 proof are **not yet
implemented**. This component does not claim complete DEV-14 acceptance.

## Normative authorities

- Accepted Shared EA v2.3 / EA-DEV DEV-14 and DEV-15.
- Shared `9fa1bbd6ad9b5c9d4ec406c721bd75227803dcea` (merged #402):
  `development/v1/engine-integration-profile.schema.json`, examples, and
  `scripts/engine_integration_profile.py`.
- ADR-SHARED-043 development-only bootstrap; -036 L4 real-component
  qualification; -017 provider lifecycle and catalogue; -015 provisioning.

The three existing authorities remain independent: environment requirements
are owned by the engine, capability-provider declarations do not certify or
activate providers, and synthetic enterprises cannot grant business authority.

## Source planning in CI / Codespaces

Check out the exact Shared pin into an isolated directory (never silently read
mutable `main`). The **only** supported profile inputs currently are the
versioned Shared JSON examples. Ensure the Python environment contains the
exact Shared validator dependencies.

```sh
git clone https://github.com/baobab-platform/shared.git .shared-dev14
git -C .shared-dev14 checkout 9fa1bbd6ad9b5c9d4ec406c721bd75227803dcea
python3 -m pip install -r .shared-dev14/.github/foundation-tests/requirements.txt

python3 -B tests/platform-integration/development/engine_onboarding.py \
  plan --profile pulse-intelligence --shared-root .shared-dev14
python3 -B tests/platform-integration/development/engine_onboarding.py \
  doctor --profile payments-sandbox --shared-root .shared-dev14
```

A planner returning `result=BLOCKED` with
`ENGINE_SOURCE_NOT_INSPECTED`, `REQUIRED_IMAGE_DIGEST_MISSING` and
`RUNTIME_ADAPTER_NOT_QUALIFIED` is **correct** for these commands. The
`doctor` action currently checks source and owner declarations only, **not**
Docker, registry, network access or readiness. Future runtime execution must
not reuse its result as a health check.

To inspect native owner declarations as well, check out the engine at an exact
commit and pass `--engine-root PATH --engine-sha 40_CHAR_SHA`. Shared's
canonical validator will check the owner environment, capability declaration,
actual implemented support, owner adapter path and Dockerfile. Both checkouts
must be clean and match their declared commits.

An optional JSON image lock has schema `infrastructure.dev14.images.v1` with
fields `profile_key` and `images`, keyed by required service keys to exact
OCI `@sha256` digests. Missing required images remain BLOCKED. Even a
complete image manifest is insufficient to assert a runnable private Compose
topology, actual IAM credentials, provider health or passed ENG-ONB cases.

## Engineering remaining before DEV-14 exit

1. Implement a reviewed owner-adapter interface for running native engine,
   migrations and tests without giving it CP database or IAM admin secrets.
2. Compose required IAM + CP + subject + engine-owned stores on a private,
   digest-locked, TTL-bound run using DEV-01's durable lifecycle and recovery.
3. Obtain real IAM signed tokens and current CP authority, enforce provider
   eligibility via its normal APIs; no activation shortcut or synthetic legal
   claim that becomes VERIFIED.
4. Record redacted per-case ENG-ONB-01..09 source/runtime/provenance and
   independently checked cleanup; no source-only automatic PASS.
5. Expose true doctor/up/test/evidence/down commands in Codespaces and Actions.
6. Generalise engine-template; adopt Pulse and Payments under DEV-15 with
   independent actual current evidence.

## Safety and rollback

No run credentials or workloads are created by the source planner. Restore the
previous Infrastructure commit to remove the feature. Do not modify DEV-01
locks or historical acceptance receipts. An unavailable native implementation
blocks only its own engine, not unrelated CMS, IAM, or Control Plane engineering.
