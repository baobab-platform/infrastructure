# DEV-11 / L4-OPS-01 — independent evidence join

**Authority:** Shared EA v2.3 / EA-DEV DEV-11, Infrastructure ADR-Infra-0016.  
**Candidate:** Infrastructure [#72](https://github.com/baobab-platform/infrastructure/pull/72).  
**Status 2026-11-02:** **IMPLEMENTED CUSTODY VERIFIER, NO COMPLETE QUALIFIED OBSERVATION.** Do not merge or certify staging/production.

## Why this gate is separate

An estate Playwright screenshot ZIP, its own summary, or a green *image build* is not an independent confirmation of functional browser execution, accessibility, visual regression or performance. Infrastructure `tests/platform-integration/development/dev11_evidence_join.py` is a separate, read-only GitHub Actions observer. It checks the **actual** Actions run ID, exact immutable SHA, current PR/branch head, workflow filename, successful *named* job and all required successful *named* steps before it downloads the estate-owned artifact.

There are five required independently pinned runs: Infrastructure native issuer→CP, Infrastructure native BFF→IAM/CP→Trade, Nabhold quality, ZuriBeans quality and Thamani quality. The last three estates retain their own approved test suites, branding, browser matrices, screenshot baselines and budgets. The central verifier does not re-run or forge these suites.

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

**Not yet complete:** the native real **OTLP collector / independently exported span graph**, real asynchronous RabbitMQ/outbox publisher→downstream consumer linkage, a business-effect/replay proof at the consumer's own transactional boundary, and failure diagnosis against those actual spans. The current native HTTP and deliberately failed-broker PostgreSQL tests do **not** provide those. Consequently, the join output's `l4_ops_01` remains **BLOCKED** even if `join_http_and_estates_verified` becomes `true`. Only a subsequent separately reviewed, real native collector + broker/consumer evidence gate may change this.

## Execute independent verification

Use GitHub Actions: `Infrastructure → DEV-11 independent L4-OPS-01 and estate evidence custody → Run workflow`. Supply the *single* `bindings_json` input with **actual current successful run IDs and immutable SHAs** for all five owners. The manifest uses the following shape (replace every placeholder; these are not real evidence):

```json
{
  "schema": "infrastructure.dev11.join-input.v1",
  "pins": {
    "infrastructure": "INFRA_HEAD_40_HEX",
    "cp": "CP_HEAD_40_HEX",
    "baobab-cp": "CP_HEAD_40_HEX",
    "baobab-trade": "TRADE_HEAD_40_HEX",
    "nabhold": "NABHOLD_HEAD_40_HEX",
    "zuribeans": "ZURIBEANS_HEAD_40_HEX",
    "thamani": "THAMANI_HEAD_40_HEX"
  },
  "runs": {
    "l4_iam_cp": {"run_id": 0, "sha": "INFRA_HEAD_40_HEX"},
    "l4_bff_trade": {"run_id": 0, "sha": "INFRA_HEAD_40_HEX"},
    "nabhold": {"run_id": 0, "sha": "NABHOLD_HEAD_40_HEX"},
    "zuribeans": {"run_id": 0, "sha": "ZURIBEANS_HEAD_40_HEX"},
    "thamani": {"run_id": 0, "sha": "THAMANI_HEAD_40_HEX"}
  }
}
```

Access: `GITHUB_TOKEN` with `actions:read` may access these currently public repository artifacts; otherwise configure `DEV11_EVIDENCE_READ_TOKEN` as a *read-only* GitHub App/PAT secret scoped to the necessary five repositories. Missing/insufficient access is **BLOCKED**, not a skip. No write permission to another repository is used or needed.

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
