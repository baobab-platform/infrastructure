# ADR-Infra-0025 --- Projected Workload Assertion Issuer

-   **Status:** Proposed (not Accepted: see section 7, the decision is gated on verification that could not be done when this was written)
-   **Date:** 2026-10-07
-   **Decision Owners:** Baobab Platform Architecture / Infrastructure
-   **Repository:** `baobab-platform/infrastructure`
-   **Supersedes:** None
-   **Related:** ADR-Infra-0006 (production compute), ADR-Infra-0013 (infrastructure IAM and workload identity), ADR-Infra-0014 (secrets, keys and certificates); ADR-IAM-0033 (Hydra owns OAuth/workload issuance, Keycloak remains enterprise federation); Shared `workload-registry.yaml`

## 1. Context

Shared registers some workloads as `credential_type: federated_workload_token`: they hold **no static secret** and present "a short-lived,
platform-projected token". The registry deliberately leaves the mechanism open ("decided by the identity-provider migration ADR"), and
baobab-iam's governed documentation names it as an open infrastructure dependency: *"Infrastructure must provide the assertion issuer and
signing-key lifecycle."* Nothing in this repository provides it today.

The first workload that needs it is the Control Plane's provisioning worker in the **staging evidence environment**
(`baobab-cp-provisioning-evidence-workload`, Shared `70f92ee`, environment `staging`, scope `erp:provision` only). This ADR decides how an
assertion is produced for it and for later federated workloads.

## 2. Requirements (what the consumers actually demand)

These are taken from the consuming code, not assumed.

**Ory Hydra, RFC 7523 `jwt-bearer` grant** (baobab-iam `internal/provider/ory/hydra.go`):

1.  The provider-side client is public (no secret), grant `jwt-bearer`, with a **trust grant** naming one exact assertion **issuer** and one
    exact **subject**, never "any subject", carrying the Shared scopes, an expiry (`TrustTTL`, default 24 h) and the issuer's **public** JWK.
2.  The assertion is a compact JWT signed by that key, addressed to the token endpoint (RFC 7523 section 3).

**baobab-iam token profile** (`internal/tokenprofile`, `scripts/build_workload_token_profiles.py`, merged in baobab-iam#87):

3.  The assertion issuer is an exact `https` URL with no credentials, query or fragment; subject and issuer contain no wildcard.
4.  Two workloads never share an issuer/subject pair; a projection serves exactly one environment (`development`, `staging`, `production`) and
    refuses a workload of another environment.
5.  The access token is issued for at most 15 minutes (`ttl.access_token=15m`).

**Control Plane** (baobab-cp `internal/workloadtoken`, baobab-cp#286, open):

6.  The worker reads the assertion from a file, **re-read on every exchange**, so the platform must keep a fresh assertion in that file
    (rotation without restart).

**Pinned provider limitation** (baobab-iam `docs/operations/ory-workload-token-profile.md`): Hydra v26.2.0 copies the assertion's audience
into the access token. Producing `aud=baobab-erp` needs a Hydra with `oauth2.grant.jwt.omit_assertion_audience`, which exists in Hydra OSS
master but in no published OSS release (the enterprise v26.3.1 changelog documents it). This is independent of the issuer decision below and
is **not** resolved here.

## 3. Boundary with ADR-Infra-0013

ADR-Infra-0013 keeps two identity planes separate: AWS infrastructure identity, and application identity (`baobab-iam`). An assertion issuer
touches both, so the bridge is bounded explicitly:

-   The AWS identity (an ECS task role) proves **which workload is asking**. It never carries application authority.
-   Application authority comes only from the provider's trust grant, the Shared scopes and audiences, and the Control Plane's Context. The
    assertion's issuer and subject are what the trust grant binds; nothing else about the AWS principal reaches the application plane.
-   The issuer SHALL NOT be able to mint an assertion for a subject other than the one its task role is bound to.
-   The staging issuer SHALL NOT be trusted by any production provider, and no production issuer by staging (environment isolation, ADR-0007
    section 102).
-   No long-lived key, secret or access key is introduced for any of this.

## 4. Options

**A. AWS-native outbound identity federation.** The task role calls STS to obtain a short-lived JWT from an account-specific issuer whose
discovery and JWKS endpoints AWS hosts. No signing key or signing service is operated by Baobab; the subject is bound to the role by IAM.

**B. Baobab-operated assertion signer.** A small service signs assertions with an asymmetric KMS key (key custody under ADR-Infra-0014) and
publishes the public JWK at a Baobab-controlled HTTPS issuer URL. The task authenticates to it with its task role (SigV4). More moving parts,
a key lifecycle to operate, and a new service in the trust path, but every property is specified by Baobab.

**C. Reuse GitHub Actions OIDC.** Rejected: the provisioning worker is a runtime service of the Control Plane, not a CI job, and CI identity
must not become a runtime workload identity (ADR-Infra-0013 section 6).

## 5. Decision (proposed)

Prefer **A**, because it removes a signing key and a service from the trust path, **provided every verification gate in section 7 passes in
a staging account**. If any gate fails, adopt **B**. The choice changes where the assertion comes from and who holds the signing key, not
what Hydra, IAM or the Control Plane require (section 2), so the consumers are unaffected by it.

## 6. Scope of the staging evidence environment

In scope here: the issuer decision, its verification gates, the dependency list and the acceptance matrix
(`docs/runbooks/fb05-evidence-environment.md`). Out of scope until section 7 and the provider question are settled: Terraform for the issuer,
and the staging Hydra and ERP services (their images, digests and the Hydra release are not yet selected, and nothing here may apply
infrastructure it cannot validate).

## 7. Verification gates for Option A (open when this was written)

The following could **not** be confirmed from documentation when this ADR was written (the AWS documentation host was unreachable from the
authoring environment). Each is a precondition of accepting A, to be checked against AWS documentation and then proven in a staging account:

  Gate   Question
  ------ ---------------------------------------------------------------------------------------------------------------------------------------
  V1     Is outbound identity federation available in `af-south-1`, and is enabling it account-wide acceptable under ADR-Infra-0002?
  V2     Can an **ECS/Fargate task role** obtain the token, and is the call permitted only for that role (IAM policy, with a condition restricting the audience)?
  V3     Token lifetime: default, bounds, and whether configurable. It must be short and refreshable at least every few minutes.
  V4     Claims: exact `iss`, `sub` (what it contains for a role session; is it stable across task restarts?), `aud` (single string or list; is it the Hydra token endpoint?), `iat`, `exp`, `nbf`, `jti`.
  V5     Signing algorithm and key rotation of the issuer's JWKS, and that Hydra's trust grant (one public JWK) can follow a rotation.
  V6     Hydra accepts the token as an RFC 7523 assertion (required claims, algorithm, audience) in the staging provider.
  V7     The issuer URL satisfies baobab-iam's exact-HTTPS rule (no query, fragment or credentials).
  V8     Subject uniqueness: the evidence provisioner and the production provisioner can never yield the same issuer/subject pair.

An unverified claim is not evidence. Passing V1 to V8 on paper is not enough: they are proven in the staging run.

## 8. Consequences

-   No code or Terraform is added by this ADR. It records the requirement set once, so the issuer, IAM and the Control Plane converge on it.
-   Whichever option is accepted, the evidence environment stays gated on a Hydra release that can issue the resource audience.
-   Accepting this ADR does not accept FB-05: that needs the end-to-end staging run in the runbook.

## 9. Not decided here

The Hydra release (or build) to run; the production issuer; key custody for B beyond ADR-Infra-0014; any change to ADR-Infra-0013.
