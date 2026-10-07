# MP2-C staging workload release

This increment can be tested before an AWS account exists. It adds optional
workloads to the staging foundation and a manual OIDC plan/apply workflow. No
AWS resources are provisioned merely by merging it. `workload_release=null`
retains foundation-only behaviour. A supplied release creates prepared services
with zero tasks; `activate_workloads=false` is the default.

## What the code provides

- private CP, IAM, Pulse, Keycloak and APISIX Fargate services with private Cloud Map;
- service-specific security-group paths, including Keycloak→IAM evidence export;
- separate CP, Pulse and Keycloak PostgreSQL 17 Multi-AZ instances, TLS enforcement,
  encryption, backups and deletion protection;
- managed bootstrap database credentials, never granted to app task roles;
- HTTPS ALB→APISIX only, with a default deny response and explicit browser realms;
- private CP mTLS termination without modifying application authority semantics;
- a version-pinned protected-file initialization container;
- container readiness using verified TLS, client certificates and no redirects;
- single-writer IAM replacement, circuit breakers and encrypted EFS;
- offline release checks, read-only AWS preflight and runtime observations.

The root uses the existing foundation state boundary. It does not copy canonical
Shared provider/profile schemas into Terraform. The typed local release input
is a deployment configuration surface, not provider selection or identity.

## Account handoff

Prepare the following non-secret GitHub environment variables:

| Environment | Variables |
| --- | --- |
| `staging-plan` | `STAGING_ACCOUNT_ID`, `STAGING_PLAN_ROLE_ARN`, `STAGING_STATE_BUCKET` |
| `staging` | `STAGING_ACCOUNT_ID`, `STAGING_APPLY_ROLE_ARN`, `STAGING_STATE_BUCKET` |

Create both environments before dispatch. Protect `staging` with the required
reviewers and main-only deployment rules. AWS OIDC trust must restrict the exact
repository and environment subject, plus audience `sts.amazonaws.com`. Use
separate roles: plan reads staging infrastructure and prerequisite metadata;
apply changes only the staging resource boundary and may promote the exact
reviewed application manifests into the four application ECR repositories.
Neither role reads application secret values. No access keys belong in GitHub.

The encrypted S3 backend uses native lock files (`use_lockfile=true`). Give the
plan role read access to the state and the lock-file operations Terraform needs;
apply additionally needs state writes. Configure state-bucket versioning,
public-access blocking, TLS-only access and the reviewed KMS boundary before
initialization. Preserve the existing foundation state key. If an existing
backend uses DynamoDB locking, migrate locking deliberately; do not create a
second state for the same resources.

Review role policies against the actual plan. The workflow does not provision
account-bootstrap roles or silently assert that environment protection exists.
It does not run for a PR or on merge. Manual runs on main default to plan only;
apply consumes that run's checksum-verified saved plan after the staging gate.
Terraform rejects a stale saved plan if state changed during approval.

## Release inputs and artifacts

Publish app images in their owning repositories; infrastructure consumes them
without rebuilding. Build the infrastructure-owned helper from
the repository root with `docker build -f deploy/runtime-helper/Dockerfile .`
and scan it. The protected apply job promotes CP, IAM federation-authority, Pulse and
Keycloak directly from their reviewed GHCR digests into staging ECR; it never
rebuilds them. Pin the Linux/amd64 **platform manifest** digest, not a
multi-platform image index. Preserve build run, source revision, SBOM and
security/provenance evidence alongside each promotion. The plan-stage preflight
checks account/certificate/secret metadata without requiring not-yet-promoted
images. After promotion, the apply job performs the full ECR digest preflight
before Terraform can mutate runtime infrastructure.

The root requires all five services, a helper image, a real PostgreSQL 17 minor
version, public ACM certificate, public Route 53 zone and host, one or two public
broker realms, and three distinct TLS etcd endpoints. `master` is forbidden.
No public listener rule forwards `/admin`, `/internal`, APISIX Admin API, the
IAM federation authority or Pulse. Pulse is an internal capability provider;
consumer routing/bindings are intentionally outside this increment. IAM has no APISIX ingress rule. The browser CP prefix
is `/api/browser/*`; routes must still be governed and registered in CP/APISIX.

APISIX/etcd configuration is a separate reviewed management-plane dependency.
The accepted ADR requires durable quorum storage and stable member identities;
this change does not invent an ephemeral Fargate etcd cluster. Provide the
same-VPC etcd SG and approved durable three-member cluster before activation.
Its peer membership, backup/restore and authenticated transport require their
own evidence. The declared endpoints must match the actual APISIX configuration.

## Protected files

Each service references a Secrets Manager bundle ARN, immutable VersionId and
an exact list of flat filenames. The bundle value is JSON:

```json
{"files":[{"path":"config.json","base64":"<base64 of protected file bytes>"}]}
```

Use the complete declared list, including `ca.pem`, `service.pem`, `service.key`,
`probe.pem` and `probe.key`. Create real private PKI: service certificates need
appropriate DNS SANs; probe certificates need clientAuth and an accepted CA.
Keycloak bridge needs its independent mTLS identity, bearer-file admission,
PKCS12 stores and password files as documented in the IAM enterprise runbook.
Do not reuse the development fixture CA or fixture bearer.

The init container reads the exact version through the task role, validates the
file manifest, rejects traversal/duplicate fields and writes private files owned
by the service UID. It also copies the verified helper binary for distroless
health probes. Application startup depends on init **SUCCESS**. Failures print
only a generic denial; no secret value enters Terraform or a task definition.
UIDs are CP/IAM 65532 and Pulse/Keycloak/APISIX 1000. APISIX must use an approved artifact
that runs as UID 1000; its protected volume also supplies the writable config
folder required by the APISIX CLI. This folder is workload-private.

`_FILE` environment references may point only into declared protected files.
CP's `DATABASE_URL`, Pulse's `PULSE_DATABASE_URL`, `PULSE_IAM_CLIENT_SECRET`
(and optional `PULSE_QDRANT_API_KEY`), and Keycloak's supported database/bootstrap
credentials may use version-pinned ECS secret selectors. Those are runtime environment secrets,
not plaintext task-definition values. Other services receive credentials only
through the protected files. Rotate a bundle by publishing a new version and
reviewing the release change; immutable startup material requires task replacement.

Task roles can read only their bundle and explicitly declared secret CMKs. ECS
execution roles read only declared environment secret ARNs and image repos.
Apps must use least-privilege database users provisioned separately from RDS
bootstrap users. Run owning-repository migrations in a controlled one-off step;
this module does not invent application schema or grant master credentials to apps.

## Application configuration

| Service | Entrypoint and private health |
| --- | --- |
| CP | `/controlplane`; localhost HTTP 8080 behind helper mTLS 8443; `/healthz` |
| IAM | `/federation-authority -config /run/baobab/config.json`; HTTPS 8443 `/ready` |
| Pulse | image-owned Uvicorn entrypoint on localhost HTTP 8000; helper mTLS 8443; `/healthz` |
| Keycloak | `/opt/keycloak/bin/kc.sh start --optimized`; HTTPS 8443 and private management HTTPS 9000 `/health/ready` |
| APISIX | owning artifact's supported start command; HTTPS 9443 with configured `/healthz` |

Configure IAM's state directory as `/var/lib/baobab-iam` and explicit enterprise
mode. Use the UID-65532 EFS access point. Set reviewed native targets, finite
Shared canonical workload admissions, audience/scope pins and CP credentials.
CP, IAM and Pulse require actual canonical engine-instance/provider registrations and
approved references; dummy configuration must fail readiness. Publish the exact
IdentityProviderRuntimeProfile through the authoritative CP path and retain its
artifact/source/evidence identities. Terraform never marks a capability VERIFIED.

CP configuration must listen on localhost `127.0.0.1:8080`; its task SG exposes
only helper TLS 8443. Keep CP's canonical admission enforcement enabled. Configure
Keycloak's real public broker issuer, HTTPS certificate/key, trusted proxy
boundary and private evidence endpoint. Its bridge mapper must use FORCE sync
mode and the signed upstream claim configuration documented by IAM #75. APISIX
must validate private backend certificates and use its own client identity for
CP mTLS. Its Admin API and etcd stay in the private management boundary.


Pulse's private TLS sidecar preserves the image contract (HTTP :8000) while the
service boundary remains mTLS :8443. Its security group has no APISIX ingress.
It may call only the private CP/IAM/Keycloak authority surfaces declared by the
staging topology, plus the same private AWS API endpoints used for image/secret
materialisation. Pulse PostgreSQL is canonical persistence; Qdrant remains an
external/rebuildable semantic projection dependency and is not invented by this
infrastructure increment. A real activation manifest must provide the reviewed
Pulse IAM/Control Plane authority endpoints and least-privilege database secret
before `activate_workloads=true`.

ECS Exec requires a writable root filesystem, so app containers deliberately
retain one while dropping Linux capabilities. Protected app volumes remain
read-only except APISIX's private generated configuration. Minimal images may
lack the utilities ECS Exec needs for complete transcripts; verify the actual
operational logging path rather than claiming a transcript from the cluster flag.
No inbound SSH path is created.

## Validation and observations

Before account provisioning:

```sh
cd terraform/environments/staging
terraform init -backend=false -lockfile=readonly
terraform fmt -check -recursive
terraform validate
terraform test
```

The test fixture is synthetic, and mocked plans make no AWS calls. Helper race
and TLS tests and Python verifier negative tests run in CI.

After approved artifacts and account setup, add a reviewed manifest under
`deploy/releases/staging/`. First use `activate_workloads=false`, apply the
prepared stack, and bootstrap database roles/migrations and protected bundles.
Then review an activation release. The manual workflow runs metadata preflight,
plans, applies the saved plan when authorized, waits for service stability and
captures only normalized observations. Read-only CLI equivalents:

```sh
python deploy/verification/staging.py preflight --release <reviewed-manifest>
python deploy/verification/staging.py observe --release <reviewed-manifest> \
  --cluster baobab-staging-ecs --infrastructure-revision <git-sha> \
  --output staging-observation.json
```

Run `private_authorities.py` inside the private boundary using an admitted proof
workload and protected client credential files. Its config references private
CP/IAM origins, namespace, CA/client files, CP token file, exact CP binding
request, and the independently observed Keycloak image digest. It checks finite
current CP binding authority and IAM readiness and emits a protected evidence
file. It neither creates nor approves platform data.

Successful tasks, observations and authority probes remain
`operational_acceptance=false`. To close item 6, additionally perform the real
brokered OIDC login through the deployed browser path, approve the actual event
through independent human maker/checker evidence, consume it through live CP/IAM
canonical identity resolution and retain the resulting decision and replay-denial
proof. Repeat the bounded SAML path before claiming that facet live. Preserve
release hash, source/build/image digests, ECS revisions, CP profile revision,
finite evidence validity and operational verification identities. Never retain
codes, ID tokens, private keys, bearer credentials or raw SAML XML as evidence.

## Staging ledger boundary

IAM desired count is one, with deployment maximum 100% and minimum healthy 0%.
There is intentional replacement downtime. Do not autoscale or manually run a
second writer. EFS ownership now matches the deployed image. If an older
UID-10001 ledger directory already exists, stop all writers and perform a reviewed
offline ownership migration before mounting it; access-point creation metadata
does not rewrite an existing directory's ownership.

This is bounded single-writer staging durability, not shared production fencing.
Backup/restore, failover and replay recovery still require item 7 evidence.
