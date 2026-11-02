# DEV-11 — correlation, safe diagnostics and affected-profile CI routing

**Authority:** accepted Shared EA v2.3 / EA-DEV DEV-11; Infrastructure
ADR-Infra-0016. **Status:** SOURCE-ONLY FIRST INCREMENT, NOT DEV-11 COMPLETE.
This work does not publish GHCR baobab-dev:v1.5.0, modify providers or merge PRs.

## Included

- A closed reference five-hop W3C trace receipt validator for BFF → IAM
  issuer → CP → engine → outbox. It verifies one trace ID, per-hop distinct
  spans, exact parent linkage, a canonical UUID correlation ID, source SHA,
  scenario identity, and closed cause codes. This **linear reference** does
  not purport to represent every possible valid branched/asynchronous trace.
- Input is **allowlisted rather than post-hoc scrubbed**. Headers, bearer
  tokens, cookies, customer names, arbitrary URLs, error text, SQL and bodies
  are forbidden. Refusals never echo inputs. Outputs exclude raw spans and
  per-request identifiers; metrics cardinality stays controlled.
- PASS, FAIL, BLOCKED and NOT_RUN are distinct; a missing service, source or
  native capability cannot become a PASS. **Even a structurally valid full
  reference chain never sets runtime_qualified**: callers can self-assert
  runtime observation and teardown, which is not independent proof. Verified
  live receipts remain under the owning native qualification gates.
- Conservative source routing names affected DEV-01..15, L4, local stack and
  estate browser owners. An unknown source path or changed workflow selects
  all, rather than silently skipping tests. The emitted receipt always says
  PLANNED_NOT_EXECUTED, not a fictional green CI execution.
- A small GitHub Actions job tests the validators on every PR and creates
  an auditable source-only profile plan. Its daily schedule records a **full
  plan only**; it deliberately does not claim nightly runtime completion.
  Existing platform-development and engine/estate owner workflows remain
  responsible for executing real suites.

## Reproduce

    python3 -B -m unittest discover -s tests/platform-integration/development -p 'test_dev11_assurance.py' -v
    python3 -B tests/platform-integration/development/dev11_assurance.py plan --full
    python3 -B tests/platform-integration/development/dev11_assurance.py plan --base <40-hex> --head <40-hex>
    python3 -B tests/platform-integration/development/dev11_assurance.py verify-chain --input /private/run-owned/safe-projection.json

The verifier input must be a run-owned **closed projection**, never a raw
OpenTelemetry dump. Do not publish original traces or credentials as CI
artifacts. A local successful test is SOURCE evidence, not live qualification.

## Outstanding DEV-11 acceptance gates

1. Native owners implement W3C context propagation across BFF, issuer, CP,
   engine and the outbox, including branch/async span links. Trace context and
   business correlation never confer CP grants or actor authority.
2. Capture genuine run-owned traces and independently attest source pins,
   native authority, negative cases, redaction, evidence hashes and teardown.
   Fail closed for missing, revoked or wrong-tenant operations, unknown provider
   outcomes, replay and missing outbox causation.
3. Connect the routing plan to actual owner workflow execution with explicit
   BLOCKED receipts and no fake-green skips. Qualify the full nightly/release
   matrix only with the necessary environments and image compatibility.
4. Reconcile Nabhold, ZuriBeans and Thamani Playwright/axe, browser visual,
   accessible navigation, responsive, CWV/Lighthouse and private preview gates.
   Retain each estate's independent branding and current budgets; leave
   thresholds unchanged absent qualified evidence.
5. Update the official Shared DEV-11 register after attributable, reviewed
   source and genuine connected evidence. Preserve protected staging and
   production acceptance as separate approvals.

**Rollback:** revert this standalone proposed source increment. Prior
runtime receipts and accepted enterprise authority contracts are unchanged.
