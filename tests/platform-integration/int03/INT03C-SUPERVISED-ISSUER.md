# INT-03C supervised issuer readback and revocation: source implementation

**Status:** engineering increment, NOT live INT-03C acceptance. Workload
OAuth only. The mandatory human Kratos/Hydra journey, canonical Principal
deactivation authority, complete seven-case evidence, and independent runtime
teardown remain blocked pending governed disposable fixtures. The canonical
Shared #354 CMS consumer/validator clients remain HELD.

## Runtime authority

- `connected_identity_issuer.py` allows actual TLS-verified discovery only
  for the two reviewed private issuers (`hydra.int03.test` and Keycloak's
  `iam.int02.test/realms/baobab`). It refuses metadata redirects,
  unapproved issuer hosts/ports, unbounded responses and unrecognised
  endpoint families. Issuer configuration is read from its live
  `.well-known/openid-configuration`; no locally fabricated JWT
  can substitute for this step.
- `connected_identity_issuer_run.py` accepts only a private
  development-only plan and two **existing**, distinct, independently
  approved confidential IAM clients. Both exact Shared #354 CMS fixture
  names are excluded. It verifies the actual clean Infrastructure
  source and locked IAM/CP/Shared/CMS/Nabhold source revisions.
  The owner client obtains a short-lived `client_credentials` token;
  the separate verifier client queries the issuer's real introspection
  endpoint and independently confirms active state, client ID, exact
  CP audience, scope and lifetime. Nothing here creates or activates a
  client, grants a Tenant, or mints a canonical CP Principal.
- A successful issuance produces a private 0600 bearer file **outside**
  the evidence directory, and a sanitized, content-hashed
  `issuer-create.json` with source-pin custody. The bearer must never
  be uploaded to Actions or echoed in logs. The output is
  `qualified=false` and `independent_acceptance=false`.
- `connected_identity_revocation.py` requires the *same* unexpired
  token to have succeeded against the CP's real own-Tenant context
  endpoint before revocation. The original owner requests RFC7009
  revocation, an independent issuer verifier observes active→inactive
  **before natural expiry**, and the CP must then deny the same bearer.
  A generic unrelated 403, an expired token, or a provider ACK alone is
  not proof. No action is executed until an authorised operator supplies
  the real approved clients, private credentials and CP-owned topology.

## Necessary further authority (not simulated)

CP's current generic changeset catalogue supports tenant suspension,
market activation, provider activation, release approval, instance
desired release and grants, but **does not provide a governed
Principal-deactivation changeset kind**. This must be addressed in
Shared/CP authority before implementing a Principal status mutation.
Direct SQL changes, hand-modified JWT claims, a fabricated inactive
Principal and reusing the buyer registration path are prohibited.

The current `cms_teardown_witness.py` is specifically bound to the
two *held CMS clients*. Reusing it as proof of removal of arbitrary
INT-03C IAM clients would be false. A new identity-specific independent
issuer/CP cleanup witness must match actual owner IDs and issuer
provider-specific native deletion, reread both issuer and CP after
cleanup, reject active grants or accepting runtimes, and verify original
creation-artifact digests.

**Seven normative INT-03C cases remain unqualified** without approved
actual identities, original evidence for each case, independent
revocation and deactivation, and provider-neutral teardown. Even a
synthetically complete receipt is structurally only
`OBSERVED_UNATTESTED`. The separate fourteen NAB-03 cases remain
BLOCKED until canonical Shared #354 activation.
