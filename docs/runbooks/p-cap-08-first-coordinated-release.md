# P-CAP-08 first coordinated release: audit and remaining execution

Audited 7 October 2026. Pulse main is
`b355bfa1139efb5e72ac0895a36b49fb1f2e4bc2`; Infrastructure base is
`2b52fe271838b38b92047ebb61ea616cb35e8276`.

## Verified selection

The proposed Infrastructure cut is `v0.1.0-staging`. Its five-component selection
is `deploy/releases/staging/v0.1.0-staging.coordination.json`. No Infrastructure
tag has been created and no account manifest has been manufactured.

| Component | Component tag | Successful publisher run | Retained receipt |
| --- | --- | --- | --- |
| Shared | v2.4.1-staging | [37657980282](https://github.com/baobab-platform/shared/actions/runs/37657980282) | shared.receipt.json |
| Control Plane | v1.1.1-staging | [37657752479](https://github.com/baobab-platform/baobab-cp/actions/runs/37657752479) | cp.receipt.json |
| IAM federation authority | v0.1.1-staging | [37670519453](https://github.com/baobab-platform/baobab-iam/actions/runs/37670519453) | iam.receipt.json |
| Keycloak | v0.1.1-staging | Same IAM run | keycloak.receipt.json |
| Pulse | v0.1.0-staging | [37627757084](https://github.com/baobab-platform/baobab-pulse/actions/runs/37627757084) | pulse.receipt.json |

All tags resolved to the selected source commits. Every publisher was completed
successfully at the exact tag/SHA. Downloaded receipt identities matched the
selection and every downloaded ZIP hash matched GitHub artifact metadata.
Receipts and SPDX SBOMs are preserved in
`deploy/releases/staging/evidence/v0.1.0-staging/`; `publisher-verification.json`
records run IDs, archive digests and receipt/SBOM digests. This is a dated audit
snapshot, not approval, deployment evidence or a replacement for live checks.
The original Actions artifacts expire on 22 October 2026. Deployment must still
retrieve and validate the publisher receipts; copied evidence does not bypass
expired/missing artifacts. Resolve retention before a delayed cut.

Verify the selection independently of an AWS account manifest:

```bash
python deploy/verification/release_cut.py \
  --coordination deploy/releases/staging/v0.1.0-staging.coordination.json \
  --output staging-selection-verification.json
```

Use the **Verify Coordinated Staging Selection** workflow on reviewed main for
the same read-only check. It uses the existing narrowly scoped
`STAGING_RELEASE_READ_TOKEN` for private cross-repository reads. It has no AWS
role, registry-write permission or governance authority. The deployment path
continues to verify the selected identities against the account manifest.

## Capability audit

| Capability | Repository result | Runtime acceptance still needed |
| --- | --- | --- |
| intelligence.evidence.search@1 | IMPLEMENTED; workload authentication, CP context redemption, exact operation scope, classification clearance, tenant-scoped retrieval and canonical hydration are present | Actual IAM/CP authority path, PostgreSQL and Qdrant, tenant/classification isolation and dependency failure behavior |
| intelligence.research-mission.manage@1 | IMPLEMENTED; CREATE/GET, durable tenant-scoped persistence, idempotency, atomic audit and held event persistence are present | Actual IAM/CP authority path, migrated PostgreSQL, concurrent duplicate convergence and cross-tenant non-disclosure |

Local verification under Python 3.14.7: 163 passed, four live PostgreSQL tests
skipped; Ruff passed; strict mypy passed for 133 source files. Earlier exact-main
Pulse CI is green and configured to run with PostgreSQL/Qdrant service containers.
Local skips are not independent live staging evidence.

The selected CP revision already contains immutable EngineRelease recording and
provider capability certification handlers. Recording does not approve, desire
or deploy. Certification resolves a human actor; the release recorder cannot
certify their own release (`CERTIFICATION_MAKER_CHECKER_REQUIRED`). No runtime CP
endpoint or authenticated governance principal was available in this audit.

## Account input handoff

Create `deploy/releases/staging/v0.1.0-staging.tfvars.json` only from real reviewed
inputs. `terraform/environments/staging/workload_variables.tf` is the input
contract. The synthetic release fixture must never be promoted to a real manifest.

| Input group | Required facts and preparation |
| --- | --- |
| AWS and state | Actual staging account; af-south-1; state bucket; separate OIDC plan/apply role ARNs; etcd security group |
| Registry targets | Existing same-account ECR repositories for CP, IAM federation authority, Pulse and Keycloak; use exact selected image digests and source revisions |
| Additional artifacts | Approved immutable ECR helper and APISIX images, with real source revisions; the five-component selection does not supply these |
| DNS and PKI | Issued ACM certificate, public hostname, public Route53 zone; private service/probe PKI; immutable bundle ARNs and version IDs |
| PostgreSQL | Available PostgreSQL 17 minor version and instance class; database roles, credentials and applied CP/IAM/Keycloak/Pulse migrations |
| Pulse dependencies | Reachable Qdrant endpoint and protected API key where required; real HTTPS issuer/JWKS/token URLs; real HTTPS CP context-validation endpoint; registered baobab-pulse-workload client and independently scoped validator credential |
| Gateway and etcd | Three distinct TLS-authenticated etcd endpoints; gateway configuration; one or two permitted browser realms; protected bundle files |
| Service runtime | CPU/memory, entrypoint/command, TLS server name, required health path, environment and version-pinned secret_environment references for all five ECS services |
| Protected workflow setup | STAGING_ACCOUNT_ID, STAGING_PLAN_ROLE_ARN, STAGING_APPLY_ROLE_ARN, STAGING_STATE_BUCKET in the correct environments; restricted tag rules and staging approvals; cross-repository read token |

The preflight now checks the version metadata of **every** separately referenced
credential as well as protected bundles. It does not read secret values. This
catches missing Pulse validator/database credentials before Terraform apply.
Metadata cannot prove a JSON key or secret contents are correct; bootstrap and
authenticated runtime checks remain necessary.

## Deployment and runtime proof

1. Review the real manifest with `activate_workloads: false` for preparation.
   Do not cut an Infrastructure tag while the required manifest is absent.
2. Run offline manifest validation and live five-component selection verification.
   Review a saved Terraform plan under the protected staging-plan role.
3. Use the protected staging apply path to promote the selected GHCR bytes into
   ECR, verify digest equality and apply the saved plan. Bootstrap the databases,
   private PKI, credentials and gateway before enabling tasks.
4. Review a subsequent manifest with `activate_workloads: true`, preserving
   immutable artifact identities. Use the reviewed manual main preparation/
   recovery path or a fresh immutable Infrastructure cut for later state changes;
   never move/reuse a release tag.
5. Capture fresh ECS observations from the deployed account. Require healthy,
   stable tasks with exact image/helper digests and matching task definitions.
6. Probe Pulse `/readyz` from the authorised private network. Require database
   readiness; evidence-search qualification also needs semantic retrieval ready.
   ECS `/healthz` is liveness only. Neither response alone proves authenticated
   workload authority or capability qualification.
7. Execute authenticated capability checks with the actual deployed authorities
   and persist immutable reports. Report dependency failures, cross-tenant
   non-disclosure, clearance enforcement and idempotency results accurately.

An ECS observation is infrastructure construction evidence. Map the real
deployment to registered CP EngineInstance identity and submit health/deployment
observations using authorised infrastructure tooling; do not invent canonical
IDs or equate the local observation JSON with accepted CP state.

## Governed closure

| Step | Required authority/evidence | Completion condition |
| --- | --- | --- |
| EngineRelease registration | Registered Pulse engine/provider, exact source and immutable artifact/provenance facts | Real CP release_id returned; retained recording audit |
| EA-09 evidence | Content-addressed HTTPS/OCI contract, integration, security and operability evidence for the exact production-bound release | Qualification evidence meets ea-09/pulse-intelligence-v1 |
| Two certification records | Human provider:certify authority independent of the release recorder | One current release-bound record per capability major |
| ENGINE_RELEASE_APPROVAL | Governed authorised approval and applicable release policy | CP approval recorded for the intended release/environment |
| Desired/observed convergence | Correct EngineInstance, desired release and fresh observed artifact/deployment state | Canonical CP readiness and release convergence proven |
| PROVIDER_ACTIVATION | Governed authorised activation of baobab-pulse.core | Activation completed after applicable prerequisites |

Staging does not require production EA-09 certification. Production certification
must bind the production-bound EngineRelease; a staging publisher receipt is not
a certification report. No certification or approval request is sent by this
implementation, because live deployment reports, canonical IDs and independent
human authority are not available.

CapabilityBinding, CapabilityGrant, tenant Intelligence-scope allocation and tenant
routing are outside P-CAP-08. The research-mission-created event remains
`HELD_UNREGISTERED`; deployment does not register or publish it.
