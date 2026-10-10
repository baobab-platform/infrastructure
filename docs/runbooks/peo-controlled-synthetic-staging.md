# PEO-03C / PEO-02E — controlled authenticated synthetic staging acceptance

**Release status:** NOT CERTIFIED. This document is an executable acceptance
definition and a deployment dependency checklist, not a staging pass report.

## Programme dependencies (in merge and deployment order)

- CP #312 → CP #315 → CP #319 (v2 admission to atomic tenant registration).
- Shared #272 already merged; Shared #273 adds the internal-authority and
  billing-event-observe workload permissions.
- CP #316 → CP #318 (current INTERNAL PDP); Subscriptions #34 → #35.
- CP #320 and Subscriptions #36 (durable event relay and receipt).
- All corresponding Shared contracts must be merged, pinned and validated
  against each engine's `contracts.lock.yaml` before staging admission.

## Required staging identities

Two distinct **real IAM-issued** OAuth client-credentials identities must be
separately registered with the platform's workload registry, restricted to
`staging` and provisioned by the IAM authority:

1. The **baobab-subscriptions** workload: CP audience,
   `subscription:internal-authority` scope and current active workload
   registration. Tests re-evaluate current INTERNAL sponsorship on every call.
2. The **baobab-cp** workload: Subscriptions audience,
   `billing:observe` scope and current active workload registration.
   This token is attached by CP's outbox relay from a sidecar-mounted
   absolute file, and Subscriptions verifies the client identity, issuer,
   audience, signature, expiry and scope before committing an inbox record.

Do **not** reuse one token for both audiences, expose client secrets in
containers or logs, or bootstrap synthetic JWKS as a staging credential.

## Protected GitHub environment configuration

Configure these **staging environment variables** before manually running
`.github/workflows/peo-synthetic-staging.yml` on infrastructure `main`:

- `PEO_STAGING_IAM_TOKEN_URL`: reviewed TLS IAM OAuth token endpoint.
- `PEO_STAGING_CP_BASE_URL`: reviewed deployed CP staging URL.
- `PEO_STAGING_SUBSCRIPTIONS_BASE_URL`: reviewed deployed billing URL.
- `PEO_STAGING_ALLOWED_HOSTS`: exact comma-delimited hostnames for all
  three endpoints; never a wildcard.
- `PEO_STAGING_CP_AUDIENCE` and `PEO_STAGING_BILLING_AUDIENCE`:
  exact live IAM OAuth audience identifiers.
- `PEO_SYNTHETIC_TENANT_ID`,
  `PEO_SYNTHETIC_PRODUCT_SUBSCRIPTION_ID`, and
  `PEO_SYNTHETIC_CLASSIFICATION_REFERENCE`: approved, **synthetic**
  commercial/INTERNAL proof fixture; the current INTERNAL assessment for
  this fixture must be valid at test time.

Configure these **staging environment secrets**:

- `PEO_STAGING_SUBSCRIPTIONS_CLIENT_ID`,
  `PEO_STAGING_SUBSCRIPTIONS_CLIENT_SECRET`
- `PEO_STAGING_CP_CLIENT_ID`,
  `PEO_STAGING_CP_CLIENT_SECRET`

The hosted job must use an approved staging runner that can reach private
staging endpoints without disabling TLS verification; no IAM identities,
clients, account IDs, AWS OIDC role ARNs or protected staging endpoints are
invented by this repository. Real AWS staging account/OIDC role/state bucket
and reviewed release `deploy/releases/staging/*.tfvars.json` must exist
before external acceptance.

## Workload-side runtime settings

- Control Plane: `PEO_FOUNDING_GOVERNANCE_ENABLED=true`,
  `PEO_PROGRESSIVE_ADMISSION_ENABLED=true`,
  `PEO_PROGRESSIVE_BRIDGE_ENABLED=true`,
  `ORGANISATION_FIRST_V2_ENABLED=true`,
  `PEO_INTERNAL_AUTHORITY_ENABLED=true`,
  `PEO_SUBSCRIPTIONS_WORKLOAD_CLIENT_ID=<IAM-issued client>`,
  `PEO_FOUNDING_DELIVERY_ENABLED=true`,
  `PEO_BILLING_EVENT_INBOX_URL=https://<staging-subscriptions-host>/internal/v1/founding-lifecycle-events`,
  and `PEO_BILLING_EVENT_TOKEN_FILE=<absolute IAM-managed rotating token file>`.
- Subscriptions: `PEO_INTERNAL_AUTHORITY_ENABLED=true`,
  `PEO_CP_INTERNAL_AUTHORITY_BASE_URL=<reviewed CP URL>`,
  `PEO_CP_INTERNAL_AUTHORITY_TOKEN_FILE=<absolute IAM-managed rotating token file>`,
  `PEO_FOUNDING_EVENT_RECEIVER_ENABLED=true`,
  `PEO_CP_EVENT_CLIENT_ID=<IAM-issued CP client>`;
  PostgreSQL persistent storage is mandatory.

Both services independently reject production-mode enablement.

## Evidence levels and final gating

| Evidence level | Proof needed | Acceptance |
| --- | --- | --- |
| Static/CI | Canonical Shared contracts, PostgreSQL migrations, Go/Java tests | May be green in PR; not staging certification |
| Authenticated client proof | Real IAM client_credentials token, correct audience/scope/client, current PDP positive and stale-reference denial | `peo-synthetic-staging.yml` generates redacted artifact |
| Direct durable receipt | Valid CP-client OAuth; HTTP 202 initial receipt, 200 exact duplicate, tamper rejection, incorrect-audience rejection | Same redacted artifact; this is **not** proof of CP relay |
| **End-to-end relay proof** | Trigger approved synthetic sponsorship suspend/revoke/expire through independently authorised CP governance API; observe committed CP outbox row, unsuccessful attempt/retry, Subscriptions durable inbox ID, CP `published_at` only after matching ACK; test replay after restart | **Separately required, not silently claimed by the workflow** |
| v2 founding tenant proof | Six distinct registered human principals, approved reviewed Organisation, separate v2 authorisation, one tenant and PRIMARY mapping, zero legacy v1 onboarding, one provisioning outbox, denial of duplicate/changed replay | PostgreSQL test and controlled staging scenario |
| Operational certification | Live IAM token rotation, workload revocation, outage, staging deployment, rollback, retention/recovery, p95 and alert evidence | Required before external onboarding |

Real NABHOLD and its autonomous subsidiaries are explicitly **excluded** from
synthetic admission and any production financial/legal actor authorisation.
ZuriBeans' operating Organisation and Nabhold legal actor remain distinct.
No parent-selling mandate, incorporation record, or ERP assignment is minted
as a side effect of PEO acceptance.

To avoid falsely reporting complete go-live, require the operator to attach
outbox/inbox/broker evidence and IAM-registration proof to the acceptance
review before taking the staging certification decision.

## PEO-02F — Actual CP-governed event and independently observed durable receipt

The acceptance capability is implemented by:
- `.github/workflows/peo-cross-engine-relay-proof.yml`
- `scripts/acceptance/peo_cross_engine_relay.py`
- `scripts/acceptance/test_peo_cross_engine_relay.py`

**This is distinct from the earlier direct HTTP consumer fixture**. The
PEO-02F proof never creates its own CloudEvent or inserts a CP outbox row.
An independently authorised *human* must call the existing governed API to
suspend one already-approved, synthetic ACTIVE sponsorship:

`POST /v2/founding-governance/sponsorships/{grantID}/suspend`

The command is idempotent, has `expected_status=ACTIVE`, names a real human
reviewer holding `admission:decide`, and sends a unique correlation ID. CP's
transaction writes its audit and the canonical event to
`messaging.outbox`; CP #320 relays it with a separately obtained IAM
`billing:observe` workload token, and Subscriptions #36 receives it,
authenticates the workload, stores the canonical envelope and verified
client identity in `billing.founding_event_inbox` and acknowledges only
after commit. The worker marks `published_at` after that acknowledgement.

### One-time governed fixture prerequisite

An authorised staging administrator and a *different*, already registered
human approver must have created an ACTIVE sponsorship through the standard
maker/checker PEO-02 procedure, never directly inserted an unaudited row.
For the proof to touch only synthetic records, the staging database must
already contain these immutable facts:

- Sponsor and operating Organisation display names begin `Synthetic PEO `.
- `authority_basis_reference` begins `staging/peo-relay/`.
- All `evidence_references` begin `staging/peo-relay/`.
- Sponsorship scope is `INTERNAL_GROUP_ADMISSION`, status `ACTIVE`,
  effective window currently valid, and proposed_by differs from approved_by.
- A different human reviewer holds current CP administrative
  `admission:decide` authority, from a genuinely signed IAM OIDC token.

**SUSPEND is forward-only.** An attempted second run with that grant must
fail its ACTIVE preflight, not reinstate the sponsorship. Every run requires
a separately reviewed new synthetic grant. No real subsidiary, seller of
record, default legal actor, ERP handoff or accounting entity is touched.

### Protected staging environment values

In addition to the earlier variables and IAM clients, configure the
following in the protected GitHub `staging` environment:

| Configuration | Origin and controls |
| --- | --- |
| `PEO_STAGING_HUMAN_REVIEWER_TOKEN` (secret) | Short-lived real IAM human access token, issued to an independently authorised reviewer immediately before an approved run; delete/rotate after the run, never expose in logs |
| `PEO_STAGING_CP_EVIDENCE_DB_URL` (secret) | Dedicated CP **SELECT-only** PostgreSQL 17 connection URI; cannot write, must reach only the protected staging database |
| `PEO_STAGING_SUB_EVIDENCE_DB_URL` (secret) | Separately provisioned Subscriptions **SELECT-only** PostgreSQL 17 connection URI; must not be the CP database |
| `PEO_STAGING_EVIDENCE_DB_CA_PEM` (secret) | Certificate authority for database `sslmode=verify-full` on both independent endpoints |
| `PEO_STAGING_ALLOWED_DB_HOSTS` (var) | Exact comma-delimited allowed DB hostnames, no wildcard or loopback hostname substitution |
| `PEO_STAGING_CP_DEPLOYED_REVISION` (var) | Reviewed currently deployed CP build/commit digest |
| `PEO_STAGING_SUB_DEPLOYED_REVISION` (var) | Reviewed currently deployed Subscriptions build/commit digest |
| `inputs.grant_uuid` | The exact reviewed, already ACTIVE synthetic sponsorship UUID; selected by authorised reviewer per run |
| `inputs.suspend_grant=true` | An explicit protected one-way approval; no unattended recurring or PR-triggered mutation |

SQL credentials should be dedicated to the evidence surfaces. For CP grant
only SELECT on `messaging.outbox`,
`admission.founding_group_sponsorship` and the two specific
`registry.organisation_profile` rows/approved synthetic-only evidence view;
for Subscriptions grant SELECT on `billing.founding_event_inbox`.
Where fine-grained staging views are available, **prefer them** to grants on
the underlying tables. These are **operational verification principals**,
not engine-to-engine runtime DB access. Do not allow a cross-engine
application SQL dependency.

Run `PEO CP to Subscriptions Real Staging Relay Proof` manually against
the merged infrastructure `main`, with the approved one-time UUID and
boolean consent. A pull request only executes compilation and pure validator
unit tests; it can never call the staging mutation or produce real evidence.

### Required evidence report

The runner writes a redacted, downloadable GitHub Actions artifact:

`peo-acceptance-evidence/cp-subscriptions-relay.json`

A result of `PROVED` is possible only when all the following are true:

1. IAM issues two genuine, distinct OAuth `client_credentials` tokens for
   their exact CP and Subscriptions audiences and required scopes.
2. An independent human's actual OIDC bearer is authorised by the CP API.
3. One existing, vetted synthetic ACTIVE grant is suspended through CP's
   governed transition. The original state, evidence reference, maker and
   approver provenance are checked through read-only SQL *before* mutation.
4. The CP outbox row has the precise grant UUID, newly generated correlation
   UUID, canonical event type, canonical envelope, event ID, occurrence
   timestamp and nonzero attempts; publication is actually recorded.
5. The independent Subscriptions PostgreSQL inbox has the *same event ID,
   grant, canonical envelope, type, source*, populated receive/process
   timestamps and matching canonical SHA-256.
6. That inbox receipt stores the client ID obtained from a token actually
   verified at the HTTP edge (Subscriptions V4 migration), and it matches
   the expected IAM CP workload client identity.
7. Temporal order is CP occurred ≤ Subscriptions received ≤ CP published.
   The proof fails if the bounded window is exceeded or any evidence is
   missing, mismatched or corrupted.

The report also records the GitHub workflow run ID, deployment revision
assertions, the on-disk subscriber wire digest and cross-engine canonical
digest. **It does not contain human/engine bearer tokens, DB passwords, raw
event envelopes, legal identity data or applicant names.**

A failed or timed-out proof **does not roll back the valid SUSPENDED grant**.
The artifact remains marked `PENDING_DURABLE_DELIVERY` for forensic review.
Operators should reconcile the specific correlation/event IDs before any
new scenario. A successful technical relay proof is not statutory
verification or authority to admit a real operating business.

### Security and staging release prerequisites

This proof requires merged and deployed CP #312/#315/#316/#320,
Subscriptions #34/#35/#36, Shared #272/#273 and the scoped IAM authority
configuration. CP #319's progressive registration can be separately
accepted; it is not automatically certified by a sponsorship suspension.
Staging must have a reviewed AWS account, IAM federated trust, protected
environment, operational token refresh sidecars, scoped read-only DB roles,
TLS certificate trust and deploy provenance. None of these external
credentials or infrastructure identities may be fabricated by tests.

**Current proof state:** code and CI automation delivered; no live GitHub
`workflow_dispatch` acceptance success has been reported by this document.
