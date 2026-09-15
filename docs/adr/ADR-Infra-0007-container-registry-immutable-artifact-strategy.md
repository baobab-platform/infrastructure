# ADR-Infra-0007 --- Container Registry and Immutable Artifact Strategy

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0001 --- Environment Provisioner Boundary
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0003 --- Terraform Architecture and Module Strategy
    -   ADR-Infra-0006 --- Production Compute Platform
-   **Follow-on:** ADR-Infra-0008 --- DNS, TLS, Edge and API Gateway
    Architecture

------------------------------------------------------------------------

## 1. Context

Baobab is a polyrepo/polyglot platform whose production workloads
execute primarily as containers on Amazon ECS with AWS Fargate.

Application repositories include platform services, engines and digital
estates such as:

-   `baobab-cp`;
-   `baobab-iam`;
-   `baobab-trade`;
-   `baobab-erp`;
-   `baobab-cms`;
-   `baobab-pulse`;
-   ZuriBeans;
-   Thamani;
-   future Baobab workloads.

A production deployment must identify exactly which artifact was built,
tested, approved and executed.

Mutable tags such as `latest` cannot provide that guarantee.

The architecture also requires a clear boundary between application
repositories, artifact registries and `nabhold/infrastructure`.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use an **immutable container artifact promotion model**.

The authoritative production artifact SHALL be identified by its **OCI
image digest**.

Application repositories SHALL:

1.  build container images;
2.  test them;
3.  generate required software-supply-chain metadata;
4.  scan them;
5.  publish approved images;
6.  expose immutable artifact identity for deployment.

`nabhold/infrastructure` SHALL:

1.  provision registry infrastructure where it owns that infrastructure;
2.  define registry access and retention controls;
3.  deploy approved image digests;
4.  verify deployment artifact identity;
5.  NOT rebuild application source code.

------------------------------------------------------------------------

## 3. Registry Strategy

Baobab SHALL support a two-role registry model:

  -----------------------------------------------------------------------
  Registry                            Primary Role
  ----------------------------------- -----------------------------------
  GitHub Container Registry (GHCR)    Repository-aligned
                                      build/distribution and development
                                      artifact publication

  Amazon ECR                          AWS production deployment registry
  -----------------------------------------------------------------------

For AWS-hosted Production, **Amazon ECR SHALL be the preferred runtime
registry** for ECS/Fargate workloads.

GHCR MAY remain the upstream artifact source where application
repositories already publish there.

Production promotion MAY copy an already-built OCI artifact from GHCR
into ECR, but SHALL NOT rebuild it.

------------------------------------------------------------------------

## 4. Artifact Flow

``` text
Application Repository
        │
        ▼
     CI Build
        │
        ▼
     Test Image
        │
        ├── SBOM
        ├── provenance
        ├── vulnerability scan
        └── signature/attestation
        │
        ▼
   Publish Artifact
        │
        ▼
       GHCR
        │
        │ promote same artifact
        ▼
       ECR
        │
        ▼
   Immutable Digest
        │
        ▼
Environment Release Manifest
        │
        ▼
nabhold/infrastructure
        │
        ▼
   ECS Task Definition
        │
        ▼
      Fargate
```

The bytes promoted to Production SHALL correspond to the artifact that
passed the required gates.

------------------------------------------------------------------------

## 5. Build Once, Promote

Baobab SHALL follow:

> **Build once, promote the same artifact.**

Rejected:

``` text
Source
  │
  ├── build DEV image
  ├── build STAGING image
  └── build PROD image
```

Required:

``` text
Source Commit
     │
     ▼
Build Once
     │
     ▼
Immutable Artifact
     │
     ├── Development
     ├── Staging
     └── Production
```

Environment-specific configuration SHALL be supplied at
deployment/runtime rather than compiled into separate environment images
unless a workload has an explicitly accepted requirement.

------------------------------------------------------------------------

## 6. Digest-Pinned Production

Production ECS task definitions MUST reference an immutable artifact
identity.

Preferred form:

``` text
<registry>/<repository>@sha256:<digest>
```

Human-readable tags MAY accompany an image, but SHALL NOT be the sole
production identity.

The following are prohibited as Production deployment selectors:

``` text
:latest
:main
:master
:production
:stable
```

unless they are resolved to and recorded as a specific immutable digest
before deployment.

------------------------------------------------------------------------

## 7. Tagging Strategy

Tags SHALL aid humans and automation without replacing digest identity.

Recommended tags MAY include:

``` text
v1.4.2
sha-3a18c7f
pr-248
rc-1.4.2
```

A release may therefore have:

``` text
zuribeans:v1.4.2
zuribeans:sha-3a18c7f
zuribeans@sha256:abc...
```

The digest is authoritative.

------------------------------------------------------------------------

## 8. Repository Naming

Container repositories SHALL use stable names aligned with workload
identity.

Examples:

``` text
baobab-cp
baobab-iam
baobab-trade
baobab-erp
baobab-cms
baobab-pulse
zuribeans
thamani
```

Registry naming SHALL NOT encode transient deployment information into
repository names.

Environment SHALL normally be represented through deployment metadata
rather than separate source builds.

------------------------------------------------------------------------

## 9. Registry Ownership Boundary

Application repositories own their application artifact lifecycle.

`nabhold/infrastructure` owns production registry infrastructure and
deployment integration.

``` text
Application Repo
      │
      │ owns
      ▼
Build + Test + Artifact Metadata
      │
      ▼
Published OCI Artifact
      │
      │ consumed by
      ▼
nabhold/infrastructure
      │
      ▼
Environment Deployment
```

Infrastructure SHALL NOT contain duplicate Docker build logic for
application repositories.

------------------------------------------------------------------------

## 10. ECR Architecture

ECR repositories SHALL be provisioned declaratively through Terraform
where owned by Baobab infrastructure.

Registry configuration SHOULD include:

-   encryption;
-   tag immutability where compatible with workflow;
-   lifecycle policy;
-   vulnerability scanning;
-   access logging/auditing through AWS controls;
-   least-privilege IAM;
-   cross-account access where required.

``` text
Production AWS Account
        │
        ▼
       ECR
        │
  ┌─────┼─────┐
  ▼     ▼     ▼
 CP   Trade  ZuriBeans
```

A single repository SHALL not mix unrelated workload images.

------------------------------------------------------------------------

## 11. Tag Immutability

Published release tags SHALL NOT be silently repointed to different
image content.

Example:

``` text
v1.4.2 ──► digest A
```

must not later become:

``` text
v1.4.2 ──► digest B
```

If artifact content changes, it requires a new artifact identity and
normally a new release version.

------------------------------------------------------------------------

## 12. Image Promotion

Promotion SHALL transfer artifact identity rather than recreate
application output.

``` text
GHCR Digest A
      │
      ▼
Promotion Verification
      │
      ▼
ECR Digest A-equivalent OCI content
      │
      ▼
Production Approval
```

Promotion tooling SHALL verify the resulting digest/content identity as
appropriate to the registry transfer mechanism.

A promotion failure SHALL not fall back to rebuilding from source.

------------------------------------------------------------------------

## 13. Environment Release Manifest

Deployment SHALL use an explicit environment release manifest or
equivalent controlled declaration.

Conceptually:

``` yaml
environment: production
release: 2026-09-15.1

artifacts:
  baobab-cp:
    image: <registry>/baobab-cp
    digest: sha256:...
  baobab-trade:
    image: <registry>/baobab-trade
    digest: sha256:...
  zuribeans:
    image: <registry>/zuribeans
    digest: sha256:...
```

The release manifest SHALL identify exactly what is intended to run.

Detailed release-manifest governance is defined by ADR-Infra-0021.

------------------------------------------------------------------------

## 14. Traceability

Every production artifact SHALL be traceable to its source.

The desired chain is:

``` text
Production Task
      │
      ▼
Image Digest
      │
      ▼
Release Metadata
      │
      ▼
Source Commit
      │
      ▼
CI Build
      │
      ▼
Tests / Scan / Attestations
```

Operators SHOULD be able to answer:

> What source produced the container currently running in Production?

without relying on memory or mutable tags.

------------------------------------------------------------------------

## 15. Software Bill of Materials

Production-bound images SHALL generate an SBOM in an accepted
machine-readable format.

The SBOM SHOULD identify material software components and dependencies.

``` text
Container Artifact
      │
      ├── Image
      ├── SBOM
      └── Provenance
```

SBOM generation SHALL occur in the application build pipeline, not by
reverse-engineering Production containers after deployment.

------------------------------------------------------------------------

## 16. Provenance

Build pipelines SHOULD produce verifiable provenance or equivalent
attestations describing:

-   source repository;
-   source revision;
-   build workflow;
-   artifact digest;
-   relevant build identity.

Provenance SHALL support supply-chain verification and incident
investigation.

------------------------------------------------------------------------

## 17. Signing

Production-bound artifacts SHOULD be cryptographically signed using an
approved OCI-compatible signing mechanism.

The preferred architecture SHOULD avoid long-lived private signing keys
where workload identity or keyless signing can provide adequate
assurance.

``` text
CI Identity
    │
    ▼
Artifact Signing
    │
    ▼
Digest + Signature
    │
    ▼
Verification Gate
    │
    ▼
Deployment
```

Signature verification SHOULD become a deployment gate as the
implementation matures.

------------------------------------------------------------------------

## 18. Vulnerability Scanning

Images SHALL be scanned for known vulnerabilities before Production
promotion.

Scanning SHOULD occur:

-   during CI;
-   at registry publication where supported;
-   periodically for retained Production artifacts.

A previously approved image MAY become vulnerable after publication
because vulnerability intelligence changes.

Production policy SHALL therefore consider both build-time and ongoing
findings.

------------------------------------------------------------------------

## 19. Vulnerability Gate

Production promotion SHALL define severity-based policy.

Critical or otherwise policy-blocking findings SHALL prevent promotion
unless an explicit, documented exception is approved.

Exceptions SHOULD record:

-   vulnerability;
-   affected artifact;
-   rationale;
-   compensating control;
-   owner;
-   expiry/review date.

Security exceptions SHALL not silently become permanent.

------------------------------------------------------------------------

## 20. Base Images

Application repositories SHALL use approved, maintained base images.

Base images SHOULD:

-   be minimal for the workload;
-   be pinned deliberately;
-   receive automated update visibility;
-   avoid unnecessary tools and packages;
-   use supported runtime versions.

Production images SHALL not include development tooling merely for
operational convenience.

------------------------------------------------------------------------

## 21. Multi-Architecture Images

Images MAY support multiple CPU architectures where there is a
demonstrated deployment requirement.

The artifact pipeline MUST ensure that the architecture selected by ECS
is tested and supported.

Multi-architecture publication SHALL not be introduced merely as a
packaging exercise.

------------------------------------------------------------------------

## 22. Registry Authentication

ECS task execution identities SHALL receive only the registry
permissions required to pull approved images.

Application task roles SHALL NOT receive registry administration
permissions.

``` text
ECS Execution Role
      │
      └── Pull image

Application Task Role
      │
      X
 Registry administration
```

Human push/delete permissions SHALL be restricted.

------------------------------------------------------------------------

## 23. Cross-Account Access

Where ECR resides in a different AWS account from the consuming ECS
workload, access SHALL use explicit cross-account IAM/repository
policies.

Production SHALL NOT depend on shared static registry credentials.

Cross-account policies SHALL preserve environment isolation.

------------------------------------------------------------------------

## 24. Registry Network Access

Where practical, ECS workloads SHOULD retrieve ECR artifacts through
private AWS networking using appropriate VPC endpoints.

Registry access architecture SHALL align with ADR-Infra-0005's
controlled-egress principles.

Public Internet access SHALL not be required merely to pull internally
managed Production images where private AWS paths are practical.

------------------------------------------------------------------------

## 25. Retention

Registries SHALL implement lifecycle policies.

Retention SHALL preserve:

-   currently deployed digests;
-   rollback candidates;
-   required audit artifacts;
-   active supported releases.

Registries MAY expire:

-   abandoned PR images;
-   superseded development artifacts;
-   unreferenced transient builds;
-   stale intermediate artifacts.

``` text
Artifact
   │
   ├── deployed? ───────► retain
   ├── rollback needed? ► retain
   ├── audit required? ─► retain
   └── transient/stale? ► lifecycle candidate
```

Retention MUST NOT delete an artifact required for rollback.

------------------------------------------------------------------------

## 26. Deletion Protection

Production artifact deletion SHALL be tightly controlled.

An image currently referenced by an active Production release MUST NOT
be deleted.

Deletion workflows SHOULD verify references before removal.

Manual registry cleanup SHALL not bypass retention and audit
requirements.

------------------------------------------------------------------------

## 27. Rollback

Rollback SHALL redeploy a previously approved immutable digest.

``` text
Release N
 digest B
    │
 failure
    ▼
Rollback
    │
    ▼
Release N-1
 digest A
```

Rollback SHALL NOT rebuild the old source revision and assume it
produces identical bytes.

------------------------------------------------------------------------

## 28. Configuration Separation

Container images SHALL contain application binaries/runtime assets, not
environment secrets.

Environment-specific values SHALL be injected through approved runtime
configuration.

``` text
Immutable Image
      +
Environment Configuration
      +
Secrets
      │
      ▼
Running Task
```

This separation is necessary for Build Once, Promote.

------------------------------------------------------------------------

## 29. Database Migrations

A container artifact MAY include migration tooling, but image promotion
SHALL not imply that a database migration is automatically safe.

Migration execution SHALL follow the release and rollback architecture.

Irreversible schema changes require explicit compatibility planning.

Artifact immutability does not make data changes reversible.

------------------------------------------------------------------------

## 30. Third-Party Images

Third-party container images SHALL be pinned to approved immutable
versions/digests for Production where practical.

Examples may include infrastructure or engine images.

Third-party images SHALL undergo appropriate:

-   provenance review;
-   vulnerability scanning;
-   licensing review;
-   version governance.

Using an official image does not eliminate supply-chain risk.

------------------------------------------------------------------------

## 31. Image Mirroring

Critical third-party images MAY be mirrored into a Baobab-controlled
registry where justified by:

-   availability;
-   provenance control;
-   scanning;
-   retention;
-   external registry rate limits;
-   supply-chain policy.

Mirroring SHALL preserve original provenance metadata where practical.

------------------------------------------------------------------------

## 32. Secrets Prohibition

Container registries and images SHALL NOT be used to distribute secrets.

Build pipelines SHALL prevent accidental inclusion of:

-   `.env` files;
-   private keys;
-   cloud credentials;
-   database credentials;
-   tokens;
-   production configuration containing secrets.

Secret scanning SHOULD be included in application CI.

------------------------------------------------------------------------

## 33. Build Environment Security

Production artifact builds SHALL execute in controlled CI environments.

Build pipelines SHOULD minimise:

-   privileged container execution;
-   unnecessary write tokens;
-   untrusted script execution with registry credentials;
-   secret exposure to pull-request workflows.

Untrusted PRs SHALL NOT receive credentials capable of publishing
Production artifacts.

------------------------------------------------------------------------

## 34. Pull Request Artifacts

PR images MAY be produced for testing.

They SHALL:

-   be clearly identified as non-release artifacts;
-   have bounded retention;
-   not automatically become Production releases;
-   not receive Production signing/promotion status without normal
    release gates.

------------------------------------------------------------------------

## 35. Release Promotion Flow

``` text
Developer Change
      │
      ▼
Pull Request
      │
      ▼
Tests + Security Checks
      │
      ▼
Merge
      │
      ▼
Build Release Artifact
      │
      ├── SBOM
      ├── provenance
      ├── scan
      └── signature
      │
      ▼
Publish Immutable Artifact
      │
      ▼
Development
      │
      ▼
Staging
      │
      ▼
Production Approval
      │
      ▼
Promote Same Artifact
      │
      ▼
Deploy Digest
      │
      ▼
Verify Runtime Digest
```

------------------------------------------------------------------------

## 36. Runtime Verification

Post-deployment verification SHOULD confirm that ECS is executing the
intended image digest.

The desired state and observed runtime artifact SHALL agree.

``` text
Release Manifest Digest
          │
          ▼
       compare
          │
          ▼
Running ECS Digest
```

A mismatch is a deployment defect.

------------------------------------------------------------------------

## 37. Drift

Manual task-definition changes that alter image references outside the
approved deployment workflow SHALL be considered deployment drift.

Persistent drift MUST be reconciled through the authoritative
infrastructure/release configuration.

Production operators SHALL NOT repair releases by casually changing
image tags in the AWS Console.

------------------------------------------------------------------------

## 38. ZuriBeans Go-Live

ZuriBeans SHALL be the first digital estate to validate the complete
artifact chain.

``` text
nabhold/zuribeans
       │
       ▼
Build + Test
       │
       ▼
Immutable ZuriBeans Image
       │
       ▼
SBOM + Scan + Provenance
       │
       ▼
Registry
       │
       ▼
Staging Validation
       │
       ▼
Production Promotion
       │
       ▼
ECS/Fargate by Digest
```

ZuriBeans-specific CI SHALL not redefine platform-wide registry security
policy.

------------------------------------------------------------------------

## 39. Shared Platform Workloads

The same artifact rules SHALL apply to Baobab platform repositories.

No distinction shall exist whereby digital estates are immutable but
platform engines deploy mutable `latest` tags.

``` text
baobab-cp     ─┐
baobab-trade  ─┤
baobab-iam    ─┼──► Same Artifact Governance
zuribeans     ─┤
thamani       ─┘
```

------------------------------------------------------------------------

## 40. Failure Handling

If artifact verification fails:

``` text
Artifact Candidate
       │
       ▼
Verification
   │         │
 Pass      Fail
   │         │
   ▼         ▼
Promote    Quarantine/
           Reject
```

Production deployment SHALL fail closed rather than substitute another
tag or rebuild implicitly.

------------------------------------------------------------------------

## 41. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Mutable `latest`        Rejected                Non-deterministic
  production deployments                          

  Rebuild per environment Rejected                Breaks artifact
                                                  identity

  Infrastructure repo     Rejected                Violates repository
  builds all applications                         ownership boundary

  GHCR only by            Rejected                ECR better aligns with
  architectural necessity                         AWS runtime; GHCR
                                                  remains supported
                                                  upstream

  ECR only for all        Rejected                Unnecessary coupling of
  development workflows                           repository CI to AWS

  Tag-only Production     Rejected                Tags may be mutable
  identity                                        

  Shared registry         Rejected                Weak identity and
  credentials                                     auditability

  Secrets embedded in     Rejected                Supply-chain and
  images                                          disclosure risk

  Production deployment   Rejected                Bypasses release
  from PR images                                  governance

  Rebuilding old code for Rejected                Does not guarantee
  rollback                                        identical artifact

  Indefinite retention of Rejected                Cost and operational
  every transient image                           clutter

  Automatic deletion of   Rejected                May destroy rollback
  old release images                              capability
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 42. Consequences

### Positive

-   Deterministic Production releases.
-   Strong source-to-runtime traceability.
-   Reliable rollback to known artifacts.
-   Clear application/infrastructure ownership boundary.
-   Reduced supply-chain ambiguity.
-   AWS-native ECR integration with ECS.
-   Supports GHCR-based repository workflows.
-   Enables vulnerability, SBOM and provenance governance.
-   Consistent artifact policy across all Baobab workloads.

### Costs

-   Promotion tooling is required.
-   Two registries may exist in the artifact path.
-   Signing and provenance add CI complexity.
-   Retention must be managed deliberately.
-   Vulnerability policy requires operational ownership.
-   Cross-account ECR policies may be required.

These costs are accepted.

------------------------------------------------------------------------

## 43. Decision Rules

The following rules are authoritative:

> **Baobab Production deployments SHALL use immutable container
> artifacts.**

> **The OCI image digest SHALL be the authoritative Production artifact
> identity.**

> **Baobab SHALL build an application artifact once and promote that
> same artifact through environments.**

> **Amazon ECR SHALL be the preferred AWS Production runtime registry;
> GHCR MAY remain the repository-aligned upstream registry.**

> **Promotion SHALL NOT rebuild application source.**

> **`nabhold/infrastructure` SHALL deploy application artifacts but
> SHALL NOT own their source build logic.**

> **Production releases SHALL be traceable from running digest to source
> revision and CI evidence.**

> **Production-bound artifacts SHALL undergo vulnerability scanning and
> SHOULD carry SBOM, provenance and cryptographic verification
> metadata.**

> **Secrets SHALL NOT be embedded in container images.**

> **Rollback SHALL use a previously approved immutable artifact rather
> than rebuilding old source.**

> **An artifact required by an active deployment or supported rollback
> SHALL NOT be deleted.**

> **The same artifact governance SHALL apply to digital estates and
> Baobab platform services.**

------------------------------------------------------------------------

## 44. Implementation Implications

Implementation SHALL establish infrastructure support for:

``` text
terraform/modules/
└── registry/
    ├── ECR repositories
    ├── encryption
    ├── lifecycle policies
    ├── immutability controls
    ├── scanning configuration
    ├── IAM policies
    └── cross-account access where required
```

Application repositories SHALL progressively implement:

``` text
Build
├── tests
├── image
├── SBOM
├── provenance
├── vulnerability scan
├── signing/attestation
└── immutable publication
```

Deployment automation SHALL consume:

``` text
image repository
+
immutable digest
+
release metadata
```

rather than mutable tags.

------------------------------------------------------------------------

## 45. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0008 --- DNS, TLS, Edge and API Gateway Architecture**

It shall define:

-   public and private DNS;
-   Route 53 ownership;
-   certificate management;
-   ACM;
-   TLS termination;
-   edge load balancing;
-   WAF;
-   APISIX placement;
-   public versus administrative gateway planes;
-   domain and subdomain conventions;
-   digital-estate routing;
-   internal service routing;
-   health checks;
-   origin protection;
-   and the request path from the Internet to Baobab workloads.
