# Nabhold Go-Live v2.0 — critical-path audit and implementation register

**Snapshot:** 16 October 2026. **Status:** source/CI audit, not release acceptance.
**Programme authority:** [Accepted NAB-GOLIVE-MP-001 v2.0](https://github.com/baobab-platform/nabhold/blob/4aa43cc18302738fed0ca79cb243614f150f3943/docs/go-live/NAB-GOLIVE-MP-001.md).
**Architecture:** Accepted ADR-NAB-0014, ADR-SHARED-036 and EA v2.2.
**Execution policy:** take over task-related open PRs; repair and observe mandatory CI and acceptance; merge before starting the next dependent engineering task. Do not merge a BLOCKED profile.

## Assessment

The programme is substantially advanced in source foundations, but **R0/R1/R2/R3 remain unreleased**. No defensible completion percentage can turn source merges into independently accepted operation. The accepted plan is in `docs/go-live`, rather than `docs/adr`.

Nabhold main `4aa43cc18302738fed0ca79cb243614f150f3943` has OIDC callback/PKCE, confidential encrypted session custody, current IAM/CP identity checks and executive capability/operation guards. G04B-04 is a **seam**, not an active executive route: the CP human-to-workload context-owner handoff is unresolved. The dashboard remains preview-gated. A signed-in human is not an executive grant.

The live Nabhold register's 14 October table is dated history; section 17 correctly records later merges but still calls Infrastructure #35 draft. Its actual 16 October API state is OPEN, non-draft, mergeable, **acceptance failing**. There were no open Nabhold PRs at this snapshot.

## Evidence and boundaries

| Source inspected | Evidence | Conclusion |
|---|---|---|
| Nabhold plan, ADR-NAB-0014, register, README, auth/authorisation code and G04B runbooks | main `4aa43cc18302738fed0ca79cb243614f150f3943` | Source advanced; real identity/onboarding/CMS and R1 authority still unaccepted |
| Shared EA v2.2 and ADR-SHARED-036 | main `33950a4b716c14e7624090349d835af334dc2bc3` | INT-02 before INT-03; real-component tests distinct from protected staging |
| CP platform-context handler/validator and context ownership | main `0f94579ff0e171202ef4be57d7e6d6bb923f19ef`; harness stays on reviewed lock pin | v1 Organisation is optional; no breaking contract change to make a matrix green |
| IAM CMS workload/context scope and human audience differential validator | current main, plus exact locked IAM baseline in manifest | Isolate audience while preserving subject/client/scopes; do not count a different-client denial |
| Infrastructure #35 code, reviews, workflow and job logs | head `25dac444ab8c2efb00613b71a31b351a44a9c91e` | Source/Foundation green; mandatory live job fails |
| [Live workflow 38845962055](https://github.com/baobab-platform/infrastructure/actions/runs/38845962055) | [job 116796481124](https://github.com/baobab-platform/infrastructure/actions/runs/38845962055/job/116796481124) | All five scenario aggregates BLOCKED; real CP positives, grant/identity revocation and several isolation negatives observed |
| [Foundation 38845962910](https://github.com/baobab-platform/infrastructure/actions/runs/38845962910) | exact original head above | Foundation success cannot waive live profile failure |

The original live run observed `ISSUED_WITHOUT_ORGANISATION`, a current entitled resolution and sibling `GRANT_NOT_FOUND`; grant revocation returned `GRANT_REVOKED`. These are useful partial observations, not full matrix completion. All retrieved inline review threads were resolved at the original head.

## Gate reconciliation

| Gate/lane | Source state | Missing acceptance / effect |
|---|---|---|
| G00 | Accepted plan and registers exist | Reconcile dates, links, PR state and immutable runtime evidence continuously |
| G01B/G01C | Verification preparation and independent-evidence workflow foundations | Actual authorised source/custody/reviewer decision; accepted corporate control/mandates only where used |
| G02 / P0-05 | Progressive onboarding implementation and synthetic proof | Real independent Principals, decisions, desired-state and PRIMARY Tenant readback |
| G04 / P0-04 | OIDC/BFF/session source plus dormant IAM client and authorisation seam | INT-02, human-context protocol, actual bounded grants and independent protected proof |
| G05/G15 / P0-06/07 | Content context convergence and CP transport source | Real workload, qualified provider/binding, INT-03, publication/revocation/rollback |
| G03/G06 / P1-01/02 | Finance baseline input and draft contract work | Shared #319/#321 unmerged; canonical/ERP acceptance and actual iDempiere accounting proof absent |
| G07-G09/G13 | Architecture/demand documented | Workforce/payroll/procurement/assets/governance contracts and provider decisions before feature code |
| G10/G11 / R2 | Billing/payment source with simulated/sandbox support | Production provider eligibility and invoice/payment/settlement/ERP reconciliation |
| G12/G14 / R3 | Relationship model and intelligence source | Explicit subsidiary reporting grants, accounting policy, qualified capability/data sources |
| G16-G18 | Infrastructure/source tooling | Real protected environment, recovery, signed G17 and release-specific G18 authority |

## Ordered implementation and exit plan

| Order | Work / owning repositories | Exact exit | Current disposition |
|---|---|---|---|
| 1 | Own Infrastructure #35, INT-02 | Every mandatory live scenario PASS, final-head Foundation/security/CI green, reviews resolved | IN PROGRESS; do not move to INT-03 |
| 1a | L4-IAM-02 workload audience and revocation / Infrastructure with IAM contract | Same registered client/subject/scopes; audience-only 401; disabled-client fresh grant denied; restored fixture and canonical-link revocation separately proved | Implemented source in this takeover; actual final-head job required |
| 1b | L4-IAM-01 / IAM + Infrastructure | Real human code/S256 callback, issuer/signature/audience/nonce/state validation, bad issuer/expired/nonce and replay denials | Not implemented by password-grant smoke |
| 1c | L4-CP-01 / Shared + CP + Infrastructure | Owner-approved matrix/contract treatment of missing PRIMARY Organisation; every negative on actual CP | Discrepancy unresolved; v1 context issuance must not be silently broken |
| 1d | L4-CP-02 / CP + provider + Infrastructure | Real provider/readiness/binding/contract-major/market positives; stale/wrong instance and missing grant negatives | No provider process in current profile; inserted ACTIVE row insufficient |
| 1e | L4-CP-03 / CP + Infrastructure | Parent, sibling, independently governed subsidiary and external cases denied without current authority | Only sibling covered |
| 2 | INT-03 / Nabhold + IAM + CP + CMS + Infrastructure | Pinned real BFF/callback/TLS Redis/CMS, published vs restricted preview, current authority/session revocation and canonical same-owner/delegated protocol | Depends on #35 acceptance; no invented endpoint or workload redemption of human-owned context |
| 3 | P0-03/04/05 controlled real onboarding / CP + IAM + authorised reviewers | Accepted real verification as operation requires; distinct accountable Principals; governed identity/Tenant acceptance, no production promotion | Protected execution evidence required |
| 4 | P0-06/07 R0 / CP + IAM + CMS + Nabhold | Qualified workload/binding, publication/cache rollback, cross-tenant negatives and signed R0 acceptance | INT-03 plus protected environment/operations |
| 5 | P1-01 Finance F1 / Shared then ERP | Reconcile #319/#321 overlap, mandatory schema/contract CI, steward/ERP decisions, canonical lifecycle truth | Open PRs, not provider support |
| 6 | P1-02 FinanceBaseline + iDempiere / ERP | Accountant-reviewed baseline, native ledger/trial-balance/reversal/closed-period/idempotency proof | Depends on accepted F1 |
| 7 | P1-03..06, then R2/R3 scopes | Accepted domain/provider contracts and per-release signed evidence | No frontend substitute for domain truth |

The operational lanes requiring authorised real humans or independent source evidence remain explicit blockers. No superadmin password or test seed is substituted. AWS staging is not required for developing the isolated L4 harness; it is required later where the release evidence says so.

## Open PR census

62 open PRs across the 17 programme/dependency repositories queried via paginated repository pull collections (100/page; each returned fewer than 100). This is a complete listing for those repositories at the snapshot, not a claim to cover unrelated organisation repositories. Dependency candidates were inventoried by metadata, not represented as line-by-line code audits.

| Repository | Open PRs | Disposition |
|---|---|---|
| nabhold | None | Dependency/tooling candidates; no release acceptance inferred |
| shared | [#321](https://github.com/baobab-platform/shared/pull/321), [#320](https://github.com/baobab-platform/shared/pull/320), [#319](https://github.com/baobab-platform/shared/pull/319), [#294](https://github.com/baobab-platform/shared/pull/294), [#293](https://github.com/baobab-platform/shared/pull/293), [#292](https://github.com/baobab-platform/shared/pull/292), [#291](https://github.com/baobab-platform/shared/pull/291), [#290](https://github.com/baobab-platform/shared/pull/290) | #319/#321 Finance F1 overlap; #320 Trade-A; others dependencies |
| baobab-cp | [#399](https://github.com/baobab-platform/baobab-cp/pull/399), [#398](https://github.com/baobab-platform/baobab-cp/pull/398), [#397](https://github.com/baobab-platform/baobab-cp/pull/397), [#396](https://github.com/baobab-platform/baobab-cp/pull/396) | Dependency/tooling candidates; no release acceptance inferred |
| baobab-iam | [#115](https://github.com/baobab-platform/baobab-iam/pull/115) | Dependency/tooling candidates; no release acceptance inferred |
| infrastructure | [#35](https://github.com/baobab-platform/infrastructure/pull/35), [#33](https://github.com/baobab-platform/infrastructure/pull/33), [#32](https://github.com/baobab-platform/infrastructure/pull/32), [#31](https://github.com/baobab-platform/infrastructure/pull/31), [#30](https://github.com/baobab-platform/infrastructure/pull/30), [#29](https://github.com/baobab-platform/infrastructure/pull/29) | #35 critical integration; others dependencies |
| baobab-cms | [#32](https://github.com/baobab-platform/baobab-cms/pull/32), [#31](https://github.com/baobab-platform/baobab-cms/pull/31), [#29](https://github.com/baobab-platform/baobab-cms/pull/29), [#28](https://github.com/baobab-platform/baobab-cms/pull/28), [#27](https://github.com/baobab-platform/baobab-cms/pull/27) | Dependency/tooling candidates; no release acceptance inferred |
| baobab-erp | [#97](https://github.com/baobab-platform/baobab-erp/pull/97) | Dependency/tooling candidates; no release acceptance inferred |
| baobab-payments | [#40](https://github.com/baobab-platform/baobab-payments/pull/40), [#39](https://github.com/baobab-platform/baobab-payments/pull/39) | Dependency/tooling candidates; no release acceptance inferred |
| baobab-subscriptions | [#42](https://github.com/baobab-platform/baobab-subscriptions/pull/42), [#41](https://github.com/baobab-platform/baobab-subscriptions/pull/41) | Dependency/tooling candidates; no release acceptance inferred |
| baobab-trade-docs | None | Dependency/tooling candidates; no release acceptance inferred |
| baobab-pulse | [#54](https://github.com/baobab-platform/baobab-pulse/pull/54), [#53](https://github.com/baobab-platform/baobab-pulse/pull/53), [#52](https://github.com/baobab-platform/baobab-pulse/pull/52), [#51](https://github.com/baobab-platform/baobab-pulse/pull/51), [#50](https://github.com/baobab-platform/baobab-pulse/pull/50), [#49](https://github.com/baobab-platform/baobab-pulse/pull/49), [#48](https://github.com/baobab-platform/baobab-pulse/pull/48), [#47](https://github.com/baobab-platform/baobab-pulse/pull/47) | Dependency/tooling candidates; no release acceptance inferred |
| baobab-regulations | None | Dependency/tooling candidates; no release acceptance inferred |
| baobab-trade | [#144](https://github.com/baobab-platform/baobab-trade/pull/144), [#142](https://github.com/baobab-platform/baobab-trade/pull/142), [#141](https://github.com/baobab-platform/baobab-trade/pull/141), [#139](https://github.com/baobab-platform/baobab-trade/pull/139) | Dependency/tooling candidates; no release acceptance inferred |
| thamani | [#24](https://github.com/baobab-platform/thamani/pull/24), [#22](https://github.com/baobab-platform/thamani/pull/22), [#16](https://github.com/baobab-platform/thamani/pull/16) | Dependency/tooling candidates; no release acceptance inferred |
| zuribeans | [#113](https://github.com/baobab-platform/zuribeans/pull/113), [#112](https://github.com/baobab-platform/zuribeans/pull/112), [#111](https://github.com/baobab-platform/zuribeans/pull/111), [#110](https://github.com/baobab-platform/zuribeans/pull/110), [#109](https://github.com/baobab-platform/zuribeans/pull/109), [#108](https://github.com/baobab-platform/zuribeans/pull/108), [#95](https://github.com/baobab-platform/zuribeans/pull/95) | Dependency/tooling candidates; no release acceptance inferred |
| equator-estate | [#18](https://github.com/baobab-platform/equator-estate/pull/18), [#15](https://github.com/baobab-platform/equator-estate/pull/15), [#8](https://github.com/baobab-platform/equator-estate/pull/8), [#7](https://github.com/baobab-platform/equator-estate/pull/7), [#6](https://github.com/baobab-platform/equator-estate/pull/6), [#5](https://github.com/baobab-platform/equator-estate/pull/5), [#4](https://github.com/baobab-platform/equator-estate/pull/4), [#3](https://github.com/baobab-platform/equator-estate/pull/3), [#2](https://github.com/baobab-platform/equator-estate/pull/2) | Dependency/tooling candidates; no release acceptance inferred |
| baobab-dev | [#47](https://github.com/baobab-platform/baobab-dev/pull/47), [#46](https://github.com/baobab-platform/baobab-dev/pull/46) | Dependency/tooling candidates; no release acceptance inferred |

**Task-related ownership:** #35 is the active implementation. Shared #319/#321 are related Finance dependencies and overlap, so review together before either is treated as landed canonical F1. #320 is independent Trade-A and is not a direct Nabhold holding-company dependency. Routine dependency/CI PRs are not blanket-merged; major runtime/toolchain upgrades require their own compatibility evidence.

## Current takeover increment

The workload proof temporarily mutates only the disposable realm's existing audience mapper, preserves its registered client and scopes, obtains a second genuine IAM token, independently introspects it, and demands CP's exact 401. It restores the mapper in `finally`, separately disables/restores the same client, observes token-issuance denial and verifies restored CP access. It records booleans and HTTP statuses only.

Client disablement proves refusal of **new issuance**. Immediate rejection of an already-issued self-contained JWT is not inferred; the separate CP canonical-link revocation ceremony remains required. Neither the mapper mutation nor the fixture is a new allowed production audience or scope.

**Rollback:** revert the source commit; fixture mutations are restored inside the probe and all Compose credentials/volumes are destroyed by the existing teardown. Do not run these fixture operations against a persistent realm.

## Validation register

- 69 INT-02 source/regression tests pass locally, including confounded audience negatives, missing/nonboolean evidence, transport failures and restoration on failure.
- 6 INT-01 source contract tests pass; static preflight and Python compilation pass.
- Local Docker is unavailable in this execution environment. Real acceptance is delegated to the existing Actions job, never replaced by mocks.
- Final-head live evidence and CI must be recorded before any merge. A BLOCKED or FAIL aggregate prohibits merge and prohibits proceeding to the next engineering task.

