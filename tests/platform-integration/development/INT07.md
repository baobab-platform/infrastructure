# DEV-06 — unrelated external API-only client

Run `BAOBAB_ENVIRONMENT=development python3 -B tests/platform-integration/l4.py
run-external development` inside the existing integration devcontainer. Actions
uses the same entrypoint in its independent `external-api` job. CMS, Nabhold's
BFF, Redis, frontend packages and DigitalEstate provisioning are not required.
The other synthetic tenants are negative controls, not related owners of the
external tenant. Their existing estate rows cannot become external estate rows.

## Owners and immutable inputs

Shared owns the exact development-only caller `baobab-dev-external-api` and
independent `baobab-dev-pulse-validator` registry ceilings. IAM's real
Hydra/Kratos processes own credential issuance. CP's explicit `--external-api`
guarded bootstrap creates canonical fixture v3 identities and current leased
assignments. `--check-external-api` queries actual PostgreSQL to prove the external
tenant has zero estates and the validator has no tenant assignment. Missing,
expired or inconsistent facts refuse; the input cannot submit canonical IDs.

`lock.json` pins Shared/CP/IAM. `external-lock.json` pins Pulse and Qdrant;
the reused `int02/pulse.Dockerfile` pins Python 3.14/uv and installs Pulse's frozen
owner lock. Source/contract/image identities enter the final receipt. Pulse uses
its real FastAPI, JWT/JWKS, CP subject-validation, canonical PostgreSQL hydration
and actual Qdrant server. The owner-provided deterministic reference embedder is
explicitly a synthetic algorithm; it proves neither model quality nor an external
LLM. No IAM token, CP context or database/provider response is mocked at runtime.

## Historical initial boundary (superseded for development by the bound rerun)

This increment implements component qualification and all INT-07 obligations as
visible outcomes. It DOES NOT establish a commercial subscription, canonical
capability grant, active binding or certified provider. It observes CP's actual
`GRANT_NOT_FOUND` and makes the following four obligations BLOCKED:

| Obligation | Reason |
| --- | --- |
| Bound resource with correct audited effect | Canonical entitlement not established |
| Controlled absent-subscription denial | Entitled positive prerequisite absent |
| Controlled unentitled resource denial | Entitled positive prerequisite absent |
| Retired binding denial | Canonical binding not established |

A direct, authenticated Pulse read is recorded only as `real_external_resource_read`.
It cannot pass the bound-resource case or imply that Pulse currently enforces a
per-operation commercial entitlement. OAuth operation scope and caller-bound
context do not themselves supply that entitlement. Canonical INT-07 qualification,
provider certification, staging and production remain false. The original INT-07
scenario and case meanings in Shared's v2.2 matrix are unchanged; the local labels
are engineering observations, not new canonical scenario IDs.

The next owner increment must establish independent subscription/grant provenance,
normal provider registration/release qualification/activation and tenant-scoped
binding, then require fresh capability authority at the engine resource call.
Only a genuinely bound positive makes absent-subscription, revoked-grant and
retired-binding differentials meaningful. The existing INT-02 provider fixture's
Infrastructure-written CP SQL is deliberately not imported into this path.

## Observations and failure behavior

The native journey checks independent OAuth issuance, own current CP context,
Nabhold/ZuriBeans/Thamani tenant denials, invented tenant and estate injection,
foreign context ownership, wrong audience, real expiry, revocation while unexpired
and denied replay, restricted evidence, CP outage/restoration, native canonical
hydration and cross-tenant storage isolation. CP zero-estate/current-assignment
read-back runs before and after the journey. Failures retain the case being
executed; they cannot overwrite an earlier zero-estate result or become PASS.

The source tests validate closed receipt vocabulary, refusal of fake estate facts,
negative case attribution and cleanup that never promotes canonical acceptance.
These tests are not runtime evidence. Source CI cannot turn an unexecuted case
into PASS. A successful runtime job requires all 14 currently implemented cases
PASS, exactly four canonical prerequisites BLOCKED, all component observations
and verified final teardown, while `int07_qualified=false`.

## Custody, cleanup and rollback

Per-run secrets, issuer clients, TLS keys, CP anchors, contexts and Pulse fixtures
stay in the existing private `0700` run root. The caller and validator receive
separate random credentials. Native clients are deleted/read back, outstanding
tokens become issuer-inactive, and the ordinary lease/watchdog and label-based
recovery remove owned containers, images, networks, volumes and private state.
The same create-before-mutate ledger and two-phase completed receipt publication
apply. Only sanitized completed receipts and SHA-256 pairs are uploaded; raw logs,
claims, bearers, DSNs, private paths, callbacks and fixture records are not.

Recovery: `python3 -B tests/platform-integration/l4.py recover development --all`.
Host recovery works after the development container is lost. Failed cleanup
retains recovery custody and never publishes a teardown PASS. Rollback recovers
the owned run, restores the reviewed source/image pins and disables only this
profile. Historical receipts remain immutable. No protected identity or storage
may depend on this development fixture.

## Python 3.14 strict TLS

The run CA has critical CA/keyCertSign/cRLSign usage; the leaf has explicit
serverAuth, key usage, subject-key identifier and authority-key identifier.
Python 3.14's default strict validation rejected the old CA's missing key usage.
The regression performs an actual socket TLS handshake with VERIFY_X509_STRICT
also enabled in the lighter Python 3.12 tool image. Verification and hostname
checks are never disabled; no arbitrary trust fallback or insecure adapter is
used. The generated private CA key is destroyed after signing as before.

## Current bound-resource rerun and source refresh

The selected external-base-lock keeps historical DEV-01..05 locks unchanged.
The current-source refresh adopts Shared #403, CP #445 and Pulse #62 only through
immutable merged revisions. This brings the canonical PostgreSQL scope,
classification and projection guards proved by DEV-15 into the independent
external API-only journey; no Digital Estate, CMS or Payments dependency is added.
All eighteen original DEV-06 cases and the 21 component checks must run again at
those pins. Earlier accepted and failed receipts retain their original source
identity and are not relabelled as current qualification.

The four BLOCKED cases described in the historical section above were resolved
by the bound development rerun. They must not be presented as the current DEV-06
status. Canonical INT-07's independent certified-provider requirement remains a
separate gate: neither these development passes nor normal development provider
activation supplies that certification or protected approval.

Merged owner pins enforce current subscription/projection provenance, current
provider/support and normal binding resolution at actual Pulse resource use.
The actual caller requests both CP and Pulse audiences with context:resolve and
the exact Intelligence operation scope; the independent validator cannot act as
that caller. All eighteen original case names and meanings are retained.

The CP-owned guarded fixture uses the original catalogue/registration, actual
running PG/Qdrant readiness and actual immutable owner source/declaration/image.
An OCI image manifest is derived from the actual saved image config and layer
bytes (diff IDs checked against config), published with its blobs only on the
private run-owned artifact endpoint. A config/image ID is not called a manifest
digest. CP fetches/hashes that actual manifest, then uses normal maker/checker
release approval, provider activation, ProductVersion/Composition expansion and
binding admission. It does not insert ACTIVE provider/certification shortcuts.
The expiring external TRIAL source is nonmonetary and creates no estate or INTERNAL
eligibility, legal verification, provider certification or protected authority.

A fresh resource read commits its actual resolution/grant/binding/provider/
instance audit in Pulse PG before returning data. The driver independently reads
that record and matches its resolution ID and tuple to CP's persisted decision.
Control one revokes only the grant (source/binding active), then normal expansion
restores a new grant. Control two actually deletes the source (grant/binding
active), then normal source/expansion restores it. Control three retires the
binding with source/grant still active, as a final transition. Each observes the
normal CP denial and repeated Pulse403 with no added read audit. These are not
unavailable-provider or missing-fixture substitutes for the original negatives.

The runner removes old suite/hash output before every attempt and requires all
18 native cases plus every source/control/audit/cleanup component observation.
Failure remains failure; skipped or BLOCKED mandatory cases cannot satisfy CI.
Original historical14/4 receipts remain unchanged; the new run needs separate
original-byte report/hash custody and actual source/merge/artifact identity.

All observations remain disposable component-development evidence. The canonical
INT-07-API acceptance matrix's separately certified-provider requirement, EA-09,
protected acceptance and production permission are not manufactured by permissive
nonproduction release approval. Qualification flags remain false until their
independent gates are satisfied. DEV-10 remains paused.

## Private proof ownership and failed-run diagnosis

Run 40256362565 built Pulse and published its OCI manifest, but did not reach
provider startup or acceptance. Its original completed receipt records host
teardown as verified and runtime identity as unverified. These are separate
observations; failed startup must not be diagnosed as failed cleanup.

The source proof is written with mode 0600 by the development operator. The
one-shot CP fixture command must use that operator's UID/GID to read the mounted
proof; the CP image's default nonroot UID is different in Codespaces. The mount
remains read-only, the proof remains private, and the normal CP service keeps
its image identity. No root or public-file workaround is required.

The runner emits the closed execution error before recovery and marks each
owner-fixture phase. It retains a hashed failed suite after verified host cleanup
even when runtime identity was never established. That receipt cannot satisfy
the eighteen-case exit. Raw subprocess output and arbitrary exception text stay
out of public logs and artifacts. Container and independent host recovery still
run on every workflow outcome.

