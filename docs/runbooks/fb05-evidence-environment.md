# FB-05 staging evidence environment: dependencies and acceptance

**Purpose.** Produce the end-to-end evidence that the Control Plane's provisioning worker, running as the staging evidence provisioner
(`baobab-cp-provisioning-evidence-workload`), can provision through ERP using a federated workload token, and is refused when it should be.

**Status.** Not operational and **not accepted**. This runbook lists what must exist and what must be proven. An `ACTIVE` registry entry is
not acceptance evidence, and neither is a successful HTTP 200.

## 1. What exists, and what does not

| Piece | Owner | State |
|---|---|---|
| Registry entry (staging, `ACTIVE`, `erp:provision`, `TENANT_PROVISIONING`, `federated_workload_token`) | Shared | Merged (`70f92ee`, shared#251) |
| IAM re-pin, environment isolation in the token-profile policy, no Keycloak client for federated workloads | baobab-iam | Merged (baobab-iam#87) |
| Control Plane client half of the RFC 7523 exchange (`ERP_PROVISIONER_ASSERTION_FILE` mode) | baobab-cp | Open: baobab-cp#286 |
| ERP signed event dispatcher report fix | baobab-erp | Merged (baobab-erp#65) |
| Projected assertion issuer and signing-key lifecycle | infrastructure | **Not built.** ADR-Infra-0025 (Proposed) |
| Hydra able to issue `aud=baobab-erp` on `jwt-bearer` | provider / baobab-iam | **Blocked.** Pinned v26.2.0 cannot; the fix is in Hydra OSS master and the enterprise v26.3.1, in no published OSS release |
| Staging Hydra, ERP and Control Plane services | infrastructure | **Not deployed.** Staging has CP, IAM, Keycloak and Pulse only |
| Hydra trust grant for the evidence provisioner (exact issuer, exact subject, public JWK, expiry) | baobab-iam, run by an operator | Not registered |
| Delivery keys for signed events at both ends | operators | Not provisioned |

## 2. External dependencies (precise)

1.  A published Hydra release (or an explicitly accepted build) with `oauth2.grant.jwt.omit_assertion_audience` and a proven way to put
    `baobab-erp` in the access token on the `jwt-bearer` path. Decision recorded 2026-10-07: wait for an OSS release; no provider pin changes meanwhile.
2.  ADR-Infra-0025 accepted, which requires verification gates V1 to V8 to be proven in a staging account.
3.  Image references **and digests** for the staging Control Plane, ERP and Hydra (none are selected here; none may be invented).
4.  An AWS staging account and a protected GitHub `staging` environment for apply (docs/runbooks/mp2c-staging-foundation.md preconditions).
5.  The ERP release containing Shared `3433036` deployed **before** the Control Plane release (deployment gate; both ends of event delivery).

## 3. Configuration to set (Control Plane, staging)

| Setting | Value |
|---|---|
| `ERP_PROVISIONING_URL` | ERP's staging HTTPS base URL including `/v1` |
| `ERP_PROVISIONER_ISSUER` | the staging Hydra public issuer, exactly as it appears in the access token |
| `ERP_PROVISIONER_ASSERTION_FILE` | the path where the platform keeps the projected assertion fresh |
| `ERP_PROVISIONER_TOKEN_URL` | the staging Hydra public token endpoint (HTTPS) |
| `ERP_PROVISIONER_CLIENT_ID` | `baobab-cp-provisioning-evidence-workload` |
| `ERP_PROVISIONER_SUBJECT` | the **assertion subject** the Hydra trust grant binds (not the logical client id) |
| `ERP_PROVISIONER_SCOPE` | `erp:provision` (default) |
| `EVENT_DELIVERY_KEYS_FILE` / ERP `BAOBAB_CP_EVENT_INGRESS_URL`, `BAOBAB_CP_EVENT_KEY_ID`, `BAOBAB_CP_EVENT_SECRET_B64` | the same delivery key at both ends (docs in baobab-cp `docs/runbooks/event-ingress.md`) |

Never set `ERP_PROVISIONER_TOKEN_FILE` together with the assertion file, and never create a Keycloak client or a client secret for this identity.

## 4. Acceptance matrix (all rows must pass in one staging run)

Every negative case must fail for the stated reason, not for an unrelated error, and each must also be shown to **pass** in the matching
positive control so the failure is attributable.

**Authorized provisioning**

-   A1. The worker obtains an access token by exchanging the projected assertion; the token's `iss` is the staging issuer, `sub` the assertion
    subject, `aud` exactly `baobab-erp`, `scope` exactly `erp:provision`, `actor_type=workload`, lifetime at most 15 minutes.
-   A2. With a `TENANT_PROVISIONING` Context for an approved plan, `POST /provisioning-operations` is accepted by ERP, the operation reaches a
    terminal state, and the Control Plane converges on ERP's authoritative read.

**Replay and idempotency**

-   R1. Repeating the same request with the same idempotency key returns the same operation; no second operation exists.
-   R2. Redelivering a `provisioning.changed` event is answered as a duplicate and applied once; an out-of-order revision never moves the state back.
-   R3. Replaying a consumed or expired assertion at the token endpoint is refused.

**Rejected**

-   N1. *Wrong environment.* A production-issuer assertion, and a token from the production provisioner, are refused by the staging provider and
    by staging ERP; a staging token is refused by production ERP.
-   N2. *Wrong audience.* A token with `aud=baobab-control-plane` is refused by ERP; so is one carrying the Hydra token endpoint as audience.
-   N3. *Unauthorized.* A token without `erp:provision`; a `RUNTIME` Context for a provisioning operation; another principal's Context; a missing
    or malformed `context_id`; a Context whose plan differs from the request's `control_plane_authority`: each refused as specified in `erp/v1`.
-   N4. *Wrong identity.* An assertion with another subject or issuer, or signed by another key, is refused by Hydra.
-   N5. *No static secret path.* Requesting `client_credentials` for this client is refused; no Keycloak client exists for it.

**Containment**

-   C1. Disabling the Hydra client (IAM `DisableWorkload`) stops new exchanges; a token already issued is shown to expire within its lifetime.
-   C2. Rotating the assertion key (new JWK in the trust grant, then the issuer) works without restarting the Control Plane.

## 5. Evidence to keep

Per row: the request (assertion and tokens **redacted**, claims decoded), the response, the ERP and Control Plane log lines, and the exact image
digests and Shared commit in use. Raw assertions, tokens, delivery secrets and private keys are never stored as evidence.

## 6. Rollback

Stop projecting the assertion and disable the Hydra client. Do **not** introduce a client secret as a fallback: the registry forbids
downgrading a federated entry to a stored secret. The production provisioner `baobab-cp-provisioning-workload` is untouched throughout.
