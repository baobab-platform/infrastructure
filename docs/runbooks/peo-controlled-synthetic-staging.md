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
