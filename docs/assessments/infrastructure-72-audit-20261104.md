# Infrastructure #72 — readiness and incremental-accomplishment audit

4 November 2026 · EA v2.3 + EA-DEV + EA-XB v1.1

**Verdict: NEEDS_CORRECTION. DEV-04, DEV-11 and L4-OPS-01 remain BLOCKED.**

This audit reviews immutable Infrastructure head
`dd755992a98443f815a54121525be44a8a93bde2` against accepted base
`a3e85794ee58266088efa846b34f58a92b996e45`. Source tests were rerun in
a separate checkout of that exact commit. Unpublished working-tree changes
are excluded from accomplishments. The containing documentation commit does
not retroactively qualify a new implementation head.

The owner's latest direction permits merging PRs that satisfy their own
specifications. Protected deployment, provider promotion and programme
acceptance retain their separate controls. This supersedes the older blanket
no-merge instruction; it does not permit bypassing a failing check.

## 1. Verified accomplishments and their limits

| Increment | Verified accomplishment | Limit |
| --- | --- | --- |
| Current #72 source | 205 development tests and 93 INT-02 tests pass in an exact-head checkout. Infrastructure CI, Foundation, L3, source/privacy and isolated OTLP workflows pass. | Source tests and isolated exporter smoke do not prove the business vertical. |
| #72 HTTP path | Current real confidential BFF/IAM/CP/Trade workflow passes at its pinned tuple. | It pins older Trade/ZuriBeans sources; it is HTTP proof, not governed Medusa commitment or native ERP consequence. |
| Issuer/CP integration | L4-CP-01, L4-CP-02, L4-IAM-01 and L4-IAM-02 pass in the actual current-head INT-02 run. Provider resolution/outage/recovery now has genuine observations. | L4-CP-03 still fails; the full workflow is red. |
| Asynchronous component | Prior original Trade run 41810341641 observes confirms, both prescribed crash windows, signed inbox admission/replay/DLX and seven exported spans across three services. | Its immutable tuple is historical. Current Trade #188 fails before current broker qualification completes. Synthetic outbox origin is not a buyer commitment. |
| Main → #72 delta | Since a4cc31b, #72 incorporates accepted main's PostgreSQL physical-volume major-version guard from merged #71. | This is DEV-12 admission safety, not physical migration, restore, RPO/RTO or full recovery acceptance. |
| Shared/identity foundation | Shared #430 has merged at 7f547ccdd759208355ef9224d2177929f4bf224e. CP #455 adopts its exact contracts on its reviewed candidate branch. | Proposed identities remain PROVISIONED; a source lock grants no active Principal or native permission. |
| Infrastructure #69 | Head 45a71c0177ca6122ff2b3a4911d3c66bdca85548 already reconciles N02/N07 Shared, CP and accepted-estate pins. All recorded current-head workflows pass, including real Ory/CP/TLS Redis components. | Its runner explicitly remains component-only; N02 same-run browser/INT-03C and native N07/booking acceptance are still held. These newer changes are not in #72. |
| Existing Trade work | Trade #183's non-binding RFQ/quotation kernel and PostgreSQL history/concurrency work are merged and composed into current #188. | Binding acceptance/conversion and ENFORCED buyer/seller/spend commitment remain separately unqualified. |
| Estate evidence | Thamani #51 was already merged. Nabhold #103 passed this audit and has now merged with an exact-head lease. | Estate quality is a bounded capability, not overall DEV-11 or live carrier/business acceptance. |

The automatic unused-`Refused` review comment is not a current source defect:
the audited import block no longer imports it. No redundant code change is
justified. Earlier automatic-review quota/failure comments are not evidence
that a substantive architecture review succeeded.

## 2. Material findings

### F01 — P1: #72 has not adopted the already implemented #69 source reconciliation

[The current N07 lock](../../tests/platform-integration/development/n07-base-lock.json)
still pins Shared `38704895c3b0c2897d4c72d4b1353945d2bbb2ff` and CP
`af86ff3e23e097f7ac26ecf2f13741e71f84fa02`. Actual current-head job
`126538381333`, run `41819306349`, refuses `EMBEDDED_CONTRACT_DRIFT`.

Reuse #69 at `45a71c0177ca6122ff2b3a4911d3c66bdca85548`; it already
contains the accepted Shared #430 / byte-matched CP #455 alignment,
accepted estate source pins and regression assertions. Rebuilding this
inventory independently would create avoidable drift. Source composition
must retain PROVISIONED status and all original negative gates.

### F02 — P1: L4-CP-03 fails its own-positive prerequisite

Run `41819306916`, job `126538587871`, reports:
`L4-CP-01=PASS L4-CP-02=PASS L4-CP-03=FAIL L4-IAM-01=PASS L4-IAM-02=PASS`.

Parent, subsidiary, sibling and external principals each receive HTTP 404
`ORGANISATION_NOT_FOUND` on their own Organisation overview, while each
directory request receives 200. The source correctly requires an own-record
200 before neighbour/spoof 404s count as isolation. Preserve that requirement:
a route, fixture, projection or authority failure cannot certify denial.

The same failed prerequisite also blocks the connected DEV-11 Keycloak/CP
workflow and the Nabhold INT-03 smoke that runs the common harness. Successful
directory access alone is insufficient. The exact root cause requires
reconciling the CP-owned read model/authorization and the fixture's canonical
Organisation identity; this audit does not guess it.

Source: [probe.py at the audited head](https://github.com/baobab-platform/infrastructure/blob/dd755992a98443f815a54121525be44a8a93bde2/tests/platform-integration/int02/probe.py#L623).

### F03 — P1: the verifier permanently rejects an already merged CP owner

[dev11_evidence_join.py:569](https://github.com/baobab-platform/infrastructure/blob/dd755992a98443f815a54121525be44a8a93bde2/tests/platform-integration/development/dev11_evidence_join.py#L569)
requires CP #458 to be open with its branch head equal to the ERP source pin.
CP #458 is already merged. Valid accepted-main source therefore cannot pass.

A correction must distinguish an exact current open candidate from accepted
current main containing the recorded merge. It must reject closed-unmerged,
stale, unrelated, wrong-base or rewritten ancestry. Removing source checking
or accepting an old green branch SHA would violate the evidence requirement.

### F04 — P1: executed checkout bytes are not consistently bound to run metadata

Several Infrastructure workflows use the default Actions PR merge checkout,
while the independent reader attributes evidence to `run.head_sha`.
Those identities can represent different source trees. The audited estate
reader also lacks a required original git readback, although Nabhold/Thamani
now emit one.

Require explicit owner-head/event checkout and independently bind its original
source readback plus successful named source guard to the pinned run.
Nabhold's reviewed pattern trusts only the exact job workspace for a single
git command, with no global wildcard.

Run `41819306521` passes the verifier's **source tests**. Its actual
independent eight-owner job is **skipped**, because that job is dispatch-only.
It is not a successful joined acceptance run.

Sources: [workflow checkout](https://github.com/baobab-platform/infrastructure/blob/dd755992a98443f815a54121525be44a8a93bde2/.github/workflows/dev11-connected-bff-trade.yml#L25)
and [dispatch gate](https://github.com/baobab-platform/infrastructure/blob/dd755992a98443f815a54121525be44a8a93bde2/.github/workflows/dev11-evidence-join.yml#L34).

### F05 — P1: the current source tuple and native business vertical remain incomplete

The broker artifact must match the current full Infrastructure head, while
Infrastructure pins the Trade head and Trade pins the imported Infrastructure
observer. This reciprocal full-repository requirement forms a moving-head
cycle. Current Trade additionally imports ERP `88c2cdcac6a3a2f2eaf0165e1bb5e284dbde6a0e`
and Infrastructure `a4cc31b1806fce3d80814b82af4a1652aa11964d`, rather than
the current owner heads. A reviewed immutable component-source/digest
compatibility mechanism is a narrowly proposed resolution; the current
strict gate must not be silently relaxed.

Current Trade `007eab655adf102c8dc3ee063d86431fc53efe85`, run
`41841700520`, job `126614679256`, fails its real PostgreSQL native-origin
readback with `NATIVE_ORIGIN_DATABASE_UNAVAILABLE`. This category does not
establish whether the underlying cause is connectivity, SQL, permissions or
schema. The `--expect-synthetic-refusal` negative did not pass; it must not
be relabelled as an expected successful refusal. Subsequent current broker
proof is missing. The positive governed order still needs actual Medusa
order, ENFORCED B2B fence, buyer/seller authority and atomic spend/outbox
provenance.

Current ERP `73788646f429e722ddc4941a27599ed745430c8d`, run
`41840786923`, job `126611505315`, independently observes CP sales
`AUTHORIZED` and negative-only documentary clearance. Its separate worker
still returns `blocked/LEGAL_ACTOR_DENIED`; its only observed worker stage
is `CP_REQUEST`. This does not prove a provider/JVM failure, nor permit
skipping the worker's fresh assessment. No native C_Order/consequence or
unknown-outcome recovery is qualified.

The existing unconditional L4 BLOCKED result remains an appropriate hold
while these genuine proofs are missing. Positive full-vertical qualification
must eventually be implemented against the same native event and exported
cross-runtime lineage; disjoint component successes cannot replace it.

### F06 — P2: valid native NUMERIC identifiers are rejected at the ERP provider boundary

At [ERP inbox_authority.py:165](https://github.com/baobab-platform/baobab-erp/blob/73788646f429e722ddc4941a27599ed745430c8d/modules/application/inbox_authority.py#L165),
`_native_id` accepts only Python int or digit strings. The dev-only JVM
adapter returns raw PostgreSQL NUMERIC IDs, normally Decimal. A source-level
reproduction using the exact remote function accepts 11 and "11" but rejects
Decimal("11"). This is a confirmed compatibility defect.

Normalize only exact finite integral native IDs without truncation, boolean,
string ambiguity or range overflow, while retaining company/Organisation
checks. This has **not** been established as the current runtime root cause:
the observed worker stops before native provider readiness. Fixing it alone
cannot justify native execution acceptance.

### F07 — P2: runbooks and the previous register are stale

The previous assessment says Shared #430 is unmerged and all merging is
prohibited. Both are superseded. The eight-owner runbook's example supplies
only seven run bindings and omits the IAM source pin; an operator following it
cannot supply a complete eligible join. Update these instructions with exact
current source/evidence semantics. Historical receipts remain historical.

## 3. ADR and specification assessment

| Requirement | Assessment |
| --- | --- |
| ADR-Infra-0016 §§9–20: authority separate from telemetry, bounded privacy/cardinality, HTTP/RabbitMQ propagation | Substantial source implementation and real isolated/component export. Complete governed same-event lineage remains unqualified. |
| ADR-Infra-0016 §§57/60: business correctness independent of collector; diagnosable end-to-end operation | No telemetry-to-authority grant was found. Full accepted failure/recovery and native operation proof remains incomplete. |
| ADR-Infra-0017: health, SLO and operational observations | Component health and quality labs exist. No field SLO/production readiness claim is justified by them. |
| ADR-Infra-0020/0023: reviewed immutable source, genuine gates, auditability and protected boundaries | Source pinning/custody exists but F01/F03/F04/F05 prevent complete source/evidence conformance. No protected activation was performed. |
| ADR-SHARED-043: real provider credentials, scoped synthetic development, exact sources, truthful evidence and teardown | Real Ory/CP/PG/Redis components and reusable lifecycle exist. PROVISIONED, unsupported and unexecuted cases must remain held. |
| ADR-SHARED-042 CAA-06/06b/08: universal native commitment controls | Native acceptance requires current governed buyer/seller/classification/spend proof. SHADOW or synthetic origin is insufficient. |
| EA-DEV DEV-12 | Accepted physical-major admission fence is implemented and tested in Docker CI. It does not close schema migration, replay, backup/restore or DR for every engine. |
| EA-DEV DEV-14 | Common prepare/start/IAM/CP/native-owner/evidence/revoke/teardown pattern exists. Every native owner keeps its own enforcement and acceptance obligations. |

## 4. Reviewed merge action and current estate evidence

Nabhold #103 was reviewed across its four changed files, current CI, review
comments and original artifact. No review comments remain. Its bounded
report-retention/exact-source scope met requirements, so it merged with
expected head `c37ffd83bd0eaba4ad0b702f3ed96347ef7b37bb` to
`c2f11f33138649d819c10f8876f785f8ae2e6d9d`.

Current-main run `41844724077` and artifact `13331007073` were independently
rechecked after merge. Exact source, workflow/job/steps, original reports,
strict counts and ZIP SHA-256 pass:
`be12769dd8e42ff24cfa72c3af4b2904a2b70232ca5465e926e9fcdb6d789d32`.

Measured executions: 135 functional, 3 accessibility, 5 visual and 1
Lighthouse; JavaScript 776695 bytes total / 229596 largest chunk; CSS 60258
bytes; all approved static budgets pass. Home/markets Lighthouse performance
96/98, accessibility 100/100, best practices 96/96 and SEO 100/100; CLS 0.
Home lab LCP is 2646 ms, so the broader 2.5 s programme target/field CWV is
not declared accepted. No budget or screenshot baseline was raised.

Thamani #51 was already merged before this audit's merge action. ZuriBeans
#156 remains source/evidence-held. A merged estate quality fix does not
accept the programme or prove live native logistics/business operations.

## 5. Readiness and implementation order

| PR / concern | Readiness |
| --- | --- |
| Nabhold #103 | MERGED after bounded specification review; current-main original independently verified. |
| Thamani #51 | Already merged; retain its distinct evidence and provider limits. |
| Infrastructure #69 | Source/component progress proven; full N02/N07 specification still held. |
| Infrastructure #72 | NEEDS_CORRECTION; F01–F05 block merge. |
| CP #455 / IAM browser-consumer candidates | Retain candidate and active-authority distinctions; source-green CI does not supply full N02 originals. |
| Trade #188 | NEEDS_CORRECTION; current real native-origin readback fails and governed positive remains absent. |
| ERP #125 | NEEDS_CORRECTION; actual worker authority refusal and native business proof remain unresolved. |

First reuse #69's accepted-source reconciliation in #72. Then correct the
Organisation own-read prerequisite and verifier source/merged-owner defects,
retaining all negatives. Diagnose the exact Trade SQL/worker CP failure
before changing authority or native adapters. Address the confirmed native
ID defect without inferring its runtime causality. Resolve source compatibility
through a reviewed decision, execute the genuine same-event vertical and all
eight current owner originals, and finally repeat exact-head review.

This audit does not make an implementation finding disappear by documenting
it. No new runtime code was implemented in this audit increment. No other PR was merged in this audit increment, and no
protected environment or provider authority was activated.

## 6. Dependency inventory and audit boundaries

The following 30 source observations refresh the earlier inventory.
“Dependency metadata” is not a complete current-head code audit or merge
approval. The machine-readable companion preserves exact findings and runs.

| PR | Recorded source | State | Inspection level |
| --- | --- | --- | --- |
| [infrastructure#69](https://github.com/baobab-platform/infrastructure/pull/69) | [45a71c0177ca](https://github.com/baobab-platform/infrastructure/commit/45a71c0177ca6122ff2b3a4911d3c66bdca85548) | OPEN | Source/runtime or contract review |
| [infrastructure#72](https://github.com/baobab-platform/infrastructure/pull/72) | [dd755992a984](https://github.com/baobab-platform/infrastructure/commit/dd755992a98443f815a54121525be44a8a93bde2) | OPEN | Source/runtime or contract review |
| [shared#420](https://github.com/baobab-platform/shared/pull/420) | [750ab553402c](https://github.com/baobab-platform/shared/commit/750ab553402c7b7485a8c74fe0e1a167eed1a6a7) | CLOSED | Dependency metadata |
| [shared#421](https://github.com/baobab-platform/shared/pull/421) | [38704895c3b0](https://github.com/baobab-platform/shared/commit/38704895c3b0c2897d4c72d4b1353945d2bbb2ff) | CLOSED | Dependency metadata |
| [shared#422](https://github.com/baobab-platform/shared/pull/422) | [3b24291f2c16](https://github.com/baobab-platform/shared/commit/3b24291f2c164ecdbadc7e3a4c190790b86b73d2) | CLOSED | Dependency metadata |
| [shared#429](https://github.com/baobab-platform/shared/pull/429) | [f56cf41d8572](https://github.com/baobab-platform/shared/commit/f56cf41d8572ec67ca52dd4172d2f1fa08a58dea) | OPEN | Dependency metadata |
| [shared#430](https://github.com/baobab-platform/shared/pull/430) | [1dc7a7eba0c1](https://github.com/baobab-platform/shared/commit/1dc7a7eba0c197159473864c5cd8bea7637e4a8c) | MERGED | Source/runtime or contract review |
| [baobab-cp#454](https://github.com/baobab-platform/baobab-cp/pull/454) | [efa4418e41a5](https://github.com/baobab-platform/baobab-cp/commit/efa4418e41a5be5b75f37f2de9adfed9aaa45d57) | OPEN | Dependency metadata |
| [baobab-cp#455](https://github.com/baobab-platform/baobab-cp/pull/455) | [a5e5458ea665](https://github.com/baobab-platform/baobab-cp/commit/a5e5458ea6651657a66698b60b765eca5774daf4) | OPEN | Source/runtime or contract review |
| [baobab-cp#458](https://github.com/baobab-platform/baobab-cp/pull/458) | [ab61e35c3502](https://github.com/baobab-platform/baobab-cp/commit/ab61e35c35028bad1090232bcf2d7c67a84ef959) | MERGED | Dependency metadata |
| [baobab-iam#145](https://github.com/baobab-platform/baobab-iam/pull/145) | [f05798a5c62a](https://github.com/baobab-platform/baobab-iam/commit/f05798a5c62a56c656143087a108090786095bc1) | MERGED | Dependency metadata |
| [baobab-iam#146](https://github.com/baobab-platform/baobab-iam/pull/146) | [4958f79ba6f8](https://github.com/baobab-platform/baobab-iam/commit/4958f79ba6f877d341bb9a98349ce8c30a29e283) | OPEN | Dependency metadata |
| [baobab-iam#147](https://github.com/baobab-platform/baobab-iam/pull/147) | [225ba193b408](https://github.com/baobab-platform/baobab-iam/commit/225ba193b4088960c5b64033bfce0f755ac347fb) | OPEN | Dependency metadata |
| [baobab-iam#148](https://github.com/baobab-platform/baobab-iam/pull/148) | [39ee45d3fe4a](https://github.com/baobab-platform/baobab-iam/commit/39ee45d3fe4a4ddcf45074add10f460451e23270) | OPEN | Dependency metadata |
| [baobab-iam#149](https://github.com/baobab-platform/baobab-iam/pull/149) | [c53fca9ebee0](https://github.com/baobab-platform/baobab-iam/commit/c53fca9ebee02c821724e2c512c282deec74b9af) | OPEN | Dependency metadata |
| [baobab-iam#150](https://github.com/baobab-platform/baobab-iam/pull/150) | [6d56cb08d912](https://github.com/baobab-platform/baobab-iam/commit/6d56cb08d912796320c16612515644bfdbaddf8b) | OPEN | Dependency metadata |
| [baobab-iam#151](https://github.com/baobab-platform/baobab-iam/pull/151) | [09a47b59b5d8](https://github.com/baobab-platform/baobab-iam/commit/09a47b59b5d8030e06c3ec07829a87604e700dc9) | OPEN | Dependency metadata |
| [baobab-iam#152](https://github.com/baobab-platform/baobab-iam/pull/152) | [e991ee2d1a6d](https://github.com/baobab-platform/baobab-iam/commit/e991ee2d1a6d53e3db3d52f3739870c09d8364db) | OPEN | Dependency metadata |
| [baobab-iam#153](https://github.com/baobab-platform/baobab-iam/pull/153) | [fae32b20187b](https://github.com/baobab-platform/baobab-iam/commit/fae32b20187b2201e6070c382f563e170773e692) | OPEN | Dependency metadata |
| [baobab-trade#183](https://github.com/baobab-platform/baobab-trade/pull/183) | [492dfb791d63](https://github.com/baobab-platform/baobab-trade/commit/492dfb791d63623396fc4ac12170059cefb6342e) | MERGED | Dependency metadata |
| [baobab-trade#188](https://github.com/baobab-platform/baobab-trade/pull/188) | [007eab655adf](https://github.com/baobab-platform/baobab-trade/commit/007eab655adf102c8dc3ee063d86431fc53efe85) | OPEN | Source/runtime or contract review |
| [baobab-erp#125](https://github.com/baobab-platform/baobab-erp/pull/125) | [73788646f429](https://github.com/baobab-platform/baobab-erp/commit/73788646f429e722ddc4941a27599ed745430c8d) | OPEN | Source/runtime or contract review |
| [baobab-tms#28](https://github.com/baobab-platform/baobab-tms/pull/28) | [32b443212fce](https://github.com/baobab-platform/baobab-tms/commit/32b443212fce671572544a31cb6c320269b3af12) | OPEN | Dependency metadata |
| [zuribeans#141](https://github.com/baobab-platform/zuribeans/pull/141) | [dcc076ab2a44](https://github.com/baobab-platform/zuribeans/commit/dcc076ab2a4436dac7adb64423694f2834ccf6a9) | MERGED | Dependency metadata |
| [zuribeans#156](https://github.com/baobab-platform/zuribeans/pull/156) | [1df43b033738](https://github.com/baobab-platform/zuribeans/commit/1df43b033738a530a821c2ef5cbe84ad3d197275) | OPEN | Source/runtime or contract review |
| [thamani#44](https://github.com/baobab-platform/thamani/pull/44) | [4e65c6cdf339](https://github.com/baobab-platform/thamani/commit/4e65c6cdf3392460ed6b3d9cd3524a46a1093f87) | OPEN | Dependency metadata |
| [thamani#50](https://github.com/baobab-platform/thamani/pull/50) | [f7c027e95d04](https://github.com/baobab-platform/thamani/commit/f7c027e95d04db626e5e5847c9caa1538630175d) | MERGED | Dependency metadata |
| [thamani#51](https://github.com/baobab-platform/thamani/pull/51) | [f7936c051659](https://github.com/baobab-platform/thamani/commit/f7936c051659d555fd5890f4f57a9704dcebe4c8) | MERGED | Source/runtime or contract review |
| [nabhold#99](https://github.com/baobab-platform/nabhold/pull/99) | [b2a6e67c9534](https://github.com/baobab-platform/nabhold/commit/b2a6e67c9534df0984eddc9974c372cd8602e8ce) | MERGED | Dependency metadata |
| [nabhold#103](https://github.com/baobab-platform/nabhold/pull/103) | [c37ffd83bd0e](https://github.com/baobab-platform/nabhold/commit/c37ffd83bd0eaba4ad0b702f3ed96347ef7b37bb) | MERGED | Source/runtime or contract review |
