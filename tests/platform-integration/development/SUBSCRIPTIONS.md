# Subscriptions native development profile

Run in the existing private integration Dev Container with Docker available:

```sh
BAOBAB_ENVIRONMENT=development python3 -B tests/platform-integration/development/ci_subscriptions.py
```

The same command runs in owner Actions. It uses the existing lifecycle lease,
watchdog, TLS, IAM bootstrap, CP-owned fixtures and source/image verification;
it adds only Subscriptions and its own PostgreSQL 17 store. No CMS, frontend,
ERP, Payments or real monetary provider starts. No engine or orchestrator writes
canonical CP data: only CP's guarded development binary owns fixture transitions.

Two immutable source locks keep this increment separate from the historical
DEV-01..06 pins. The engine source pins its original Shared contract bundle. CP and Subscriptions
have distinct per-run database secrets; native own-store authentication must pass
and the same engine credential must receive a specific password-authentication
refusal from the running CP database. A network outage cannot satisfy that case.
Every native service has run ownership labels, no published/admin ports and one
internal-only network. TLS verification stays enabled; the JVM truststore holds
only this run's CA. Audience-specific tokens and introspection secrets stay in
private run custody and are mounted read-only into the engine. Current CP tokens
are refreshed in place so bind mounts see renewal; credentials are never evidence.

The fixed engineering inventory has seventeen native observations and three
independent blocked obligations. COMMERCIAL persistence is real but its monetary
readiness must remain BLOCKED/simulated. This fixture confers no INTERNAL
eligibility or actual legal/financial authority. Full Subscriptions onboarding,
DEV-09/INT-08 and DEV-06/INT-07 remain partial. No commercial dispatch is enabled.
Events are durable invalidation hints, never grants or completed reconciliation.

The suite must fail if any native case fails or is missing; a BLOCKED independent
provider/eligibility obligation must not become PASS. The completed report carries
actual tested harness/source SHAs, running image IDs, exact case outcomes, original
byte hash and scoped cleanup. Initial or interrupted runs cannot reuse an earlier
green report. CI uploads only completed sanitized receipts, never private state,
DSNs, tokens, raw bodies or fixture IDs. Artifact metadata controls actual expiry.

On failure inspect the closed phase/case diagnostic and owner CI; do not print
private captured logs. Use the same recovery command:

```sh
python3 -B tests/platform-integration/l4.py recover development --all
```

Recovery discovers only this namespace's nonce-labelled resources and removes
owned containers, volumes, networks, built images and private state. It does not
remove third-party base images or claim host destruction. Restore reviewed pins
together to roll back this profile; never reuse a previous physical PG volume.
DEV-06's original entitlement/binding negatives stay deferred until the actual
Subscriptions INTERNAL prerequisite is established.
