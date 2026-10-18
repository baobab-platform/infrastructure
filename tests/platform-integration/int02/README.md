# INT-02 real IAM, Control Plane and Pulse qualification

Authority: Accepted ADR-SHARED-036, EA v2.2 mandatory acceptance matrix and
[the owner-approved named bootstrap decision](https://github.com/baobab-platform/shared/blob/33f1dd6aa7c0db43743dbb02cff16d5dc0802610/docs/architecture/int02-pulse-proof-bootstrap-decision.md).

Status: implementation candidate until a complete final-pin live run passes.
All five mandatory scenarios, every required provider observation and teardown
must pass. Schema tests, token issuance, native conformance and ACTIVE workload
status independently establish no complete qualification.

## Run

Use the integration Codespace (4 CPUs, 8 GiB RAM) or the matching GitHub Actions
Dev Container. Docker Compose and public read-only source/image downloads are
required. The complete entrypoint guarantees cleanup on success and failure:

```sh
bash tests/platform-integration/int02/run-in-devcontainer.sh
```

For diagnosis the individual entrypoints are:

```sh
python3 tests/platform-integration/l4.py preflight iam-cp --static
python3 tests/platform-integration/l4.py materialise iam-cp
python3 tests/platform-integration/l4.py up iam-cp
python3 tests/platform-integration/l4.py test iam-cp
python3 tests/platform-integration/l4.py evidence iam-cp
python3 tests/platform-integration/l4.py down iam-cp
```

Always run `down` after individual commands. Source revisions and runtime
images are locked in `lock.json`; receipts independently record the executing
harness SHA and actual built image IDs. Candidate IAM/CP revisions use the
validated reusable-workflow inputs, without shell expression interpolation.

## Real boundaries

- IAM is actual Keycloak from pinned Baobab IAM source. A confidential RP and
  Chromium complete code/S256 and privileged TOTP enrollment/challenges, with
  state/nonce/verifier/code-reuse, callback, issuer, signature and expiry checks.
  No human password grant substitutes for this ceremony. The same-workload
  audience differential uses a real issuer token and restores its mapper.
- CP runs its normal binary, migrations, canonical identity, governed PRIMARY,
  market, current grant/revocation and caller-owned context checks. Four humans
  have exact, time-bounded Organisation grants. Shared corporate ownership and
  PlatformAccount membership never confer neighbour access: all 16 record
  isolation checks must pass, each after its own positive.
- Pulse runs its normal HTTP composition with real IAM/JWKS and its independent
  registered validator calling CP with the caller's subject-token evidence.
  Its canonical PostgreSQL and separate Qdrant server are actual processes.
  Native persistence, hydration, stale projections and classification/tenant
  isolation are distinct from HTTP authorization. Embeddings use the owner's
  deterministic reference implementation; no model-quality claim follows.

All external application requests traverse the TLS 1.3 edge and verify this
run's one-day CA and hostnames. The CA signing key is destroyed immediately.
The edge-to-service hops and database/vector connections are HTTP/native
protocol on the internal Compose network; no ports are published. Tokens,
secrets, cookies, TOTP seeds and database responses never enter retained logs.

## Named bootstrap and provider governance

Shared #346 accepts only `baobab-int02-pulse-consumer` as a development evidence
producer. Its fixture-only client uses a fresh secret, 120-second tokens, no
human/password/admin grant and two independent optional scopes/audiences:
`context:resolve` at CP and `intelligence:evidence:search` at Pulse. Product IAM
bootstrap is unchanged. CONFIDENTIAL is the ceiling; RESTRICTED stays denied.
Wrong credential, disabled issuance, wrong audience, wrong context owner,
fabricated context and neighbour results are independently checked.

The three governance Principals are different actual browser-authenticated
humans: `human` records the release, `parent` requests the changesets and
`subsidiary` checks them. Additional canonical administrative scopes exist only
on this disposable human fixture. The Pulse caller and validator receive no
provider or certification authority.

A frozen native/HTTP conformance report binds exact sources, the provider
manifest digest and actual local image configuration digest. The EngineRelease
records that local build, with no claim that a registry artifact was published.
Actual APIs record certification, refuse recorder self-certification, approve
the release through ENGINE_RELEASE_APPROVAL and activate the registered DRAFT
provider through PROVIDER_ACTIVATION. Certification is deliberately revoked,
observed as unqualified and replaced through its API; it is rechecked after
all faults. Approval, certification, activation, binding and health stay
separate facts. No SQL-written certification, release approval or activation
is permitted.

Tenant authority, topology, grants and binding faults are explicit synthetic
fixtures in the disposable CP database. Health rows derive from actual HTTPS
readiness and authorized search, or the observed stopped Pulse process. There
is no health-ingestion HTTP endpoint at the pinned CP revision; the fixture
writes its canonical ephemeral observation table directly, with this boundary
explicit in `provider_fixture.py`.

The real provider must resolve to the exact registered provider/instance and
contract. Missing grant/binding, wrong contract, incompatible market scope,
inactive instance and incompatible isolation scope require exact CP decisions.
Expired HEALTHY becomes UNKNOWN: CP's Shared policy permits UNKNOWN for a
STANDARD capability. The harness observes this policy and refuses to count
expired observations as current qualification. Stopping Pulse must produce a
real upstream outage while IAM/CP stay ready; a current UNAVAILABLE observation
must then deny resolution. Restart, authorized search, current certification,
current three-level health and exact resolution must all recover.

## Evidence and acceptance

Each run begins BOOTSTRAP / REQUIRED_NOT_EXECUTED. The first proof may be
produced during its disposable window, ending on success, failure or the
75-minute live-job timeout. Only the complete final-pin run plus teardown may
be QUALIFIED_SYNTHETIC_RUN. Missing, stale, false or merely truthy required
checks fail closed. Cleanup failure leaves `passed: false` and retains recovery
handles. No earlier run's result transfers to a new run or changed source pin.

The workflow always retains scrubbed `*-int02.json` receipts and immutable
`*-provider-proof.json` reports, including failed runs. Certification evidence
names the actual Actions run (or local harness revision), identifies the
provider-proof report and records its exact digest. A receipt carries a fresh
self-digest after teardown. No real enterprise identity, legal verification,
protected staging acceptance, Nabhold release or production authority is
created by these synthetic tests.
