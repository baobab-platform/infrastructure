# INT-03A — private Nabhold identity-smoke handoff

**State: INT-03A prepares private inputs; INT-03B implements their connected
identity lifecycle. Only verified per-run receipts at reviewed exact pins can
establish a scoped identity-smoke result. Full INT-03 remains OPEN until the
complete mandatory matrix and independent acceptance requirements are met.**
Authority: Accepted ADR-SHARED-036, EA v2.3 P0-A (retaining the v2.2 L4 matrix), Nabhold Go-Live
v2.0 P0-04/P0-06/P0-07, ADR-NAB-0004/0014 and IAM ADR-IAM-0033.

INT-02's merged Keycloak/CP/Pulse proof is recorded in Shared's
[qualification register](https://github.com/baobab-platform/shared/blob/main/docs/architecture/int02-pulse-qualification-register.md).
It does not establish the separate C4-03 protected Kratos/Hydra→CP journey,
C4-04B/C activation/consumption, Nabhold identity smoke, CMS or staging.

`handoff.py` prepares inputs for Nabhold's existing
`keycloak-identity-smoke` consumer. It generates a distinct random confidential
client secret, Redis password, AES key and recovery epoch for each bundle.
It never connects to IAM/CP, provisions a Principal, verifies a supplied UUID,
grants tenant access, activates a product client, starts services or emits a
PASS receipt. Expected Principal/source values are **unverified declarations**.
Its manifest explicitly withholds identity verification, runtime attestation,
protected staging and production authorisation.

## Prepare a bundle

Use a clean, reviewed IAM checkout including the Nabhold `basic` subject-scope
repair ([IAM #127](https://github.com/baobab-platform/baobab-iam/pull/127)). The
helper rejects the older template rather than silently fixing the owning
repository's profile. The product `nabhold-executive` client remains disabled.
The separate generated `nabhold-int03` fixture has no role mapper, optional
scope, service account, password grant or authentication-flow override. It
has only code/S256, the exact lab callback and CP human self-read defaults.
During disposable Keycloak provisioning only, the runner adds and independently
reads back one exact client-dedicated audience mapper for `nabhold-int03`.
Keycloak 26.7 checks that the confidential introspecting client is included
in the access token's `aud` claim; the existing `authority:self` scope retains
`aud=baobab-control-plane` for CP. This additional self-audience does **not**
add a role, Tenant membership, business entitlement, new optional scope, or
permission to use a token at another resource. The dormant product client
remains disabled and unchanged. **Product IAM client-audience convergence and
protected-provider approval remain outstanding**; a synthetic fixture alone
does not prove them.

Create an **owner-private 0700 parent directory**, then a 0600 JSON input with
exactly these keys (placeholders intentionally cannot pass):

```json
{
  "synthetic": true,
  "sources": {
    "infrastructure": "ACTUAL_FULL_COMMIT",
    "baobab-iam": "ACTUAL_FULL_COMMIT",
    "baobab-cp": "ACTUAL_FULL_COMMIT",
    "shared": "ACTUAL_FULL_COMMIT",
    "nabhold": "ACTUAL_FULL_COMMIT"
  },
  "principal_id": "EXISTING_MAPPED_SYNTHETIC_CP_UUID",
  "username": "l4-int03-human",
  "password": "PRIVATE_DISPOSABLE_HUMAN_PASSWORD",
  "ca_file": "/absolute/path/to/disposable-lab-ca-bundle.pem"
}
```

The disposable non-admin human must be registered in the real issuer and
independently mapped to an ACTIVE CP human Principal. No real director, client,
enterprise records, production credentials or protected-staging identity may
be used. Protect all input/template/output parent paths from concurrent edits.
The CA bundle must contain only the disposable lab's public CA certificates;
never a signing key. Its PEM envelope is checked here; Nabhold additionally
checks X.509 CA extensions before launch. Only the real connection establishes
trust in the actual issuer, CP and Redis certificates.

```bash
python3 tests/platform-integration/int03/handoff.py \
  --inputs /absolute/private/int03-input.json \
  --iam-template /absolute/reviewed/iam/config/clients/nabhold-executive.json \
  --output /absolute/private/new-int03-run
```

Each new output contains one atomically published `prepared` directory:

| File | Use |
|---|---|
| `integration.env` | Nabhold's existing private dotenv handoff; do **not** shell source |
| `client.json` | Input for authorised provisioning of the disposable confidential client |
| `users.acl` | Hashed-password Redis ACL limited to this run's exact session epoch |
| `ca.pem` | Public disposable CA bundle copied into its final absolute location |
| `manifest.json` | Explicit `PREPARED_NOT_PROVISIONED` metadata, never an acceptance record |

All files are 0600 inside 0700 directories. Existing destinations, symlinks,
hard-linked inputs, FIFOs, insecure modes, oversized/duplicate JSON, extra
template privileges and floating source refs are refused. Partial generation
is removed. No credentials, URLs, identities or paths are printed on failure.
Never upload these files to Actions artifacts or commit them. Keep generated
bundles under ignored `.runtime` if inside this repository. The preparer owns
no active services; its cleanup never tears down an external environment.

## Connected execution responsibilities — INT-03B

The generated bundle is **not runnable by itself**. The Infrastructure-owned
connected lifecycle must provide and verify:

1. An actual pinned private lab and independently observed source/image
   identities. Keep the existing qualified INT-02 lock/evidence unchanged.
   Requalify affected base assertions for changed engine pins.
2. Dedicated `nabhold.int03.test` HTTPS routing, the existing verified
   `iam.int02.test` and `cp.int02.test` origins, and actual TLS Redis at
   `redis.int03.test:6379`. No management or database host ports. The new edge
   and Redis certificates must be issued by the supplied disposable CA bundle.
   Install the CA in Chromium's NSS trust store too; no TLS bypass flags.
3. Authorised fixture provisioning, current CP external-identity mapping and
   isolated non-admin human credentials. No `cp:platform-admin` role is needed
   for `authority:self`. The client profile is not a business entitlement.
4. Redis TLS-only transport and the generated `users.acl`. Mount secret files
   privately under the service UID. Disable the default Redis user; never use
   a wildcard namespace or `+@all`. BFF ciphertext/session storage is distinct
   from an engine database. The helper's ACL grants only SET/GET/GETDEL/DEL and
   the documented node-redis handshake, not administration or scripting.
5. Run Nabhold from a clean actual checkout using the existing launcher. Keep
   the exact absolute bundle paths valid in every process that reads them:

   ```bash
   export NABHOLD_INTEGRATION_ENV_FILE=/absolute/private/new-int03-run/prepared/integration.env
   pnpm integration:check
   pnpm dev:integration
   # In another terminal on the same private network:
   pnpm test:e2e:integration
   ```

6. Verify and retain only the **sanitized observation receipts**, bind their
   declared dependencies to actual runtime sources/images, and prove teardown
   of all disposable services, identities and private files. A configuration
   check, a prepared manifest or local checksum does not supply that proof.

The recently merged Nabhold/ZuriBeans/Thamani/Shared/CP Codespaces settings
solve their image/package bootstrap lane; they do not attach five independent
Codespaces to this private network or provide IAM/CP registrations. Reuse the
Nabhold Node 24/pnpm 11.24.0 baseline and approved package-read permissions;
never bake registry tokens into images or put them in the BFF environment.

The Keycloak compatibility smoke does not close native Ory qualification. Full
INT-03 additionally needs IAM revocation/CP deactivation negatives and real CMS
published/preview, binding/context and publish/unpublish assertions. ERP F1,
Subscriptions production billing, legal evidence and protected staging retain
their own authority and acceptance gates. Nabhold remains non-trading.

## Source verification

```bash
python3 -m unittest discover -s tests/platform-integration/int03 -p test_handoff.py -v
```

Twelve source/security tests exercise private-file refusal, atomic publication,
fresh secrets/ACL epochs, exact dormant-template cloning, source pin checks,
secret-free errors and actual Node dotenv/CA/key interoperability. They run in
the existing mandatory INT-02 source job. The existing live job still proves
only its original IAM/CP/Pulse profile. Rollback: revert this preparer, stop any
separately provisioned disposable lab under its owning lifecycle, and destroy
unneeded private bundles; retain sanitized evidence under its original scope.


## INT-03B connected identity runner

`run.py` now owns an actual disposable lifecycle, unlike `handoff.py`. It loads
its separate `lock.json` and `prerequisite-lock.json`, imports the unchanged INT-02 implementation in an
isolated module/session, and overlays `compose.yaml`/`edge.conf`. The frozen
INT-02 lock is never edited. Selected current IAM/CP/Shared pins are requalified
through the complete existing IAM/CP/Pulse suite before Nabhold is tested.
That requalification is a new run, not inheritance of prior acceptance.
The qualifier hashes its own prerequisite file so that the recorded source
pins and manifest digest agree, rather than hashing the old frozen lock.
The integration devcontainer feature lock is now committed (Docker-outside-of-
Docker 1.10.1, resolved OCI digest from the pinned CLI's actual registry query);
CI uses `--frozen-lockfile`. Earlier attempts stopped because the CLI generated
an untracked lockfile. The clean-source requirement remains strict.

The profile builds the exact Nabhold checkout on its approved immutable Node
24/pnpm 11.24.0 browser image. Git metadata is retained so the existing consumer
independently checks its clean source revision. Package-read authentication
arrives through private stdin, is consumed by a BuildKit secret/tmpfs npmrc,
and is blanked before services start. Temporary GHCR Docker authentication is
removed after build. No registry credential becomes a runtime environment
variable, application mount, image layer or artifact. A package ACL/registry
failure blocks the run; it never substitutes local Shared packages or mocks.

A new non-admin synthetic `l4-int03-human` and `nabhold-int03` client are created
through real Keycloak administration. The product client stays disabled. The
issuer-generated subject is explicitly mapped to a new ACTIVE CP human in this
throwaway DB; no administrative/business grant or Tenant membership is added.
This SQL is a synthetic fixture boundary, never a protected registration recipe.
The private issuer additionally verifies the exact self-audience mapper on
the disposable `nabhold-int03` client. Failure to observe it blocks the run
before browser assertions. It is the minimum Keycloak 26.7 introspection
compatibility requirement, and is deliberately not a production IAM template
change or an acceptance assertion about native protected C4.

The edge and TLS-only Redis have distinct per-run leaf keys under one temporary
CA; the signer is destroyed before launch. Nabhold mounts only its prepared
handoff, Redis only its leaf material and namespace ACL. Chromium gets NSS trust
and Node gets the verified CA file; no certificate-ignore settings are used.
Actual running image configuration IDs are checked against built images and
recorded explicitly as **config IDs, not OCI manifest digests**. Source checkouts,
the running estate Git revision and consumer-declared pins are checked separately.

Run the same entrypoint inside the integration devcontainer or an equivalent
Docker-capable local runner, from a clean reviewed Infrastructure checkout:

```bash
python3 -B tests/platform-integration/int03/run.py preflight
printf '%s\n' "$BAOBAB_PACKAGES_READ_TOKEN" | \
  INT03_REGISTRY_USERNAME="$GITHUB_USER" \
  python3 -B tests/platform-integration/int03/run.py run --package-token-stdin
# Retry an interrupted cleanup without supplying a registry token:
python3 -B tests/platform-integration/int03/run.py down
```

Use the existing approved read-only package token/user; do not create a broader
credential. The Actions workflow uses its repository token with contents/package
read only, private stdin and the existing integration devcontainer. Repository
package/image access still needs to be granted by the owning GitHub package;
a 403 is a blocker, not authority to broaden permissions automatically.

`*-int03-identity/completed/receipt.json` and its paired digest contain only fixed scenario outcomes,
source/image identities, an original consumer-receipt hash and a fixed failure
stage/class, finite prerequisite browser failure facts, and fixed HTTP route/method/status
observations. Query strings, headers, cookies, bodies and raw URLs are excluded.
No raw Docker/Keycloak/Next/Playwright logs or fixture files are
uploaded. A smoke PASS requires all four NAB-ID cases, observed runtime pins and
successful resource/image/private-file cleanup. A failed teardown preserves
recovery handles and cannot leave `passed=true`. Interrupted runs require the
independent cleanup step, with label-scoped host recovery if the devcontainer
is unavailable; host recovery never grants qualification. Missing evidence
cannot establish a pass.
When browser execution fails, its actual nonzero exit and closed per-case
PASS/FAIL/BLOCKED projection are retained; raw browser errors remain suppressed.

This smaller identity profile does **not** accept NAB-01–04/full INT-03. CMS
qualification/binding, published/preview and mutation/denial tests, the remaining
revocation/Principal-deactivation/session-negative cases, protected native C4,
legal onboarding, staging and production retain their own gates. Nabhold remains
non-trading; human `authority:self` is never promoted into executive authority.

The connected handoff enables Nabhold's explicit trusted-proxy setting. Its
private TLS edge overwrites Host, X-Forwarded-Host and X-Forwarded-Proto; Nabhold
has no published host port. The app validates both authorities and exact HTTPS
against its configured public origin before reconstructing the callback URL,
including removal of the private listen port. This is an ingress transport
contract, not permission to trust arbitrary forwarded headers or bypass Origin,
PKCE, IAM introspection, CP identity or session custody checks.


The current Nabhold pin includes the callback completion-document correction
under Nabhold #80. Its real browser case requires an HTML 200 completion
document before account/session/logout assertions, ending the cross-site
redirect chain without relaxing Strict session cookies. Candidate source
execution does not establish merged-source or release acceptance. Before this
Infrastructure PR merges, verify the pinned Nabhold commit is reachable from
its reviewed main history and the exact pinned connected run passes; preserve
that commit with a normal reviewed merge rather than changing a qualified pin.


Nabhold #81 additionally uses a same-origin account referrer policy so native
logout submits the exact Origin required by the existing handler. Protocol
routes retain no-referrer. Missing/null/foreign Origin and invalid CSRF remain
denied. The actual browser must observe exact Origin and logout 303, then prove
server custody revocation with the prior opaque handle. These assertions cannot
be replaced by callback/account/session success or a source unit result.

## INT-03 CMS — registry gate (NAB-03 BLOCKED)

Accepted Shared #354 ([decision](https://github.com/baobab-platform/shared/blob/main/docs/architecture/int03-cms-proof-bootstrap-proposal.md))
lets exactly two named development identities produce synthetic CMS evidence:
`baobab-int03-cms-consumer` (owner Infrastructure) and
`baobab-int03-cms-validator` (owner CMS). They can authenticate only after a
reviewed change adds them to the canonical workload registry. The platform
owner's no-registry-activation hold keeps them out, and Shared #356, which
proposed them, was closed unmerged. **Every connected NAB-03 case is therefore
BLOCKED.** Nothing here provisions, borrows or synthesises either identity.

`cms_gate.py` reads the unmodified registry at the Shared commit locked in
`cms-lock.json`, refusing any other commit or a modified file, and writes
`cms-gate-receipt.json` with its SHA-256:

| Verdict | Meaning | Job |
| --- | --- | --- |
| `HELD` | Neither named row is present; the hold is in force | passes |
| `REFUSED` | A named row differs from #354 field for field (any extra or widened field included), only one of the two is present, a row is duplicated or unparseable, another `baobab-int03-cms-*` row appears, or `nabhold-backend` / `baobab-cms-workload` changed | fails: registry defect |
| `OPEN` | Both rows match #354 exactly | fails: the connected CMS lane is now owed |

In every verdict all 14 NAB-03 cases are `BLOCKED`, `identities_created` is
false and `qualified` is false. The case keys refine the normative NAB-03
scenario (Shared `ea-v2.2-integration-acceptance-matrix.md`) and are not new
normative IDs. Only a connected run's own scenario-complete receipt, under
#354's lifecycle, deadline and teardown rules, can report
`QUALIFIED_SYNTHETIC_RUN`.

```bash
python3 tests/platform-integration/int03/cms_gate.py \
  --shared /absolute/shared/checkout/at/locked/commit --out /absolute/output
```

CI runs it as the `cms-gate` job, which needs `source` and retains the receipt
as `int03-cms-gate-receipt`.

Registry parsing uses pinned PyYAML 6.0.3 with duplicate-key and alias refusal. Quoted keys and block/flow syntax cannot hide a named identity; duplicate top-level workload sections refuse. Registry and decision evidence bytes are read from immutable committed blobs, with working-tree changes separately refused. These checks still grant no identity and leave every connected case BLOCKED.


## Actual CMS/PG17 component preparation while the registry is held

`python3 -B tests/platform-integration/int03/cms_provider.py run` source-builds
CMS using its reviewed production Dockerfile and locked Node 24 base. The build
stage supplies explicit committed migrations and the bounded CMS fixture CLI;
the standalone unprivileged runtime serves actual HTTP. PostgreSQL 17 uses a
locked image and isolated project-owned disposable volume; no service publishes
host ports. The network is private, and no IAM caller, validator, token or CP
identity is fabricated. The named registry identities remain held.
This standalone pre-gate command requires `HELD`; `OPEN` or `REFUSED` refuses
before any container is built or started. A later connected command can reuse
the composition without treating this held-only component as qualification.

The job verifies exact clean CMS/Shared checkouts, source and package-lock hashes,
built tool/migration file hashes, actual migration-table readback, runtime image
content IDs/source labels, Node/npm and PostgreSQL versions. It runs idempotent
seeding, restart verification and CMS-owned fixture publication, withdrawal and
draft restoration. HTTP proves liveness, actual DB readiness, anonymous/malformed
authentication denial and the unconfigured identity path's fail-closed 503. It
also proves actual database outage/readiness failure and recovery. Those component
observations do not prove IAM/CP authorisation, human editorial approval or any
connected acceptance case.

A private recovery handle is created before resource allocation. Success, failure
and SIGINT/SIGTERM use the existing INT-03 ownership-label destruction strategy,
which also works if the Compose environment/source or database is unavailable.
The workflow always retries `cms_provider.py down`. It verifies no owned container,
network or volume remains, removes the two per-run image tags and private files,
and publishes receipt plus independently hashable SHA256 file atomically only
after teardown. A failed cleanup never yields component PASS.

Cleanup attempts all validated owned resources even if one removal fails, then
retains the private recovery handle and fails; the next `down` can retry. A lost
handle is restored from the running process's known owner before recovery.
Shared base images and build cache contain only public source/dependencies and are not per-run trust
or data. No credential is supplied during image builds.

The receipt is `ACTUAL_CMS_PG17_COMPONENT_SYNTHETIC_DATA`, qualified=false. **All
fourteen NAB-03 connected cases remain BLOCKED**, including the connected teardown
case; this component's own teardown result is recorded separately. The source,
health and fixture checks cannot replace actual IAM-issued independently scoped
caller/validator tokens, current same-principal CP authority, independent current
provider certification/health/binding, Nabhold consumption or the full matrix.
The canonical activation hold, native protected IAM–CP, executive authority,
staging, production and R0–R3 remain open. Do not change the frozen identity or
INT-02 locks to make this component pass.


## Patched-source refresh — 22 October 2026

The identity/prerequisite overlay now pins CP #425's supported Go 1.27.3
security build and IAM #132's merged source. The isolated CMS component also
pins CMS #47 and Nabhold #86, retaining the real Node24/PG17 provider ports.
The frozen INT-02 baseline and its historical receipt remain unchanged; these
are new run inputs and need their own actual runtime observations. Old PASS
receipts do not certify these revisions.

Shared authority pins are unchanged. Both named CMS identities remain absent;
CMS component execution still requires HELD and every connected case remains
BLOCKED/qualified=false. No source refresh activates authority, upgrades CMS
PARTIAL support or accepts native protected C4, staging, production or R0–R3.

## Supervised native-CMS lifecycle pre-gate foundation

`cms_lifecycle.py` introduces a separate, fail-closed lifecycle guard with an
immutable UTC and monotonic maximum of 90 minutes from creation, a 60-second
maximum token lease bounded by the original deadline, operation-level timeouts
and an independent watchdog. It requires an authentic OPEN-shaped canonical
gate receipt **before** executing an adapter operation; HELD and REFUSED cannot
provision. The Infrastructure runner must independently verify the receipt
against the pinned clean Shared checkout, never handcraft an OPEN document.
`test_cms_lifecycle.py` exercises guard/cleanup behaviour using fake callbacks
and cannot establish actual provider compatibility.

For an eventual real run the owner MUST register all four bounded, separately
verifiable closure callbacks *before* any POST: stop every accepting CMS/CP
runtime and invalidate trust; revoke/destroy issuer clients and token trust;
remove CP-owned disposable topology/grants; remove private files, volumes and
secrets. Closure attempts all owners even if one fails. A callback returns
`True` only after separate observation confirms destruction. No callback may
log secret material. Use an external process supervisor and host recovery as
well: in-process watchdogs cannot survive SIGKILL, runner crash or host loss.

This new primitive intentionally never emits `qualified=true`, even when a
unit test marks 14 local labels observed. Only a separately reviewed live
executor can prove real issuer/CP/CMS operations, independently certified
current CP topology, all negative scenarios, original source/image provenance,
verified teardown, durable evidence and an independent acceptance decision.
The present Shared #354 activation hold means the gate still returns HELD and
all NAB-03 cases remain BLOCKED. Do not run named fixtures or edit the registry
to exercise this code.


### Current CP-owned topology adapter

`cms_cp_context.py` uses CP's current, actually mounted
`POST /v1/platform-context/resolve` and `/validate` routes, rather than
inventing a registry or inserting CP UUIDs through the SQL fixture. The
Infrastructure runner must supply real independent IAM consumer and validator
tokens, approved synthetic Tenant/Organisation/market participation and the
disposable trusted CA. It demands that CP return a fresh, bounded context for
the exact Tenant, Organisation, Organisation kind, country and active market,
then confirms the context using the separate registered validator's subject
token path. Redirects, unsafe TLS, unbounded/mismatched/expired results and
TENANT_PROVISIONING authority are denied. Tokens and response bodies are
never written to the source receipt. A unit-test transport is *not* live proof.

This verifies only CP's current context authority **after** the CP-owned
topology, grants, independent maker/checker provider certification and binding
have actually been established through their governed APIs. The adapter does
not create, approve or certify them. It must never be wired to a held registry
or treated as authority merely because a synthetic test supplied matching
JSON. The remaining connected CMS executor must verify deployment/health and
capability binding, exercise every normative NAB-03 positive/negative against
the live providers, and retain independent runtime provenance and destruction.


### CP-owned synthetic topology and independent certification (PR #44)

[CP-TOPOLOGY-RUNBOOK.md](CP-TOPOLOGY-RUNBOOK.md) defines the concrete
governed Tenant, Organisation, Principal, administrative grant, market,
EngineRelease, provider-certification and changeset/binding routes. The
development-only operator client `cms_cp_governance.py` uses CP's real
HTTPS APIs, CP-issued IDs, separate maker/checker human Principals,
immutable evidence digests, independently observed market activation and
certification read-back. The separate capability resolution helper requires
a *real workload-owned CP context* and a current certified provider.

`cms_cp_fixture_run.py inspect --plan <reviewed-file>` is safe before
activation and performs no network or mutations. Applying one reviewed
CP-only step requires two real CP human admin tokens, a private CA, a
private receipt journal and existing approved CP admission evidence.
An intent is durably recorded **before** a write, with ambiguous outcomes
left for independent CP reconciliation rather than blind retry.

This does NOT create or activate either Shared #354 CMS IAM identity;
it never uses the buyer human-Principal registration route to fabricate a
CMS workload Principal, and a CP administrative grant is **not** a runtime
capability grant. A local test's positive HTTP response is non-qualifying.
Actual CP adapter live execution, governed binding activation, registered
workload Principal/context, issuer teardown and NAB-03 evidence remain
outstanding.

## Native issuer provisioning, revocation and crash recovery — IAM #135 / Infrastructure #43

The maintained IAM provider port now has a named, development-only
`cmd/int03-cms-native` bridge. The Infrastructure owner
`cms_iam_native.py` is the only accepted calling seam. It verifies
`cms_gate.evaluate()` from the immutable Shared registry, checks the exact
clean IAM source pin and **refuses all creates while #354 is HELD**. The CMS
gate workflow also checks this native preflight against independently checked
out, exact Shared/IAM revisions. No live issuer client is created in a HELD
preflight, and no operation is a NAB-03 pass.

When the canonical registry is independently activated through the approved
Shared change, the connected owner must create an *existing owner-private
0700 parent*, supply actual pinned IAM/Shared checkouts and real independently
verifying CP/runtime teardown callbacks, and call
`provision_connected(...)`. Before either HTTP mutation the owner commits
an exclusive fsynced 0600 `owner.json` recovery journal with random 128-bit
run marker and immutable deadline, plus a private credentials directory.
Its `Lifecycle` registers four cleanup fences before starting: accepting
resource servers, issuer, CP and private runtime files. A 90-minute maximum
absolute window and per-invocation timeouts are enforced; the journal survives
host/process failures for a new owner process.

IAM independently verifies each post-created Hydra client, exact allowed
grant/scopes/audiences, credentials method, 60s lifetime and per-run marker.
A client secret is written exclusively to its named private file only after
that read-back. The separate `revoke_connected` action calls the IAM native
`RevokeWorkload` port then verifies the issuer has **no grant types**.
This is issuance containment, not JWT invalidation. `recover()` retries
native revoke **and delete** in reverse order, independently reads back 404,
never deletes another run's client, and retains the journal if any issuer
fence fails. Recover is permitted even if Shared has reverted to HELD.
All accepting CMS/CP runtimes must be stopped/isolated and independently
verified before issuer destruction; no stale JWT may be treated as revoked
merely because a client was deleted.

The standalone safe modes are:

```bash
python3 -B tests/platform-integration/int03/cms_iam_native.py preflight \\
  --shared /absolute/exact/pinned/shared \\
  --iam /absolute/exact/pinned/iam

# After a real run/interruption, while the private issuer is reachable:
python3 -B tests/platform-integration/int03/cms_iam_native.py recover \\
  --journal-dir /absolute/private/int03-native-owner \\
  --shared /absolute/original/pinned/shared \\
  --iam /absolute/original/pinned/iam \\
  --hydra-admin https://hydra.int03.test \\
  --kratos-admin http://kratos:4434 \\
  --issuer https://hydra.int03.test \\
  --ca /absolute/private/disposable-ca.pem
```

The CLI intentionally exposes **no standalone create command**; only the
connected owner with registered accepting-runtime and CP cleanup callbacks
may invoke `provision_connected`. No actual Ory/Hydra docker provider has
yet been added to the INT-03 service overlay, so this is the guarded native
issuer orchestration seam, not an already operational connected CMS proof.
A future admitted connected runner must supply the real private Hydra,
Kratos/companion configuration, source-built CMS, current CP topology,
capability certification, operational kill switch, token/subject validation,
and all 14 runtime cases. Until that is verified, all NAB-03 results remain
BLOCKED, `qualified=false` and protected/production support unchanged.
