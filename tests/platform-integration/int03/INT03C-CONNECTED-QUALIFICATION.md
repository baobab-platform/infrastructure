# INT-03C — connected IAM/CP identity and negative-control qualification

**Engineering status:** governed probe source implemented on Infrastructure
PR #46. This does **not** establish live acceptance. Provider credentials,
independently approved CP synthetic topology, issuer/CP mutation read-backs,
actual 7-case evidence, and full teardown are not present in this branch.
Shared #354 is still HELD: neither CMS fixture client may be activated
through this workflow. All fourteen NAB-03 cases remain BLOCKED.

## Architectural ownership

- IAM owns issuer authentication, native human/workload credentials, token
  issuance and revocation. Runtime evidence must establish that the bearer
  was minted by the actual issuer, the exact audience, expiry and current
  issuer state; a locally signed JWT or changed clock is not evidence.
- CP owns canonical Tenant, Organisation, Principal, market participation,
  legal entity, context, grants, provider certification and capability binding.
  A UUID in a test file is only an *assertion* until independently read back
  through CP-owned governed APIs; no direct SQL or self-certified topology.
- Infrastructure owns the private trust boundary, source/image custody,
  per-run nonce and independent cleanup witness. A Docker Compose cleanup
  success message is not proof all accepting runtimes or CP grants are gone.
- Neither this work nor standalone IAM/CP qualification may activate the
  two Shared #354 CMS identities, enable production access, or mark NAB-03
  accepted. INT-03A/B's frozen Keycloak smoke does not automatically qualify
  the separate native Ory Kratos/Hydra protected path.

## Seven required evidence dimensions

| Case | Live authority and minimum proof |
|---|---|
| iam_issued_token | IAM issuer/client independent configuration and token issuance GET or introspection, signed source/issuer evidence and unexpired exact audience |
| cp_current_principal | ACTIVE canonical workload Principal and original IAM issuer/subject linkage from independent CP-owned read-back; human `GET /v1/admin/effective-authority` alone is insufficient |
| wrong_audience_denied | A **real IAM-issued** token for an independent wrong audience is denied by authenticated CP `POST /v1/platform-context/resolve`; no arbitrary 403 counts |
| cross_tenant_denied | Real own-Tenant token succeeds for an ACTIVE Tenant/Organisation/country context but CP refuses a *separate CP-governed active* neighbouring Tenant |
| revoked_credential_denied | IAM independently confirms revocation of a previously live token **before natural expiry**, then CP refuses reuse; an expired token alone is not revocation proof |
| deactivated_principal_denied | CP independently reads back a deactivated Principal and refuses its otherwise valid credential; issuer failure alone is not CP deactivation proof |
| independent_teardown | Different operator rehashes original issuer/CP/runtime create proofs, observes actual Hydra client and CP-resource removal or terminal inactivity, accepting runtime and built-image removal, and no private secrets |

The source contract `connected_identity_evidence.py` describes these
as `OBSERVED`, `BLOCKED` or `FAILED`; it deliberately cannot record
`PASS`, `qualified=true`, or `nab03_qualified=true`. Even a
structurally complete candidate remains `OBSERVED_UNATTESTED` until an
independent reviewer retrieves and validates every original immutable
artifact. A self-reported `live` Boolean cannot count as authority.

## Real CP HTTP probe

`connected_identity_cp.py` uses Python's TLS verification with the
private disposable CA and allows only `cp.int02.test` /
`cp.int03.test`. It blocks redirects, host/port changes, unregistered
routes, open-ended response bodies, unrecognised CP problems, URLs or
credentials in logs.

`connected_identity_cp_run.py inspect --plan /private/plan.json`
validates the private input but makes **no network requests**.
`probe --plan /private/plan.json --out /private/new-evidence` may run
only once real approved development-only tokens and canonical CP-owned
Tenant/Organisation/Principal IDs are available. The plan is a 0600 JSON
file inside a 0700 owner-controlled parent, using:

```text
schema: infrastructure.int03c.cp-observer-input.v1
environment: development
run_id: 32 independently generated lowercase hex characters
sources: immutable 40-hex source pins for shared, infrastructure,
         baobab-cms, baobab-iam, baobab-cp and nabhold
cp_origin: https://cp.int03.test
ca_file: private disposable CA bundle path
tenant_id: actual canonical CP UUID
neighbour_tenant_id: distinct actual active CP UUID
organisation_id: actual canonical CP UUID
country_code: ZA or UG, matching reviewed CP market
organisation_kind: ORGANISATION, BUYER_ORGANISATION or SUPPLIER_ORGANISATION
human_principal_id: existing ACTIVE CP canonical UUID
tokens: owner-private file paths for human, workload, wrong_audience,
        revoked and deactivated (no token values in the plan)
```

Do not invent or paste secrets into tracked documentation. The runner
requires the **actual clean Infrastructure git revision** and the
reviewed IAM/CP/Shared/CMS/Nabhold `int03c-lock.json` pins, distinct
issuer tokens and actual nonexpired CP organisation/context readbacks.
The exact execution SHA must descend from the lock's merged Infrastructure
baseline. Use full clean history containing that baseline; a shallow checkout
without it is refused. The default CMS lock's registry hold is unchanged.
Infrastructure #49 must separately authorise the exact sources, host/network,
image digests, run window, distinct CP admins, private credentials, external
supervisor and immutable evidence custody before any probe or issuer request.
`inspect` validates input shape only and grants no permission to run.

The runner records fixed route/method/status/problem codes only, without
retaining token bodies, headers or CP Principal details, and seals all
original sanitized case files and the receipt using the merged
`cms_evidence.py` content inventory. A locally hashed file is
**not** immutable external storage until independently uploaded to
approved retention custody and downloaded/rehashed by the reviewer.

It deliberately leaves `iam_issued_token`, `revoked_credential_denied`,
`deactivated_principal_denied` and `independent_teardown` BLOCKED.
The last two negative HTTP responses, if actually seen, are preserved
only as **transport observations**. They cannot become genuine revocation
or deactivation cases without independent issuer/CP readback, token expiry,
supervised mutation, original SHA-256 proof, and post-operation denial.
No CLI option can override this boundary.

## Engineering still owed

1. Exact disposable native Hydra/Kratos service and CP governed topology
   with two independent human reviewers, approved AdmissionDecision,
   ACTIVE Principal and market, current eligible grant/binding and
   independent provider certification; retain actual CP-generated IDs.
2. Separate real IAM issuance/introspection bridge for INT-03C, including
   independent token issuer/subject/audience and bounded expiry evidence.
   IAM #135's development-only CMS native bridge cannot be reused while
   Shared #354's two named CMS identities remain HELD.
3. Supervised issuer revocation and canonical CP Principal deactivation,
   *without* reusing the same token for multiple negative assertions,
   proving both before natural token expiry with real CP denials.
4. Full seven-case runtime observation, source/image/digest custody, 90-minute
   deadline, distinct issuer/CP/acceptor cleanup, and independent reviewer.
5. Separately authorised CMS connected NAB-03 14-case run after canonical
   registry activation. A successful INT-03C run does not waive NAB-03.

Test commands from the Infrastructure repository checkout:

```bash
python3 -B -m unittest discover -s tests/platform-integration/int03 -p 'test_connected_identity*.py' -v
python3 -B -m unittest discover -s tests/platform-integration/int03 -p 'test_*.py' -v
```

The INT-03 source/security workflow already discovers these tests. It does
not run the private live probe without approved credentials and reviewed
topology.
