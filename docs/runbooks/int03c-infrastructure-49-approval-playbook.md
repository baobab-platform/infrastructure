# Infrastructure #49 — independent INT-03C approval, provisioning and witness runbook

**Classification:** governance and development-only operator procedure. **Current gate:** `APPROVAL_REQUIRED / RUNTIME_HELD`. This document is **not** an approval, instruction to bypass an owner gate, attestation or executed evidence.

**Authority:** [Infrastructure #49](https://github.com/baobab-platform/infrastructure/issues/49); Accepted [Shared EA v2.3](https://github.com/baobab-platform/shared/blob/main/docs/architecture/EA-implementation-plan-v2.3-2026-10-20.md); Accepted [Shared INT-03C decision](https://github.com/baobab-platform/shared/blob/main/docs/architecture/int03c-governed-proof-bootstrap-decision.md); [INT03C governed final gate](../../tests/platform-integration/int03/INT03C-GOVERNED-FINAL-GATE.md); CP, IAM, Infrastructure and Nabhold applicable accepted ADRs. Source-merged is not real-component qualification or production permission.

## 1. Decision rights, nominations and independence

The Nabhold Group Africa executive direction identifies **Wekhaso Nabusiu** as overall group business approver, including group-controlled subsidiaries. This is a *business mandate supplied for this work*, not an independently verified legal instrument or a CP/IAM entitlement. Each subsidiary retains its legal-entity authority, independently governed Tenant/Organisation, permissions and statutory obligations. The group approver cannot unilaterally waive those rights, technical safety checks, regulatory obligations or the independent engineering witness.

Four named **candidates** have been identified. No GitHub account, CP Principal, competence, delegation or personal consent has yet been independently established merely by naming them:

| Person | Proposed function for #49 | Preconditions for appointment |
| --- | --- | --- |
| **Wekhaso Nabusiu** | Group executive sponsor and exact-run **business go/no-go**; may be the independent run authoriser only after independent identity/role and security authority are verified | Authenticated, independently attributable written decision on exact packet digest; **no execution, maker/checker impersonation or self-attestation** |
| **Brian James Nabusiu** | **CP maker** / disposable runtime operator candidate | Personal, ACTIVE, specifically authorised CP human Principal; independent existing grants; privately held personal credentials; not a run approver or independent witness |
| **Brenda Adams** | **CP checker** / separate technical controls reviewer candidate | Distinct ACTIVE specifically authorised CP human Principal, distinct grants and credentials; reviews maker's exact digest and existing source/plan; must not approve own mutations |
| **Edo Watalu** | **Independent evidence-custody and teardown witness** candidate | Independently authenticated read-only provider/issuer/CP/Docker and immutable external custody access; does not provision, mutate, delete, operate or self-witness the test resources |

This mapping is **NOMINATED, NOT ACCEPTED**. Each person must accept through their own authenticated identity. Do **not** infer GitHub usernames from names (including the current issue author); do not share personal passwords, IAM subjects or CP human tokens. If a nominee lacks authority or independence, replace the *role* with a separately authorised qualified individual via a reviewed amendment, not a fictional role assignment.

**Minimum separation:** business/run authoriser ≠ runtime operator; CP maker ≠ CP checker; witness ≠ authoriser, runtime operator, maker or checker. The two CP human administrators must exist as separate ACTIVE authorised CP Principals *before* disposable workload creation. A security reviewer competent to inspect the isolation/threat model must countersign the topology; the CP checker may fill that review function only if separately qualified and not the plan's maker or runtime operator. GitHub PR approval alone never constitutes run approval.

## 2. Independent approval packet (private, reviewed, content-addressed)

Record an immutable **plan digest** (SHA-256 of the exact frozen packet) and secure each separate authenticated approval against that digest, **before the earliest creation or issuance**. Keep sensitive host details, secrets, identity subjects and network inventory in approved private custody; public issue comments carry only sanitized digests and evidence references.

The proposed operator packet must include all of:

1. **Purpose / scope:** `development`, synthetic only, `INT-03C`, Infrastructure issue `#49`, exactly one single-use run ID, explicit disallow of production/customer credentials and CMS #354 activation.
2. **Exact immutable sources:** Shared, IAM, CP, Infrastructure, CMS, Nabhold Git 40-hex commits; use `int03c-lock.json` for the current upstream pin set; Infrastructure execution SHA must be a clean descendant of its pinned baseline. Record clean checkout and mandatory CI/review results. Pin **built/runtime OCI image digests**, not mutable tags or merely Docker config IDs.
3. **Topology/threat model:** explicitly approved isolated nonproduction host/account, private network, only `https://cp.int03.test` and `https://hydra.int03.test` private CA-bound control endpoints, PostgreSQL, issuer, current CP ingress, resource-server endpoint, non-public administration, egress limits, no production route, no customer data.
4. **Actors / provenance:** authenticated group approver, independently approved run authoriser, security reviewer, *two distinct active CP human Principal IDs*, runtime operator, independent teardown witness and separate external evidence custodian. Include issuer/subject-to-CP Principal read-back plan, maker/checker proof and role-effective grants. No user-declared Principal UUID may substitute for CP GET.
5. **Privately retained authorisations:** signed or independently authenticated **APPROVE / REJECT** per approver, timestamp, principal/account identity, exact immutable plan SHA-256, run ID, requested scope and clock window, independent authorization reference and required conflict-of-interest checks. A prepared GitHub PR or unverified pasted text cannot serve as authority. Every actor must explicitly accept their role.
6. **Bounded execution:** unique random run nonce; absolute UTC start and hard deadline **no later than 90 minutes after start**; fresh per-run secrets with least privilege, short native Hydra lifetimes, separate signed verifier, durable owner-private create journal; *independent of the workload process* shutdown/restart/reconciliation controller with proof of external authority and tested deadline enforcement. No automatic renewal or silent retry into a new run.
7. **Actual governed synthetic CP path:** CP-owned AdmissionDecision, TenantOnboardingRequest and Organisation verification, CP-issued Tenant/Organisation/Principal IDs, two ACTIVE independent Tenants and distinct Organisations, market/grant/provisioning/provider evidence and live independent CP read-backs. No direct SQL, arbitrary UUID, mock issuer or self-certified legal status.
8. **Independent external evidence custody:** named write-once/object-lock capable destination and retention policy, custodian authentication, content hashes of *original sanitized issuer/CP/runtime creation and all seven-case receipts*, authorized read-only verifier retrieval/rehash, incident/recovery journal, key rotation and expiration/teardown evidence. Never retain tokens, private keys, credentials or sensitive legal records in repository/Actions uploads.

An approver must review the exact final immutable packet. **Any change** to sources, image digest, people/privileges, topology, secrets scope, window or custody voids prior packet approvals and requires a fresh approval cycle. A missing approver, reviewer, private host, credential, independently witnessed action or custodian means **HELD**.

## 3. Procedural gates (each requires an independent observation)

| Gate | Required action | Evidence / authority | On failure |
| --- | --- | --- | --- |
| **G0 Source** | Reconcile merged IAM #137, CP #427, Infrastructure #47/#48 and Shared registry, recheck exact-source CI/security/ADR pins | Independently examined commits, clean lock and mandatory workflow reports | HOLD |
| **G1 Role** | Individually authenticate/appoint nominees; verify actual two CP human operators, independent run authoriser and witness | Private role acceptance, CP Principal + effective grants read-back and separation matrix | HOLD |
| **G2 Topology** | Security review/threat model, cost/quota/data rules, approved provider isolation, public-network deny, CA and outside-the-process shutdown | Signed packet SHA-256 from authoriser and independent technical reviewer; independent witness agrees custody | HOLD |
| **G3 Provision** | Runtime operator creates *only* approved disposable host and real IAM/CP + actual governed synthetic CP resources | Original timestamped provider / issuer / CP create evidence; resource IDs independently retrieved, original hashes externally retained | STOP/CLEAN UP |
| **G4 Qualify** | Execute seven named live cases in [governed final gate](../../tests/platform-integration/int03/INT03C-GOVERNED-FINAL-GATE.md) | Real token issuance/introspection, active Principal, wrong audience and cross-tenant denials, **before-expiry** revocation and deactivation denials | FAIL/CLEAN UP |
| **G5 Teardown** | Independently stop externally accepting processes, revoke and destroy two native clients, terminalise CP resources, delete every owned image/container/network/volume/private secret | **Different witness**, raw original rehash from external custody, live provider/CP/issuer read-backs including 404 and no accepting credentials | FAIL/INCIDENT |
| **G6 Attest** | Independent technical reviewer + group approver examine actual originals, times and bounded run; explicitly record qualified/not-qualified | Separately signed immutable approval/acceptance record (or rejection), references to originals, evidence class `REAL_COMPONENT_SYNTHETIC_DATA` only if justified | OBSERVED_UNATTESTED |

Run scripts that offer `inspect` / preflight only establish **source or packet structure**, never authorization. No scripted or AI-created approval can act as a human signature. All resources must be disposed even after a failed run; a failed teardown stays open with an escalation owner, never silently marked clean.

## 4. Seven cases and stop conditions

Execute and retain **each** `iam_issued_token`, `cp_current_principal`, `wrong_audience_denied`, `cross_tenant_denied`, `revoked_credential_denied`, `deactivated_principal_denied`, `independent_teardown` with independent original-byte custody. Reuse actual implementation in `tests/platform-integration/int03/connected_identity_*` and `INT03C-GOVERNED-FINAL-GATE.md`; do not substitute mocks, synthesized issuer receipts or hand-edited PASS flags.

**Fail immediately** if the absolute deadline is exceeded, source pins drift, network isolation fails, a human Principal has no proven current role, independent witness unavailable, issuer revocation occurs only after natural expiry, CP deactivation did not atomically remove active links, cleanup cannot be independently read back or external custody fails. Capture an incident and independent recovery evidence rather than erasing the failure.

## 5. Status register and adjacent programme

At the time this runbook is written: **role nominations known; role acceptance NOT VERIFIED; topology NOT APPROVED; real deployment NOT PROVISIONED; seven cases NOT EXECUTED; external custody NOT ATTESTED**. IAM #137 and CP #427 are now merged; that is engineering source progress, not runtime approval.

The INT-03C result, even if later accepted, **does not activate** the separate development-only Shared #354 CMS consumer/validator or independently prove the fourteen NAB-03 cases. Shared #354 remains **HELD** and **NAB-03 14/14 BLOCKED** until their own owner-authorised activation and connected runtime acceptance.

**Issue update convention:** in [#49](https://github.com/baobab-platform/infrastructure/issues/49), record sanitized `plan_digest`, source SHA set, accountable actor identities (public handles only where consented), clock window, private evidence receipt IDs, decision and independent witness outcome. Do not post secrets, private infrastructure addresses, exact legal identity documents or token material. Separate `NOMINATED`, `APPROVED_FOR_DISPOSABLE_RUN`, `PROVISIONED`, `OBSERVED_UNATTESTED`, `ACCEPTED_REAL_COMPONENT_SYNTHETIC_DATA`, `BLOCKED` and `FAILED_TEARDOWN` statuses; no transition without preceding evidence.

## 6. Opening request and final closure

To authorise G1/G2, Wekhaso Nabusiu must personally confirm the exact business mandate and bounded disposable run packet through a verified signing/account route. Brian James Nabusiu, Brenda Adams and Edo Watalu must personally accept or decline their proposed independent functions; security reviewers must verify their competence and actual CP/provider permissions. This documented nomination **cannot stand in for those actions**.

After G6, close #49 only if independent custody and teardown proofs are accepted, the final disposition is explicit, and all relevant evidence links are retained. Otherwise keep #49 open. No production go-live is inferred.

## 7. Offline packet preflight (never a permission grant)

Use `tests/platform-integration/int03/int03c_approval_packet.py` to inspect a **private**, credential-free frozen packet against the exact committed `int03c-lock.json`. This is only a review candidate; actual CP/IAM and signer identity/role proof must be independently established before provisioning. Run:

```bash
python3 -B tests/platform-integration/int03/int03c_approval_packet.py \
  --packet /private/int03c-approval-packet.json \
  --lock tests/platform-integration/int03/int03c-lock.json
python3 -B -m unittest discover -s tests/platform-integration/int03 \
  -p 'test_int03c_approval_packet.py' -v
```

The packet requires **exactly** these top-level keys:

- `schema`: `infrastructure.int03c.infrastructure49.review-packet.v1`
- `issue`: `baobab-platform/infrastructure#49`
- `environment`: `development`; `synthetic_only`: `true`
- `run_id`: an independently randomly generated 32-character lowercase hexadecimal value
- `window`: `start_utc` and `deadline_utc` as actual ISO-8601 UTC timestamps, no more than 90 minutes apart
- `sources`: 40-character Git SHAs for `shared`, `baobab-iam`, `baobab-cp`, `baobab-cms`, `nabhold` and `infrastructure`; the first five must equal the committed INT-03C lock
- `image_digests`: actual `sha256:<64 hex>` OCI digests for at least `cp`, `iam`, `postgres` and `verifier`, plus every other run-critical service
- `roles`: one object per `executive_approver`, `run_approver`, `security_reviewer`, `cp_maker`, `cp_checker`, `runtime_operator`, `independent_witness`, `evidence_custodian`; each has exactly `person` and `authenticated_actor_ref` (the verified, non-secret stable identity reference)
- `topology`: `private_host_ref`, `private_network_ref`, `threat_model_ref`, `private_ca_sha256` (64 hex), `external_deadline_supervisor_ref`, `external_immutable_custody_ref`, `custody_retention_policy_ref`, `cp_origin`, `hydra_origin` (the exact private `.int03.test` HTTPS origins defined above)

Never commit a completed private packet. No credentials, production resource names or private grant details belong in tracked JSON. A zero exit code reports only `STRUCTURAL_REVIEW_ONLY` with `authorised=false` and `APPROVAL_REQUIRED_RUNTIME_HELD`; the canonical `plan_sha256` printed must be bound to **separate independently authenticated approvals outside this source preflight**. A valid format neither proves real identities nor supplies an approval. Changing a packet after signatures invalidates them.

The preflight cannot verify source ancestry, signed decision authority, source/image-to-running-instance matches, CA trust, live grant read-backs, actual external WORM retention or external supervisor operation. Those checks remain G0–G6 independent operator responsibilities. Missing one means no execution.
