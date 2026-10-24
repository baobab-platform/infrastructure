# DEV-05 — native CMS, confidential BFF and original NAB-03 cases

Use `BAOBAB_ENVIRONMENT=development python3 -B tests/platform-integration/l4.py
run-cms development` in the integration devcontainer. Source and image locks in
`lock.json` and `cms-lock.json` must be reviewed immutable identities. Package
installation additionally requires a read-only `DEV05_NPM_TOKEN` accepted by
GitHub Packages. Actions supplies its repository package-read token through a
private BuildKit secret; it is deleted after the build and never enters layers,
reports or runtime environments. Local operators supply their own scoped read
credential. No credentials are requested from or sent to a browser.

This addon consumes the DEV-01/02/03/04 lifecycle. It provisions real pinned
Hydra/Kratos/CP, PostgreSQL 17, the actual Payload/Next CMS and the actual Nabhold
Next BFF with TLS Redis encrypted session custody. All services use the owned
private Docker network, no host ports. Only CP's guarded bootstrap creates
canonical tenant, Organisation, synthetic legal, estate, Principal and market
IDs. CMS's maintained fixture CLI receives those real IDs and labels the local
projection unverified; no official legal or provider verification is invented.

## Original case inventory

| Case | Actual observation |
| --- | --- |
| published-home-nav-footer | Genuine CMS scope token, real CP validator/context and Payload PUBLISHED records for all three keys; estate must use canonical RESOLVED capability and fail closed without fallback. PARTIAL/missing provider stays BLOCKED even if direct component HTTP succeeds. |
| wrong-audience-token | Genuine same-client CP-audience token receives CMS 401. |
| wrong-credential | Invalid bearer receives CMS 401 before content. |
| disabled-caller | Native client DELETE/404, issuer inactive and same unexpired bearer CMS 401. This is terminal issuer disable, not a fabricated Hydra enabled flag or CP Principal toggle. |
| expired-caller-token | Actual issuer short lifetime, natural expiry then CMS 401; no JWT editing. |
| revoked-caller-token | Positive control, real native revoke, independent inactive readback, same-token CMS 401 before expiry, fresh-token positive control. |
| missing-grant | Only after a real RESOLVED positive: separate active tenant/context has no grant and CP returns DENIED/GRANT_NOT_FOUND without invocation. An unknown capability cannot pass this case. |
| wrong-owner-or-context | Genuinely separate CP Principal's issued context is refused for the consumer. |
| neighbour-tenant | Exact consumer context with a real neighbour's CP tenant ID receives 403 and no record. |
| draft-or-preview | Actual CMS draft transition; no preview scope gives 403; ordinary lookup must be 200 record:null. |
| withdrawn-content | CMS-owned withdrawal, then ordinary lookup 200 record:null. |
| dependency-outage-and-restoration | Stop real CP; same previously issued context gives CMS 503. Restore CP and recheck actual published home. |
| validator-negatives | Actual CP invalid subject 401/SUBJECT_TOKEN_INVALID and unknown-context CMS 403. |
| teardown | Native clients DELETE/404 and issuer inactive, independent host resource absence, private-state removal and durable final receipt publication. |

The development client rows are checked by the existing Shared registry gate;
old #354/#49 holds cannot veto ADR-043 synthetic development. Token hook and
credentialed introspection edge are closed fixture transports over the actual
issuer. They normalize issuer-produced `ext.actor_type` only, and cannot mint a
token, set active status, invent a CP grant or approve an engine provider.
CP's audience-specific subject verifier and CMS's caller authentication both
recheck issuer status. An issuer read failure is unavailable, not inactive.

The BFF independently executes code/S256/state/nonce and signed ID-token checks,
checks current CP self-authority, writes only encrypted server custody to real
TLS Redis and exposes token-free identity plus a secure opaque cookie. Logout
must revoke server custody even when the old handle is replayed. This is a
native HTTP BFF observation, not a claim of an independently observed browser
UI, protected sign-in, step-up/MFA or production session acceptance.

## Result and custody semantics

`cms_contract.py` preserves all fourteen original IDs. Each case is PASS, FAIL
or BLOCKED with a closed reason; no skip or missing case can qualify. Source
CI green means the expected observed states were verified, **not** that NAB-03
passed. `nab03_qualified` remains false if any case is blocked or failed.
Direct authenticated CMS component results never substitute for the estate's
canonical capability binding/grant path. The current source declaration is
PARTIAL and production_permitted:false; this runner does not promote it, insert
an ACTIVE binding, self-issue certification or invent an invocation descriptor.

`cms_probe.py` checkpoints only closed results and booleans. The host validates
that vocabulary, retains the original final receipt and its SHA-256, and emits
`dev05-cms-suite.json` with exact source/build/config/contract identities.
No tokens, session cookies, callback codes, provider bodies, DSNs, raw build logs,
private package keys or synthetic identity credentials enter custody. Recovery
uses the same labels, deadline/watchdog and two-phase pending receipt publication
as DEV-04; `.pending` is never an artifact. A failed run must still be recovered.

On failure run `recover development --all` in the same checkout/user namespace.
Do not erase the state ledger, edit result JSON, weaken TLS, use product clients
or reclassify missing authority as PASS. Restore source pins to roll back after
owned cleanup. A changed owner source/image/contract requires fresh actual
execution and artifact rehash review. Dated assessments and earlier receipts
remain untouched. Once provider support/real binding are implemented through
normal owner interfaces, rerun the same inventory; Shared accepts the gate only
after all original cases, exact-head review/CI and verified cleanup succeed.
