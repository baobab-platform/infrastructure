# NAB-03 — Connected CMS / IAM / CP qualification runbook

**Status:** engineering source prepared; actual connected run **BLOCKED** by
the canonical Shared #354 activation hold. The two named development-only
identities have not been activated. This file does not lift the hold.

## Preconditions (mandatory, in order)

1. Confirm an immutable, reviewed Shared registry at the exact approved pin,
   with **both** named rows active and all guarded production rows unchanged.
   The existing `cms_gate.evaluate()` must derive `OPEN` from the pristine
   source commit; never manufacture a receipt, use a changed worktree, reuse a
   product credential, or borrow the Pulse exception. The current answer is HELD.
2. Own a completely private disposable runtime with no host management ports,
   independent trust roots, current source and digest-pinned image proofs. A
   connected executor must instantiate the *real* IAM, CP, CMS, PG17 and
   Nabhold processes; no JSON transport substitution qualifies.
3. In an independently supervised IAM lifecycle, create two fresh profiles
   through IAM's maintained native port, with exact separate audiences,
   scopes, owners, service account roles and 60-second maximum token lifetimes.
   Register full-fence cleanup before any issuer mutation. Refuse already
   existing identities and credentials. Set one immutable <=90 minute deadline
   and stop acceptance at that deadline or earlier, including process crash.
4. Provision Tenant, Organisation, market participation, workload Principal,
   grants, provider/release and capability binding using **CP-owned governed
   interfaces**, and verify independent maker/checker and eligibility. CP
   identifiers must be read from the actual APIs; direct SQL/fixture UUIDs,
   locally asserted registration and self-issued certification are unacceptable.
5. Verify `POST /v1/platform-context/resolve` returns the exact fresh,
   expiring Tenant/Organisation/market context and
   `POST /v1/platform-context/validate` accepts the separate registered
   CMS validator with the original caller's actual subject token. The CP
   service issues authority; neither browser nor CMS does.
6. Configure CMS to verify the actual issuer, pinned JWKS, audience and CP
   TLS endpoint, and to acquire the disposable validator's own credential,
   never a static product bearer fallback. Confirm CMS projection ownership
   is CP-attested and does not accept unverified reference declarations.
7. Execute the live cases below, collecting only bounded HTTP method, route,
   status and fixed problem codes. Separately capture issuer mutation API
   read-backs, CP read-backs, runtime image/source pins and cleanup evidence.
   The `cms_nab03.py` assertions only validate expected *semantics* and
   intentionally cannot issue a qualification.
8. Always destroy accepting runtimes, issuer trust/clients, CP grants/context,
   then private secrets/volumes. Independently confirm each fence, including
   on an early exception, cancellation or deadline; retain recovery controls
   until all fences independently pass. Fail closed if any fence is uncertain.

## Normative NAB-03 case inventory

| Case | Actual operation and minimum expected observation |
|---|---|
| published-home-nav-footer | 3 CMS POST /v1/content/resolve calls; 200, exact own-Tenant content keys home/navigation/footer and PUBLISHED |
| wrong-audience-token | Present token cryptographically minted for wrong audience; CMS denies 401 AUTHENTICATION_REQUIRED |
| wrong-credential | Incorrect secret/token; CMS denies 401 AUTHENTICATION_REQUIRED |
| disabled-caller | Disable exact disposable issuer caller, independently confirm issuer state, then deny 401; cannot depend on expired JWT alone |
| expired-caller-token | Wait past independently observed token expiry, reject 401; disallow clock/TTL manipulation |
| revoked-caller-token | Independently prove revocation and accepting runtimes' rejection; deny 401. JWT revocation that remains redeemable is a failed case, never pass |
| missing-grant | Use real token for a Principal without the needed CP grant; CP denies context resolution 403 |
| wrong-owner-or-context | Present CP-issued context belonging to another Principal; CMS rejects 403 CONTENT_CONTEXT_REJECTED |
| neighbour-tenant | Use genuinely separate active Tenant and issuer Principal; no cross-tenant context/content; CMS rejects 403 |
| draft-or-preview | Without preview scope, 403 CONTENT_PREVIEW_NOT_PERMITTED; normal unpublished lookup is empty (200 record:null) |
| withdrawn-content | CMS-owned withdraw then own-context resolution returns 200 record:null |
| dependency-outage-and-restoration | Stop real CP validator route; CMS gives 503 CONTENT_CONTEXT_UNAVAILABLE, restore and re-probe live published home 200 |
| validator-negatives | CP directly rejects incorrect subject token 401 SUBJECT_TOKEN_INVALID; CMS rejects wrong context 403 CONTENT_CONTEXT_REJECTED |
| teardown | Independent read-backs verify every accepting runtime, issuer client/trust, CP topology and secret/volume cleanup |

Each destructive issuer case requires isolated disposable credentials or ordering
that cannot strand subsequent positive cases. The runner must fail the **entire**
test if it has to skip a case, cannot restore a dependency, or cannot prove
teardown. The receipt must carry original immutable evidence links and signed
reviewer/custody information before any separate gate could ever accept it.
Production authorisation is **not** implied by a complete synthetic run.

## Implemented source vs outstanding execution

- IAM #133 native-plan / `RequireNew` and bounded role/read-back foundation:
  implemented and merged; both identities still absent in Shared.
- Infrastructure `cms_lifecycle.py`, `cms_cp_context.py` (PR #41):
  lifecycle and actual CP context HTTP client source; needs independent
  credential provider/CP governed topology orchestration under an OPEN gate.
- Infrastructure `cms_nab03.py`, `cms_nab03_http.py` (PR #42):
  exact 14-case assertion engine and real TLS CMS request adapter;
  unit tests use synthetic observations, not live qualification.
- Remaining: complete live connected executor wiring all side-effect adapters,
  actual issuer/CP maker-checker records and release/binding evidence,
  the canonical registry review/activation (currently HELD), source/image
  requalification on the future exact pins, all 14 actual scenarios and
  independently retained gate acceptance.

Do not switch `qualified` from false, or change CMS
`production_permitted=false`, until the owning authorities separately
approve those outcomes. Nabhold remains a non-trading holding organisation.
