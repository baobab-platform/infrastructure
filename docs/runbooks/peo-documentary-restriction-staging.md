# PEO-02T — protected real IAM / CP documentary restriction staging proof

**Current acceptance state: PENDING until an independently reviewed, protected
`workflow_dispatch` runs against deployed CP with genuine IAM credentials.**
A green PR CI run only validates the proof program, not a live environment.

Workflow: `.github/workflows/peo-documentary-restriction-proof.yml`.

## Authority and scope

The proof never writes a documentary restriction, application, Organisation,
tenant, sponsorship, mandate, appeal, legal record or provider state.
It exercises the **read-only** CP PEO-02T private negative-scope assessment
(related CP PR #326) with a real IAM client-credentials token.

Two reviewed fixtures must exist in STAGING before dispatch:

- One currently active, independently governed **synthetic** remediation hold
  for an exact Organisation + `HELD_CAPABILITY` + market.
- One distinct `CLEAR_CAPABILITY` for the **same** synthetic Organisation
  and market with no active remediation hold.
- A current bounded RUNTIME PlatformContext owned by the same authenticated
  CP workload client, attached to the synthetic ACTIVE tenant and PRIMARY
  Organisation. The caller's IAM scope must be
  `documentary:restriction-assess` **and** `context:resolve`.
- CP workload registry must list the client and allow both scopes, and
  `PEO_DOCUMENTARY_SCOPE_CONSUMERS` must explicitly allow its client ID.

Both responses must bind exact context, Organisation, market, capability,
operation reference and current policy, say `authority_granted:false`,
report the expected `blocked` state, and expire within two seconds.
No response ever establishes a positive business grant.

## Protected staging environment

Configure the following under the GitHub **staging** environment with
independent reviewers; do not place secrets in ordinary repository variables.

| Key | Kind | Meaning |
|---|---|---|
| `PEO_STAGING_IAM_TOKEN_URL` | var | Reviewed TLS IAM token endpoint |
| `PEO_STAGING_CP_BASE_URL` | var | Reviewed TLS CP deployment |
| `PEO_STAGING_ALLOWED_HOSTS` | var | Exact comma-delimited HTTPS hostnames; no wildcard |
| `PEO_STAGING_CP_AUDIENCE` | var | Exact registered CP workload audience |
| `PEO_STAGING_CP_DEPLOYED_REVISION` | var | Reviewed deployed CP digest/commit (>=12 chars) |
| `PEO_STAGING_DOCUMENTARY_CONTEXT_ID` | var | Preexisting governed synthetic runtime context UUID |
| `PEO_STAGING_DOCUMENTARY_ORGANISATION_ID` | var | Synthetic tenant PRIMARY Organisation UUID |
| `PEO_STAGING_DOCUMENTARY_MARKET` | var | Exact ISO-2 market |
| `PEO_STAGING_DOCUMENTARY_HELD_CAPABILITY` | var | Exact capability with active synthetic negative hold |
| `PEO_STAGING_DOCUMENTARY_CLEAR_CAPABILITY` | var | Different capability without negative hold |
| `PEO_STAGING_DOCUMENTARY_CLIENT_ID` | secret | IAM client for this controlled test |
| `PEO_STAGING_DOCUMENTARY_CLIENT_SECRET` | secret | Short-lived reviewed secret, never printed |

The guarded job only runs on infrastructure **main**, manual dispatch, after
`confirm_synthetic=true` and approval of the protected staging environment.
It requires TLS trust and denies unreviewed redirect hosts. Its artifact
`peo-acceptance-evidence/cp-documentary-restriction.json` is redacted, contains
no token, and is **PENDING** if any authority or context check fails.

## Independent go/no-go remains separate

This proof establishes only one current CP negative restriction service,
not the Trade/ERP/Payments/Trade Docs point-of-use runtime, evidence attestation,
release from a hold, external provider certification or production availability.
Complete integration, IAM revocation/rotation, provider outages, rollback,
audit review and independent PEO-07 / LA-07 acceptance before production use.
