# DEV-11 / L4-OPS-01 — independent evidence join

**Authority:** Shared EA v2.3 / EA-DEV DEV-11, Infrastructure ADR-Infra-0016.  
**Candidate:** Infrastructure [#72](https://github.com/baobab-platform/infrastructure/pull/72).  
**Status 2026-11-02:** **IMPLEMENTED CUSTODY VERIFIER, NO COMPLETE QUALIFIED OBSERVATION.** Do not merge or certify staging/production.

## Why this gate is separate

An estate Playwright screenshot ZIP, its own summary, or a green *image build* is not an independent confirmation of functional browser execution, accessibility, visual regression or performance. Infrastructure `tests/platform-integration/development/dev11_evidence_join.py` is a separate, read-only GitHub Actions observer. It checks the **actual** Actions run ID, exact immutable SHA, current PR/branch head, workflow filename, successful *named* job and all required successful *named* steps before it downloads the estate-owned artifact.

There are **eight** required independently pinned runs: Infrastructure native issuer→CP, Infrastructure native BFF→IAM/CP→Trade, Infrastructure real SDK→Collector→Jaeger exporter, Trade-native Medusa→RabbitMQ→independent ERP inbox + exported component lineage, ERP native Hydra/CP→protected iDempiere JVM business effect/recovery, Nabhold quality, ZuriBeans quality and Thamani quality. The last three estates retain their own approved test suites, branding, browser matrices, screenshot baselines and budgets. The central verifier does not re-run or forge these suites.

The eighth owner is **ERP #125**: real Ory Hydra client credentials,
current CP RUNTIME context and a separately approved sales mandate,
quorum RabbitMQ delivery into ERP's durable inbox, protected iDempiere 13
JVM C_Order/C_OrderLine execution, two read-only PostgreSQL verifiers
(CP immutable decision + JVM native attribution, and ERP source/inbox/native
business consequence), live CP revocation and run-owned teardown.
The owner artifact is
`dev11-real-hydra-cp-native-jvm-engine-local` from workflow
`.github/workflows/dev11-real-native-engine.yml`. The reviewer verifies
the exact ERP PR head, successful named workflow/job/steps, ZIP SHA-256,
native effects, RUNTIME provenance and absence of false L4 certification.

**Engine-local remains synthetic-source evidence.** It proves real
IAM/CP-to-iDempiere runtime mechanics only when a real GitHub Actions
execution passes. It does not prove that Medusa accepted an authorised
buyer/seller commitment under a shared transaction, or that the same
Trade event ID has end-to-end independently exported OpenTelemetry
lineage. Both are required before `l4_ops_01` can become PASS.

For each estate the verified mandatory step outcomes are:

| Owner | Playwright | Accessibility | Visual | Lighthouse | Static budget |
| --- | --- | --- | --- | --- | --- |
| Nabhold | `Public functional end-to-end journeys (five browser profiles)` | `WCAG 2.2 AA public accessibility gate` | `Landing-page visual and layout gate` | `Isolated production-build Lighthouse lab` | `Enforce approved static budgets after all browser diagnostics` |
| ZuriBeans | `End-to-end tests` | `Landing-page accessibility checks` | `Landing-page visual regression checks` | `Isolated Lighthouse performance lab` | `Enforce frontend performance budgets` |
| Thamani | `Verify landing and Next.js logistics routes` plus keyboard/logistics browser step | `WCAG landing-page and logistics-route accessibility` | `Independent homepage visual layout and screenshot evidence` | `Isolated Lighthouse production-build lab` | `Enforce emitted-asset performance budget` |

**Any skipped, cancelled, failed or absent step blocks the join.** A failed quality job that nevertheless uploaded screenshots does *not* pass. No snapshot-update candidate can override the owner visual gate. The owner run must still be the latest source head for its PR/branch. Source SHAs are compared to the pinned inputs, not inferred from the artifact name.

The verifier downloads each owner artifact using a **read-only GitHub Actions API token**, follows the GitHub-generated signed blob URL *without forwarding the API token*, validates a bounded safe ZIP, and independently compares SHA-256 to GitHub's advertised artifact digest. The join receipt publishes only bounded gate outcomes, verified run/job/artifact IDs, source SHA and ZIP digest—not screenshots, traces, URLs containing credentials, customer data or raw logs.

### Connected L4-OPS-01 prerequisites

The Infrastructure IAM/CP artifact must include the actual seven W3C/current-authority observations and independently verified teardown. The Infrastructure BFF/Trade artifact must include current CP/Trade/ZuriBeans source pins, the six real native HTTP allow/deny/log-correlation checks, run-owned resources and issuance/revocation cleanup. Both owning workflows must pass. An *all-success source graph* without verified native evidence cannot pass.

**Not yet complete:** Infrastructure #72 now proposes real SDK→Collector→Jaeger export; Trade #188 and ERP #125 now propose a connected native Medusa PostgreSQL outbox→RabbitMQ quorum queue→independent ERP PostgreSQL inbox execution **with a real post-commit/pre-ACK process crash and recovery**, separate signed-payload denial/DLQ, and an independent backend query of the three native component span services. **These are unqualified current-head candidate workflows until their actual CI results pass**. A full authenticated BFF/IAM/CP→Trade→ERP trace plus actual current-authority iDempiere business-effect/replay/uncertain-outcome evidence is still missing. Consequently, `l4_ops_01` remains **BLOCKED** even when all eight component/estate runs eventually join. Never mistake a synthetic outbox event or a durable ERP inbox receipt for a native financial consequence.

## Execute independent verification

Use GitHub Actions: `Infrastructure → DEV-11 independent L4-OPS-01 and estate evidence custody → Run workflow`. Supply the *single* `bindings_json` input with **actual current successful run IDs and immutable SHAs** for all eight required owner/connected profiles. The manifest uses the following shape (replace every placeholder; these are not real evidence):

```json
{
  "schema": "infrastructure.dev11.join-input.v1",
  "pins": {
    "infrastructure": "INFRA_HEAD_40_HEX",
    "cp": "CP_HEAD_40_HEX",
    "baobab-cp": "CP_HEAD_40_HEX",
    "baobab-iam": "IAM_HEAD_40_HEX",
    "baobab-trade": "TRADE_HEAD_40_HEX",
    "baobab-erp": "ERP_HEAD_40_HEX",
    "nabhold": "NABHOLD_HEAD_40_HEX",
    "zuribeans": "ZURIBEANS_HEAD_40_HEX",
    "thamani": "THAMANI_HEAD_40_HEX"
  },
  "runs": {
    "l4_iam_cp": {"run_id": 0, "sha": "INFRA_HEAD_40_HEX"},
    "l4_bff_trade": {"run_id": 0, "sha": "INFRA_HEAD_40_HEX"},
    "l4_exporter": {"run_id": 0, "sha": "INFRA_HEAD_40_HEX"},
    "l4_rabbit": {"run_id": 0, "sha": "TRADE_HEAD_40_HEX"},
    "l4_erp_native": {"run_id": 0, "sha": "ERP_HEAD_40_HEX"},
    "nabhold": {"run_id": 0, "sha": "NABHOLD_HEAD_40_HEX"},
    "zuribeans": {"run_id": 0, "sha": "ZURIBEANS_HEAD_40_HEX"},
    "thamani": {"run_id": 0, "sha": "THAMANI_HEAD_40_HEX"}
  }
}
```

Access: `GITHUB_TOKEN` with `actions:read` may access these currently public repository artifacts; otherwise configure `DEV11_EVIDENCE_READ_TOKEN` as a *read-only* GitHub App/PAT secret scoped to the necessary eight evidence profiles and their repositories. Missing/insufficient access is **BLOCKED**, not a skip. No write permission to another repository is used or needed.

### Current accepted dependencies after an owner PR merges

The native ERP owner depends on CP #458 and IAM #153. An open owner must
match its exact current PR head. For a merged owner, the reviewer requires
`merged=true`, target `main`, the exact current `main` SHA as the source pin,
and independently queried GitHub comparison ancestry containing the recorded
merge commit. A closed unmerged PR, historical branch tip, stale main pin,
foreign base, diverged ancestry or missing merge identity remains denied.
This handles already merged CP #458 without accepting an old green source.

### Estate checkout provenance

Each estate quality job must pass `Verify exact owner source SHA` and retain
`reports/dev11-source-sha.txt` from `git rev-parse HEAD`. Its original value
must match the pinned run source. Actions defaults to a PR merge checkout;
`run.head_sha` alone cannot establish which bytes the job actually tested.
The owner explicitly checks out `github.event.pull_request.head.sha` (or the
event SHA for main/dispatch) and verifies that readback before browser tests.
Historical artifacts lacking this binding need fresh qualification. See the
official checkout behaviour at
https://github.com/actions/checkout#checkout-pull-request-head-commit-instead-of-merge-commit.

Run receives a scrubbed `dev11-l4-ops-01-independent-join` artifact with `dev11-l4-ops-01.json` and `.sha256`. The independent job deliberately exits non-zero on incomplete connected evidence and on incomplete native OTLP/consumer qualification. Preserve both that outcome and the detailed per-owner cause in the audit.

Reproducible source-only verifier regression:

```bash
python3 -B -m unittest discover -s tests/platform-integration/development -p 'test_dev11_evidence_join.py' -v
```

**Observed blocker on 2026-11-02:** Nabhold #99 workflow 41390782054 failed the Playwright quality journey; Lighthouse/accessibility/visual steps were skipped, despite the browser artifact being uploaded. This is explicit `RUN_FAILED` (and missing required step success), not an accepted estate qualification. Infrastructure #72 newly connected jobs did not yet have completed passing executions at the last read.

The DEV-10 `baobab-dev:v1.5.0` toolchain image decision remains a separate workstream; this gate never raises performance budgets to manufacture a PASS.


## Machine-readable owner result custody

The owner CI branches now deliberately **retain different output directories for each real suite** so later runs cannot overwrite earlier results. Nabhold [#99](https://github.com/baobab-platform/nabhold/pull/99), ZuriBeans [#156](https://github.com/baobab-platform/zuribeans/pull/156) and Thamani [#50](https://github.com/baobab-platform/thamani/pull/50) own those changes. Their downloadable artifact ZIPs must contain:

- `reports/dev11-functional-playwright.json`, `reports/dev11-accessibility-playwright.json`, `reports/dev11-visual-playwright.json`, `reports/dev11-lighthouse-playwright.json` (and `dev11-logistics-playwright.json` for Thamani), with matching per-gate HTML reports and actual non-empty Playwright cases;
- `test-results/dev11-lighthouse/**/lighthouse-home.json` and owner-specific `lighthouse-markets.json` or `lighthouse-quotes.json` created by the real Lighthouse binary;
- `reports/static-budget.json` containing actual emitted-asset byte measurements and approved limits.

The independent verifier checks actual `stats.expected > 0`, `stats.unexpected == 0`, `stats.flaky == 0`, and an empty Playwright top-level error list. It parses the native Lighthouse reports to enforce each owner's approved minimum performance (90) and accessibility/best-practices (95) scores, public-page SEO (95), CLS no more than 0.1 and transferred JavaScript no more than 250 KiB. Thamani's intentionally `noindex` quote workspace is **not required to meet a public SEO indexability target**; it retains the original owner test's security policy. Single-run Lighthouse LCP is recorded as a **lab diagnostic**, never a fabricated field P75 LCP or INP result.

The original four static limits remain exact: total JavaScript 800 KiB, largest chunk 250 KiB, total CSS 64 KiB and largest raster image 250 KiB. The verifier compares the source-owned report's limits to those independently hardcoded values, then compares actual measured byte counts to them. A report that raises its own limits or has an empty/incorrect sample **cannot pass**, even after a successful GitHub step. Only bounded numbers and fixed category labels leave the private join, never raw reports or screenshot data.


## 4 November 2026 verifier hardening

Browser evidence must contain the original nested Playwright executions as
well as its statistics. Every test must have one passing result, retry zero,
expected status passed, no error and a finite duration. Counts must match the
original summary; skipped, flaky and unexpected counts must all be integer
zero. Missing executions, expected failures, retries and skipped cases refuse
the candidate even if GitHub marks the owner job green. HTML alone cannot
supply measured results. The eight owner groups and all original estate
budgets remain unchanged.

The ZIP reader also rejects duplicate member names and bounds total expanded
size to 1 GiB. JSON rejects duplicate keys, non-finite values and excessive
nesting. These are input-integrity checks, not attestations of runtime success.
Regression tests retain the real/fixture distinction and L4-OPS-01 remains
BLOCKED until the governed commitment and same-event native trace proof exist.


## Audit follow-up: source reconciliation and provenance (4 November 2026)

The DEV-11 branch now composes Infrastructure #69 at
`45a71c0177ca6122ff2b3a4911d3c66bdca85548`: N02/N07 consume accepted Shared
#430 and byte-matched candidate CP #455, with the original PROVISIONED and
protected-acceptance boundaries retained. This removes the superseded source
lock mismatch; it does not certify browser or native booking cases.

INT-02 grants now use CP's governed `development` deployment environment.
The harness's integration evidence class is distinct from that server
environment. Previously the grants selected `integration`, so CP correctly
denied own-Organisation overviews and could not establish the positive
prerequisite for isolation. Exact per-Organisation scope, four principals,
foreign/spoof denials and full teardown remain mandatory in the real rerun.

Verifier changes require current accepted main plus recorded merge ancestry
for merged owners, and bind estate originals to the actual git source
readback and its named successful source guard. Infrastructure checkouts
explicitly select the PR/event source instead of a temporary merge ref.
Source regressions pass 209 development and 94 INT-02 cases (26 independent
verifier cases are included in 209). Actual current-head runtime evidence
must be refreshed; source success does not resolve the reciprocal full-head
compatibility decision or prove the native business vertical.

The broker component's original ZIP must additionally contain
`native-origin.json` from Trade's read-only PostgreSQL checker, and the exact
`Independently refuse synthetic outbox as native B2B buyer order` job step
must succeed. For this intentionally synthetic profile the only eligible
result is `NATIVE_ORDER_ABSENT`, with all native-origin, buyer authority,
atomic commitment/spend, ERP effect and production flags false and L4 blocked.
A missing schema, database outage, skipped step, missing original or added
authority claim cannot stand in for that negative. A future genuine B2B
positive requires its own reviewed business/authority qualification path.
