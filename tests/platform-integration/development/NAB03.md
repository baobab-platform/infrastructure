# DEV-05 — native CMS, confidential BFF and original NAB-03 cases

Use `BAOBAB_ENVIRONMENT=development python3 -B tests/platform-integration/l4.py
run-cms development` in the integration devcontainer. Source and image locks in
`cms-base-lock.json` and `cms-lock.json` must be reviewed immutable identities. Package
installation additionally requires a read-only `DEV05_NPM_TOKEN` accepted by
GitHub Packages, plus `DEV05_REGISTRY_USERNAME` for that token's GitHub actor.
Actions supplies its repository package-read token through a
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
| missing-grant | Only after a real RESOLVED positive: the same active tenant/context loses its current entitlement source through the CP owner fixture and CP returns DENIED/GRANT_NOT_FOUND without invocation. An unknown capability cannot pass this case. |
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

## Closed fixture failure diagnostics

The CMS-owned fixture emits `CMS_INT03_STAGE_FAILED=<fixed-phase>` only on
nonzero exit. The Infrastructure harness accepts an exact finite set of stages
(`BOUNDARY`, `REFERENCE_DECLARATION`, `PAYLOAD_INIT`, `PG17_CHECK`,
`ESTATE_PROJECTION`, `CONTENT_SEED`, `PUBLICATION`, `READBACK`,
`DESTROY`) and reports `CMS_FIXTURE_<fixed-phase>`. Unknown or embellished
messages remain `COMMAND_FAILED`. These stage names localize failures without
disclosing SQL, stack traces, provider data, secrets or CP-issued references.
A stage is **not** an acceptance result. Inspect the CMS owner implementation
and its migrations at the *exact pinned source SHA*; fix the owner error rather
than replacing real execution with a stub or promoting blocked cases.

## Native BFF session-custody compatibility

The pinned Nabhold confidential store rejects recovery epochs outside
`^[a-z][a-z0-9-]{0,31}$`. A literal `dev` plus the 32-hex-character
run ID was 35 characters and refused before the OAuth login could start.
The provider now uses lowercase Base32 of the **complete 128-bit** run ID,
prefixed with `dev`, preserving per-run isolation within the strict length
limit. A source regression checks exact shape and last-nibble distinction.
This does not weaken cookie binding, TLS Redis, one-time GETDEL semantics,
issuer checks or session expiry. Closed BFF stage markers isolate any remaining
Kratos/authorization errors without recording credentials or HTTP bodies.

## CMS validator bounded clock qualification

The named DEV-05 CMS validator uses its own actual Hydra client with an
**exact 55-second client-credentials lifetime**, verified by a native issuer
readback. Payload/CMS's maintained token provider still checks current
introspection, issuer, subject, client, single audience, exact scope, actor type,
introspection request timestamp, expiry, immutable run deadline, and a hard
60-second end-to-end maximum. Hydra may sign after access-request time; the
qualifier allows no more than five seconds of nominal timing difference, and
never accepts tokens over the hard 60-second ceiling. Neither source CI green
nor a positive validator token alone qualifies any of the fourteen cases;
actual published-content requests and independent teardown remain required.

## Result and custody semantics

`cms_contract.py` preserves all fourteen original IDs. Each case is PASS, FAIL
or BLOCKED with a closed reason; no skip or missing case can qualify. Source
CI green means the expected observed states were verified, **not** that NAB-03
passed. `nab03_qualified` remains false if any case is blocked or failed.
Direct authenticated CMS component results never substitute for the estate's
canonical capability binding/grant path. The pinned source declaration is COMPLETE with production_permitted:false. CP
registers and activates the provider through its normal release, maker/checker,
OCI manifest and TLS readiness checks, then admits an expiring TRIAL subscription,
composition grant and binding. This development proof confers no certification
or protected-environment permission.

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

Actions concurrency is scoped to ref plus exact commit. Each candidate owns a
fresh runner and nonce-labelled private services; duplicate events for one
candidate serialize. A superseded setup cannot block execution of its corrected
revision. No candidate is accepted without its own final checks and teardown.

Hydra v26.2.0 client TTL fields use `x.NullDuration` (`x/sqlx.go`), whose
JSON serializer calls Go's `time.Duration.String()`. Therefore requested `60s`
reads back as `1m0s`; the validator's `55s` remains `55s`. Client provisioning
checks those exact native representations and rejects missing or changed TTLs.
The `ISSUER_CLIENTS` and `CMS_SCHEMA` phase markers distinguish client readback
from database preparation without exposing captured commands or provider data.


## Current governed content qualification

The current pins join CP #443, CMS #51 and Nabhold #95. CMS resolves the actual
caller's fresh CP capability authority before native reads and requires a durable
Payload allowed-read audit before returning content. The BFF uses the exact CP
and CMS resource audiences, current context and the fixed content/v1 route.

The original fourteen-case inventory is unchanged. After published content is
visible through the estate, CP's owner withdraws that same tenant's grant; direct
CMS access must deny, the estate must expose none of the published markers and
the native allowed-read audit count must not increase. A fresh grant restores
content. The host independently joins the native audit's resolution, context,
correlation, grant, binding, provider and instance to CP's stored RESOLVED decision.

CI refuses qualification unless every original case passes, runtime identities
match, all seven bound-path observations pass and teardown independently proves
owned resource and private-state absence. The final receipt retains the actual
CMS OCI manifest digest and immutable source/configuration identities. Stale
suite/report success is cleared before preparation; failures still require cleanup
and remain failures. DEV-06's unchanged eighteen cases rerun against the same CP
refactor using its separate external-client profile.

The BFF receives the same CP-issued synthetic LegalEntity selector as the CMS
fixture and direct probes. DIGITAL_ESTATE records carry that scope dimension;
omitting it correctly resolves no matching content. This selector only chooses
content within already validated tenant/Organisation authority and grants no legal
mandate. The estate's exact-scope checks and disabled fallback remain unchanged.

CP-supplied Market fixtures declare native MARKET scope (CMS #52), so the
estate's configured Market selector receives EXACT content without accepting
estate-wide fallback. Fixed development workload diagnostics distinguish token,
context and capability failures before cleanup; only the closed classes leave
private runtime logs.

The additional withdrawn-grant control requires GRANT_REVOKED. It cannot mark
the original missing-grant case PASS. The owner then separately removes the
run-owned current entitlement source, and the unchanged missing-grant case
requires DENIED/GRANT_NOT_FOUND with no invocation, native CMS 403, absent
estate markers and no new allowed-read audit. Normal owner restoration must
recover published content and independently matching native audit afterward.
