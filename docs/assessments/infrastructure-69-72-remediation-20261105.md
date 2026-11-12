# Infrastructure #69 / #72 — joint engineering audit and remediation

5 November 2026 · EA v2.3 / EA-DEV DEV-04, DEV-07, DEV-11, DEV-14 · development only

**Acceptance:** Source/isolated component checks are distinct from
connected qualification. IAM-N02/N07 and L4-OPS-01 remain **BLOCKED**.
Neither PR may be used as staging/production activation authority.

## Reviewed changes and source custody

- [Infrastructure #69](https://github.com/baobab-platform/infrastructure/pull/69):
  original checked head `45a71c0177ca6122ff2b3a4911d3c66bdca85548`;
  N02 first-party HTTPS, private Hydra/Kratos/CP state and N07 Redis
  component candidates. N02 pinning retains accepted Shared #430, CP #455
  unmerged candidate, IAM #147 and accepted ZuriBeans main. N07
  additionally binds IAM #152, Thamani #44 and TMS #28. These intentionally
  separate candidate locks must not be overwritten by DEV-11's six-owner
  BFF/Trade/runtime pins; they represent different reviewed consumers.
- [Infrastructure #72](https://github.com/baobab-platform/infrastructure/pull/72):
  original checked head `f5fea1ef774190eb7de9554e07154f886c3bced3`;
  DEV-11 source/OTLP/Jaeger/broker and independent evidence custody.
  Its six-owner manifest and connected BFF runner have been refreshed to
  ZuriBeans `e171ede6cbb9512359266e85870e297c5a1e4361`,
  IAM `ba2100304f9fdabee5308b72d6ff5cbbd3d30ce8`,
  CP `e461b9e2c3a3f0cdd0c2f8b909c263c627f128be`,
  Trade `4df942719b14cbdcdb81160f11d75d858f1f94cc`,
  ERP `93d2ac51fb07f9afcdfb958fe2df2c94f5484746`.
  This manifest is one immutable candidate snapshot, not a permanently
  current pointer; later owner commits require a new source-specific review.

## Errors corrected

| Control | Defect | Remedy | Acceptance consequence |
|---|---|---|---|
| #69 N07 Redis original | JSON parsed from one file open, SHA taken from a second open | Same private, owner-only inode read+hash; refuse symlink, hardlink, group rights, oversized and duplicate-key originals | No new issuer/consumer acceptance |
| #69 Redis probe | `lstat` followed by a distinct `read_bytes` open | Use `O_NOFOLLOW`, `fstat`, 1MiB cap, owner-only mode and duplicate-key refusal on original probe state | Live TLS Redis component remains only a component |
| #72 exact source admission | `git status --untracked-files=no` allowed injected unchecked files | All tracked and untracked source changes now refused | Exact-HEAD identity stronger, not production proof |
| #72 candidate pin drift | Trade, ZuriBeans and ERP head pins no longer matched current owning PRs | Refresh six-owner lock, BFF workflow and six-source workflow together; test SHA/Action parity | Previous original runs are **not** reused |
| #72 six-owner CI | Deterministically red PR job even after successful source checks, because no actual runtime was provisioned | PR now reports bounded source-only BLOCKED receipt; manual connected qualification still fails closed without private original event, live network, issuer and native evidence | CI source green must not be reported as L4 green |
| #72 run isolation | Shared network name check admitted extra host bridge/ports | Require only one genuine Compose-owned Internal network, no published host ports/privileged/host networking | Private lab topology strictly verified |
| #72 private image/event custody | Path checks could be raced between read and validation | Owner-only `/run/private` direct-child original opened with `O_NOFOLLOW`; same-inode size/owner/mode and duplicate JSON checks | No acceptance from a forged source receipt |
| #72 exported Jaeger graph | Required span names could be unrelated siblings connected only by a generic root | Check concrete BFF→IAM, IAM server/client, Trade→CP, CP→introspection, outbox→publisher and actual consumer origin parents | Synthetic/misattributed graph denied |
| #72 exported privacy | Arbitrary span keys/values might contain secrets, PII, SQL or headers | Reject sensitive keys and bearer/password-looking values in independent OTel evidence | Privacy violations are independent L4 blockers |
| #72 static review | Unused `copy` import and unused `lock` variable | Remove without changing runtime semantics | Code-quality cleanup |

## Execution classification and remaining gates

On the inspected **pre-remediation** heads, #69's eight core source/component
workflows passed. On #72 the owner source/observability and BFF/CP component
jobs passed, but the six-owner genuine buyer job failed at absent authenticated
commit entrypoint under its then-pinned historical Trade/ZuriBeans sources.
This failure was **not** a positive business transaction. After changes,
run/final-head CI must be checked again; old green checks do not carry forward.

All remaining real-positive acceptance requirements stay intact:

1. N02: actual same-origin Playwright/Kratos/Hydra browser AAL2 and session
   cases; independently CP-verified ACTIVE human Principal and exact original
   seven-case/teardown evidence.
2. N07: real operator/market/tenant authorisation, Thamani confidential
   client, native TMS booking and independently held provider/Redis custody.
   Redis GETDEL is not cross-worker confidentiality or booking acceptance.
3. DEV-11: real governed tax/freight/duty issuer, consequential IAM/CP
   buyer commit and non-draft Medusa order/seller/buyer spend/outbox XID;
   unchanged original event through RabbitMQ and real iDempiere JVM effect;
   independently queried exported trace, legal/mandate negative tests,
   recovery and secure teardown.
4. Eight-owner evidence custody must verify the current exact source heads
   and unchanged negative scenarios independently before changing
   `L4-OPS-01` from BLOCKED. Synthetic buyer-origin refusal remains in force.

**Protected environments:** no staging/production change, automatic merge,
provider success waiver, identity grant or false accepted evidence was made.


## 2026-11-12 checkout configuration audit

Reviewed Infrastructure #72 at `749166768633d8c8a36fd496a3f878b673f5ff87`.
Its 16 successful PR workflows do not establish the dispatch-only genuine
six-owner transaction or the independent eight-owner acceptance join. #69
at `4417e24adefce0e214281830f5093c56fea8b0fb` likewise retains N02/N07
browser and native-owner qualification obligations despite green CI.

Corrected `dev07_checkout_configuration.py`: the previous PEM wrapper and
base64-character check accepted arbitrary bytes as an Ed25519 public key.
Configuration now requires the exact RFC 8410 SubjectPublicKeyInfo encoding
(id-Ed25519, absent algorithm parameters, 32-byte public-key BIT STRING),
valid canonical base64, and no appended DER data. This is structural key
validation, not issuer authorization or proof of possession. The existing
Trade signature verification and IAM/CP authority remain required.
Reference: https://www.rfc-editor.org/rfc/rfc8410.html sections 3, 4 and 10.1.

Endpoint configuration now rejects whitespace and ASCII control characters
before URL parsing, preventing parser normalization from hiding input changes.
The existing HTTPS, private hostname, path, credentials and query restrictions
remain in force. Regression cases cover arbitrary bytes, X25519 algorithm
substitution, truncated/appended DER and stripped URL controls. The public
positive fixture is RFC 8410's published example, not a generated credential.

Validation: all 253 development harness unit tests pass locally, including 15
checkout configuration/witness tests. These are source regressions only; no
buyer order, approval, private credential, ERP effect or runtime acceptance
was fabricated. Final-head CI must rerun after publication. Both Infrastructure
merge gates remain held pending their original connected evidence.
