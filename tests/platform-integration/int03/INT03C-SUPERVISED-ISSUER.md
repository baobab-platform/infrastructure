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
  approved confidential IAM clients. Only Shared #366 names `baobab-int03c-issuer-owner` and
  `baobab-int03c-issuer-verifier` are eligible; both held Shared #354 CMS names
  are excluded. It verifies the actual clean Infrastructure
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

CP #427 is merged at `bcea71bd9909be3672dfcb7ce78d04d6feb0e748`.
Its default-off, nonproduction Principal provenance and deactivation routes
require two existing ACTIVE authorised human operators, a separately governed
ACTIVE workload Principal and exact external linkage, immutable source/run
provenance and digest-bound approval. The routes create neither the target
Principal nor its external link. Their source/PG regression is not live
qualification. Direct SQL, fabricated JWTs or an inactive fixture remain
prohibited. IAM #137 is separately merged with native-client and deadline
watchdog safeguards; actual supervised runtime shutdown still needs proof.

The current `cms_teardown_witness.py` is specifically bound to the
two *held CMS clients*. Reusing it as proof of removal of arbitrary
INT-03C IAM clients would be false. A new identity-specific independent
issuer/CP cleanup witness must match actual owner IDs and issuer
provider-specific native deletion, reread both issuer and CP after
cleanup, reject active grants or accepting runtimes, and verify original
creation-artifact digests.

## Canonical registration and independent original-byte custody

The operator must provide an **actual clean Shared checkout** at the exact
`int03c-lock.json` Shared SHA. Both CP and issuer observers use that separate
lock, never `cms-lock.json`. The exact Infrastructure execution SHA must match
its clean checkout and descend from the lock's merged Infrastructure baseline;
fetch the full reviewed history, because missing ancestry is refused.

`verify_governed_workloads()` pins both complete canonical Shared #366 rows:
ACTIVE development-only `client_credentials`, Infrastructure ownership and
rotation, CP audience, and **only `context:resolve`** for both clients. The
verifier has no `context:validate` privilege; its independent OAuth
introspection permission is governed by IAM. A free-form approval digest or
provider client is not independent approval. Infrastructure #49 remains an
approval request: named independent approval of exact sources/images, topology,
run window, CP operators, private credentials, external deadline supervisor and
immutable evidence custody must precede live issuance. Do not borrow Pulse or
HELD CMS clients, create Principals directly or execute from a locally edited
registry. `inspect` is input review, not authority or source/runtime qualification.

`connected_identity_seven_case.py` re-opens the sealed original
seven-case evidence bundle, including issuer-create, CP Principal,
wrong-audience, second Tenant, issuer revocation, Principal deactivation
and independent teardown proofs. Every digest must refer to the precise
original file; exact SHA-40 source pins and closed problem/status codes
are checked again. It returns `candidate_structurally_complete` only
as a source-level, unqualified result. Local hashes do **not** establish
external immutable storage or independent acceptance.

`connected_identity_teardown.py` provides an independent, read-only
post-cleanup witness. The reviewer must verify the original sealed
creation-artifact bundle at exact source pins, provider-native absence
of both reviewed IAM clients, terminal CP synthetic resources, a
**CP-owned** Principal status read-back by a distinct checker, no owned
Docker resources/images, and no surviving private credentials. There
is no automatic cleanup call, and no replacement of an unavailable
Principal status endpoint with a fabricated record. Test doubles exercise
guards only; they are not proof of actual teardown.

**Seven normative INT-03C cases remain unqualified** without approved
actual identities, original evidence for each case, independent
revocation and deactivation, and provider-neutral teardown. Even a
synthetically complete receipt is structurally only
`OBSERVED_UNATTESTED`. The separate fourteen NAB-03 cases remain
BLOCKED until canonical Shared #354 activation.
