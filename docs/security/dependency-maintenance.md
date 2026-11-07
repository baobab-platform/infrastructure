# BA-SEC-DEP-001 — Infrastructure dependency/security maintenance audit

**Authority:** [Approved Baobab Dependency & Security Maintenance Policy v1.0 — Shared #429](https://github.com/baobab-platform/shared/pull/429). Shared's proposed *strict* validator is not yet released; this repository consumes only accepted Shared baseline SHA `31de2bc3dcd56128c019c640dc7e12c10ae9ca69` plus owner-local tests.

**Review date:** 7 November 2026. **Status: SOURCE_COMMITTED only.** CI_VERIFIED, SECURITY_ALERT_PATH_VERIFIED, CONSUMER_QUALIFIED, STAGING_VERIFIED and PRODUCTION_VERIFIED have **not** been demonstrated. A failed/unknown audit is BLOCKED; WAIVED is not PASSED.

## 1. Observed manifest inventory and bounded bot coverage

| Real source | Dependabot ecosystem and owning directory | Additional obligation |
| --- | --- | --- |
| GitHub Actions workflows | `github-actions /` | Pinned actions, least-privilege roles, independent advisories |
| `go.mod` and `go.sum` | `gomod /` | AWS SDK Go v2, runtime-helper TLS |
| `terraform/environments/staging/versions.tf` and `.terraform.lock.hcl` | `terraform /terraform/environments/staging` | Locked AWS provider; never automatic apply |
| `tests/platform-integration/devcontainer-cli/package.json` + lock | `npm /tests/platform-integration/devcontainer-cli` | Disposable Dev Containers CLI |
| `tests/platform-integration/int02/human/package.json` + lock | `npm /tests/platform-integration/int02/human` | Real Playwright/JOSE/OIDC consumer |
| `deploy/runtime-helper/Dockerfile` | `docker /deploy/runtime-helper` | Digest-pinned Go builder, scratch runtime |
| `.devcontainer/platform-integration/Dockerfile` | `docker /.devcontainer/platform-integration` | Integration laboratory and its dependencies |
| `tests/platform-integration/int02/human/Dockerfile` | `docker /tests/platform-integration/int02/human` | Human/OIDC browser container |
| `compose/compose.yaml` | `docker-compose /compose` | Local APISIX, PostgreSQL 17, RabbitMQ, Redis, etcd |
| `tests/platform-integration/compose.yaml` | `docker-compose /tests/platform-integration` | INT-01 disposable L4 dependencies |
| `tests/platform-integration/int02/compose.yaml` | `docker-compose /tests/platform-integration/int02` | IAM/CP/Ory/TLS integration lab |
| `tests/platform-integration/int03/compose.yaml` | `docker-compose /tests/platform-integration/int03` | Nabhold overlay and TLS Redis |

The `terraform/versions.tf` root declares the Terraform tool constraint but no provider. Provider dependencies and the lockfile belong to staging; do not manufacture a root Terraform provider update. Python scripts alone do not justify a `pip` ecosystem without an owned package-manager manifest. The root is not an npm package; its two actual npm consumers are separate.

Routine updates are weekly and staggered on Monday Africa/Johannesburg. All entries have finite, nonzero PR limits, labels and commit prefixes. The two optional Action/Go routine groups use `applies-to: version-updates` and only patch/minor; majors and security alerts receive distinct review. No `target-branch` override, blanket ignore or automatic major-grouping has been introduced.

## 2. Native security checks, not runtime acceptance

New `.github/workflows/dependency-security.yml` runs on pull requests, main and daily:

- Native Go vulnerability analysis is pinned to `govulncheck@v1.1.4` and reads `go.mod` through a pinned setup-go Action; the tool release was checked against the upstream project release.
- Each locked npm consumer is independently installed with `npm ci --ignore-scripts --no-audit --no-fund` and runs a full `npm audit --audit-level=high`. Do not omit development dependencies or ignore audit failures.
- Terraform uses immutable setup-terraform source and version 1.16.5 to execute `fmt -check`, `init -backend=false -lockfile=readonly` and `validate`. It has **no AWS credentials, OIDC role, remote state, plan, apply or destroy**. Validation and checksums are **not** a Terraform vulnerability scanner or protected-plan evidence.

The accepted Shared validator is now called with six required ecosystems, supplemented by manifest-aware and negative local policy tests. The existing Foundation workflow has `dependency_review_enabled: false`. Confirm whether the GitHub dependency-review control can be enabled and actually works; absence of that evidence is an explicit security qualification gap, not a PASS.

## 3. Supplier-chain/security concerns that remain

**Dynamic Compose images:** INT-01/02/03 Compose files commonly take run-scoped image values from environment variables and immutable lock/checkout inputs. Dependabot may recognize the Compose file while being unable to update those dynamic image references. Reconcile the exact resolved Docker digest, owner, published provenance and actual connected consumer readback. An entry's presence is not proof every image is covered.

**Mutable published images:** Main `compose/compose.yaml` uses named published tags for infrastructure services; `.devcontainer/devcontainer.json` uses a Baobab developer image tag. Scan each resolved image for OS and library vulnerabilities, reconcile release publisher and immutable digest, and qualify any upgrades with L4/DEV-11 negative tests. Do not invent new digests or mass-replace tags in this source policy increment.

**Terraform provider advisories:** Staging locks `hashicorp/aws` to `6.67.0`. Its lockfile hashes guarantee installed artifact identity, not that no provider advisory exists. Read-only init/validate cannot close provider-vulnerability surveillance. Independent inventory and approved mitigation are outstanding.

**Existing narrow secret-scan exceptions:** `.gitleaksignore` contains one fingerprint for a historical Compose environment-variable reference. `.gitleaks.toml` has an anchored Keycloak SBOM metadata allowlist. These are not broad dependency-advisory suppressions and remain unchanged. Independently confirm their false-positive evidence, responsible Security reviewer and bounded disposition; do not extend them silently.

**Protected environments:** Infrastructure's staging release workflows use separate plan/apply environments, OIDC trust, strict release manifests, saved-plan custody and explicit `inputs.apply`. They are untouched. No new security workflow receives deploy credentials. Existing DEV-11/DEV-14 runtime qualification, IAM/CP authority, independent exported traces, durable broker replay and PostgreSQL 17 recovery remain separate acceptance gates.

## 4. Evidence exit

1. Run the policy source tests, accepted Shared validator, daily native scans, existing Foundation checks and existing integration/CI at the **final PR commit**.
2. Independently check actual Dependabot service jobs, GitHub dependency graph, Alerts, automatic security updates, provider recognition and supply-chain permissions. Source YAML alone never activates those features.
3. Investigate HIGH/CRITICAL alerts using current CVE/GHSA, reachability, installed image/library version, available fix, owner and response deadline. Expiring independent exception records are required for any unremediated exposure; never relabel WAIVED or unknown as PASSED.
4. Requalify the protected runtime-helper, INT-01/02/03 identity/supplier barriers, DEV-11 original event lineage and lost-result replay, DEV-12 PostgreSQL volume refusal/recovery and DEV-14 engine-revocation negatives before declaring CONSUMER_QUALIFIED.
5. Retain staging/prod approval, Terraform apply, secrets and provider setup strictly outside this maintenance PR. No staging or production decision follows from source-policy conformance.

**No CI execution or monitoring, PR merge, protected deployment or runtime/provider acceptance is claimed by these changes.**
