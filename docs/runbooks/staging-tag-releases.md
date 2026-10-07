# Coordinated staging tag releases

A strict `vX.Y.Z-staging` tag triggers component publication in Shared, CP, IAM and
Pulse. The matching infrastructure tag triggers the deployment of a reviewed
manifest; it does not build application images. Component version numbers may
be different: the coordination file selects them explicitly. No component
repository directly mutates AWS or uses a cross-repository dispatch PAT.

## Cut procedure

1. Merge the relevant source changes and wait for successful main Foundation CI.
2. For Shared npm publication, prepare and merge Changesets staging prerelease
   versions (for example `1.2.3-staging.0`) and consume pending changesets. The
   staging workflow refuses stable package versions and never increments a
   version during publication. Normal package publication excludes staging tags.
3. Cut component tags on reviewed commits contained in main. A repository-native tag cutter may explicitly dispatch the publisher at that immutable tag when GitHub's `GITHUB_TOKEN` recursion guard suppresses a tag-push workflow. The coordinator accepts either the direct tag-push run or that exact-tag `workflow_dispatch`; in both cases tag, source SHA, receipt and digest must match. The tag publishers
   test/scan, build once, publish to GHCR, attest and retain an SPDX SBOM and
   `staging-image.json` receipt. Pulse publishes its `baobab-pulse` runtime
   receipt under the explicit `pulse` artifact suffix. IAM produces two distinct
   artifacts: native federation-authority and Keycloak. Stable aliases are never moved.
4. Wait for **all** selected tagged publisher workflows to succeed. Download
   their receipts from the Actions artifacts. A failed partial publication
   requires investigation and a fresh version, not overwriting existing tags.
5. Promote the exact Linux/amd64 image manifests into the account's ECR without
   rebuilding or changing the digest. Prepare the helper and APISIX images using
   their existing approved promotion procedures. ECR preflight verifies their
   availability; these images are not rebuilt by the platform tag workflow.
6. Submit a reviewed infrastructure PR containing:
   - `deploy/releases/staging/v1.2.3-staging.tfvars.json`: the complete existing
     typed workload release input, including immutable ECR digests, configuration
     and secret-version references. Set `activate_workloads` deliberately.
   - `deploy/releases/staging/v1.2.3-staging.coordination.json`: component tag,
     source revision and platform digest selections in the format below.
7. Merge, then cut the infrastructure `v1.2.3-staging` tag on that reviewed commit.
   The workflow verifies the tag is contained in main, resolves each component
   tag (including annotated tags), requires a successful matching publisher run,
   checks its receipt and compares runtime ECR digests/source revisions before
   acquiring AWS credentials. Missing or inconsistent selections deny deployment.
8. Approve the protected `staging` environment after the saved plan is ready.
   All staging applies use one concurrency group and the same locked state key.
   Readiness observations do not substitute for federation operational proof.

Coordination metadata is an infrastructure release-cut input, not a replacement
for Shared's canonical EngineRelease contracts or CP release approval. This
workflow never records a CP release as APPROVED or manufactures human governance
or federation evidence.

## Coordination file

```json
{
  "release_tag": "v1.2.3-staging",
  "components": {
    "shared": {"tag": "v1.2.3-staging", "source_revision": "<40 lowercase hex>", "digest": "sha256:<64 lowercase hex>"},
    "cp": {"tag": "v1.2.3-staging", "source_revision": "<40 lowercase hex>", "digest": "sha256:<64 lowercase hex>"},
    "iam": {"tag": "v1.2.3-staging", "source_revision": "<40 lowercase hex>", "digest": "sha256:<64 lowercase hex>"},
    "pulse": {"tag": "v1.2.3-staging", "source_revision": "<40 lowercase hex>", "digest": "sha256:<64 lowercase hex>"},
    "keycloak": {"tag": "v1.2.3-staging", "source_revision": "<40 lowercase hex>", "digest": "sha256:<64 lowercase hex>"}
  }
}
```

The placeholders are documentation only. Real manifests must contain verified
receipts, existing account references and approved configurations.

## Account and GitHub prerequisites

Keep the setup in `mp2c-staging-workloads.md`: account/backend variables,
separate plan/apply OIDC roles, ECR, PKI, database bootstrap and durable etcd.
Configure the protected `staging-plan` and `staging` environments to allow only
reviewed main and strict staging tags. Use tag rulesets to restrict creation,
updates and deletion. The OIDC trust subjects remain the protected environment
subjects (`repo:baobab-platform/infrastructure:environment:staging-plan` and
`...:environment:staging`), not an unrestricted organization-wide tag subject.

Set `STAGING_RELEASE_READ_TOKEN` in infrastructure to a narrowly scoped GitHub
App installation token or fine-grained token able to read contents and Actions
artifacts in Shared, CP, IAM and Pulse. It is used solely for verification, never for
repository writes or AWS. Private cross-repository artifact reads cannot rely
on infrastructure's own `GITHUB_TOKEN`. Plan credentials have no secret-value
read capability. GHCR publishers require package creation/write permission and
GitHub artifact-attestation availability for the repository.

The existing main-only manual release workflow remains available for reviewed
preparation/recovery. It does not automatically select component releases.
`staging-deploy.yml` is now callable only and cannot independently deploy
from a second tag trigger or use a competing Terraform backend.

No staging or release tags are created by this implementation. No AWS deployment
or account configuration is performed by merging the workflow changes.
