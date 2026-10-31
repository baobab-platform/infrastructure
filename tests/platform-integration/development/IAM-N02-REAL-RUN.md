# IAM-N02 — Disposable first-party browser/CP execution runbook

**Status (2026-10-31): IMPLEMENTATION IN PROGRESS — NOT ACCEPTED.**
This is a private **development** execution only under EA v2.3 / EA-DEV,
ADR-SHARED-042/043 and current IAM ADRs. It does not activate staging,
production, a canonical provider, legal mandate, customer or Trade buyer
permission. All named PRs remain review-held and unmerged.

## Exact source and ownership gate

The independent N02 **candidate** source lock is
`tests/platform-integration/development/n02-base-lock.json`. It pins
**four** exact independently reviewable owner commits:
Shared #421, CP #455, IAM #147 and ZuriBeans #141. This is distinct
from the accepted three-source DEV-04 `lock.json`. CP #455 pins the
exact Shared #421 commit in both `contracts.lock.yaml` references and
embeds the byte-identical changed workload and scope registries; CP Go
contracts and generated CP console client must pass at that exact head.
A Shared or CP PR change invalidates this candidate lock until updated
and reviewed. The current browser producer, attached original and
pre-deactivation checkpoint must each bind the **same** first-party
ZuriBeans source SHA. Ordinary DEV-04 cases must remain unchanged.

Review the actual role allocation before provisioning:
- **Native browser** `baobab-dev-zuribeans-native-browser-bff`: confidential
  authorization-code + S256 PKCE, exact
  `https://<reviewed-estate>/auth/callback`, `openid trade:buy` scope
  and `baobab-trade` audience. Distinct from the existing Next.js buyer
  `baobab-dev-zuribeans-bff`.
- **Separate CP Principal reader**
  `baobab-dev-zuribeans-cp-principal-validator`:
  `client_credentials`, `identity:principal:resolve`,
  `baobab-control-plane` audience, permitted subject audience
  `baobab-trade`. Shared status is **PROVISIONED**, which grants
  **nothing** until a distinct governed development CP activation and
  principal binding are proven.
- **Kratos human**: an actual synthetic user with real password, TOTP
  enrolment and approved recovery courier. Synthetic user identities
  may not be inferred from email or automatically converted into CP
  Principals. The real exact issuer/subject must link to an ACTIVE
  existing CP human Principal.
- The independent Go IAM BFF is the native browser session and current
  CP Principal boundary, not the existing Next `/api/iam/*` trade login.

## Required actual services before qualification

The ordinary DEV-01/04 base starts real Hydra, Kratos and CP with
private disposable PostgreSQL and native registry. N02 additionally
requires live **same-browser-origin** TLS
`/identity/native-qualification`, ZuriBeans first-party Kratos
`/identity/kratos/login` and `/identity/kratos/recovery`,
`/self-service/*`, `/sessions/whoami`, and native Go `/auth/*`.
Use an explicitly reviewed root and verified upstream certificates;
the Go BFF rejects missing TLS, unexpected Host or origin. Kratos
public self-service and Go BFF must share the same host-only Secure
cookie origin; Hydra issuer is a different HTTPS origin. Do not publish
Hydra/Kratos Admin or CP private credentials to the browser.

The N02 branch includes source-only ingress renderer and NGINX
syntax check, Kratos public origin/UI overlay, actual first-party
Next UI, IAM real private Hydra client controller, source-pinned
Playwright producer and original-evidence reconciler. **These are not
yet an independently deployed, continuously running N02 topology.**
A properly secured first-party listener, real Kratos flow application,
TLS Go BFF vault, PostgreSQL TLS/capability ledger, approved synthetic
Principal, TOTP enrollment, and real recovery courier are mandatory.
The existing base dev Compose has no public N02 browser ingress or
native Go BFF service. Never count static NGINX syntax or its
`DEV-04` legacy IDP/CP check as N02 evidence.

## Two-stage *reserved* development run

Execute in the same Codespaces/devcontainer context used for DEV-04,
with a clean, reviewed Infrastructure checkout and Docker. The first
phase creates a run-owned lease and immutable four-source checkouts,
but does **not** start Kratos, CP, browsers or issue clients:

```sh
export BAOBAB_ENVIRONMENT=development
export BAOBAB_N02_JOIN=development
export BAOBAB_N02_RESERVE_ONLY=true
python3 -B tests/platform-integration/development/ci_int03c.py
# Capture actual N02_PRIVATE_DEVELOPMENT_RUN_RESERVED=<32-hex>.
```

The lease has an independent watchdog. Do not invent, reuse or commit
the nonce. Before its deadline, in the owned `0700` run directory
`tests/platform-integration/.runtime/dev01/<nonce>/`, create a
`0700` private subdirectory, current `0600` real browser JSON
(profile shape in IAM
`tests/browser/n02-profile.example.json`) and client-registration
JSON (IAM `tests/browser/n02-disposable-clients.example.json`).
The client profile and all two confidential credential files, any
CA root, and the `0700` original evidence directory MUST be contained
in that owned private subdirectory. Both profiles must name the same
nonce, current **four** source SHAs, original Infrastructure executable
SHA, and exact first-party origin. Client `expires_at_unix` must be
a bounded current timestamp; never use the placeholder `0`.

Then provision the real private first-party services, TLS trust,
current CP Principal and synthetic Kratos identity through their
owning runtime without opening public Admin ports. The IAM client
controller is invoked **automatically** under the original Hydra
container's authenticated internal network namespace: the pinned IAM
Python source is mounted read-only, its owner-only files remain private,
the actual Hydra client registrations are read back by ID/metadata,
and the original register/verify observations are SHA-bound. The
container cannot claim CP authorization.

Once the real runtime prerequisites are actually available, resume
the same run (NOT a second `prepare`):

```sh
unset BAOBAB_N02_RESERVE_ONLY
export BAOBAB_N02_PREPARED_RUN_ID="<actual-reserved-nonce>"
export BAOBAB_N02_PRIVATE_PROFILE="<absolute-0600-browser-profile>"
export BAOBAB_N02_CLIENT_REGISTRATION_PROFILE="<absolute-0600-client-profile>"
export BAOBAB_N02_ORIGINAL_DIR="<absolute-0700-private-originals>"
python3 -B tests/platform-integration/development/ci_int03c.py
```

This sequence seals the current first-party Kratos public/UI base,
starts real DEV-04 owners, first proves the non-destructive base
claims, registers/reads back native Hydra development clients,
executes real Chromium, records the original pre-deactivation
checkpoint, then performs **all seven** existing destructive INT-03C
cases. The nested `finally` attempts actual client recovery (only
matching run lease) before host Docker teardown. Unknown client
custody, missing browser or a surviving resource remains **HELD**.

## Original receipt and independent evidence

Demand all of the following as distinct original artifacts:
1. owner-private `n02-clients-register.json` and
   `n02-clients-verify.json` plus SHA256 sidecars from real Hydra Admin
   GET/POST/readback, all five source identities and the actual run;
2. original `browser-observation.json` and SHA sidecar from genuine
   Chromium/Next/Kratos/Hydra/IAM BFF/CP navigation (not mocks or
   Playwright API-only), with every seven N02 case marked OBSERVED,
   actual AAL2 readback, real recovery courier, fresh post-recovery
   OAuth and same current CP Principal;
3. original DEV-04 `completed/receipt.json`, original seven
   INT-03C cases with real current issuer readback, pre-deactivation
   browser checkpoint and post-teardown Docker inventory verified
   empty;
4. independent custody of source/image, TLS/ingress configuration,
   native BFF/Next runtime source/registry, Credential and courier
   revocation evidence, provider and CP readbacks, and teardown.

No source-only or self-declared observation upgrades to independent
N02 provider certification. Missing one is **BLOCKED**, not partial
PASS. A failed run's original must remain immutable and must be
recoverable without changing case meaning.

## Review/merge hold

Shared #421, CP #455, IAM #147, Infrastructure #69 and ZuriBeans #141
remain **DRAFT**, with individual final-head CI and independent
architecture/security reviews required. Do not merge until those
checks and the original connected N02 run/teardown meet their
specified development acceptance class. Production/staging and N04
provider support remain separately unapproved.


## Current runnable source guard versus original runtime acceptance

Before any native Hydra client is registered, the runner now performs a
**certificate-verified, proxy-disabled, redirect-disabled HTTPS preflight**
against the current first-party origin. It requires:
`GET /identity/native-qualification` = actual HTML 200;
`GET /auth/session` = real 401 + no-store;
`GET /sessions/whoami` = real Kratos 401;
and Kratos public `/self-service/login/browser` and
`/self-service/recovery/browser` returning real same-origin
`/identity/kratos/{login,recovery}?flow=<uuid>` redirects.
No fake self-reported readiness, untrusted CA, HTTP success, alternative
login RP or unregistered redirect counts as a pass.
Missing services block **before** client creation and before Playwright.

The run-owned Hydra client controller executes on the disposable Hydra
container's private network namespace using the locked Python probe
image, a read-only immutable IAM checkout and a mounted `0700`
owner-private run directory. It performs actual GET/POST/readback and
a separate GET404 verified recovery. Public host Admin ports are
forbidden. A missing Python/git dependency, incorrect runtime label,
unexpected Docker network, or foreign-run registration is a **HELD**
outcome. Source tests only test those denials.

The original DEV-04 **lost-Compose teardown** remains mandatory but
must occur **after** actual IAM client cleanup and original readback.
If a client outcome is unknown, the Compose descriptor remains
available for recovery and host cleanup; no client recovery result may
be relabelled as real prior registration. The watchdog/host inventory
must still verify complete teardown.

This implementation does **not** create the missing full N02 browser
topology: no deployed Go BFF/Next.js/TLS Kratos bridge, no enrolled real
TOTP synthetic user, no functioning real recovery courier or governed
ACTIVE CP caller is evidenced. Until those exact pieces run in an
approved disposable development host with original custody, this
milestone's **connected browser-plus-CP acceptance remains BLOCKED**.
