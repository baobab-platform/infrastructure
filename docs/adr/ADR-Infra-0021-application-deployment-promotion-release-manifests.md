# ADR-Infra-0021 --- Application Deployment, Promotion and Release Manifests

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0001 --- Environment Provisioner Boundary
    -   ADR-Infra-0003 --- Terraform Architecture and Module Strategy
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0007 --- Container Registry and Immutable Artifact
        Strategy
    -   ADR-Infra-0013 --- Infrastructure IAM and Workload Identity
    -   ADR-Infra-0014 --- Secrets, Keys and Certificate Management
    -   ADR-Infra-0015 --- Tenant and Workload Infrastructure Isolation
    -   ADR-Infra-0016 --- Observability and Telemetry Architecture
    -   ADR-Infra-0017 --- SLOs, Health, Capacity and Operational
        Monitoring
    -   ADR-Infra-0018 --- Backup, Restore and Data Retention
    -   ADR-Infra-0020 --- CI/CD and Infrastructure Change Governance
-   **Platform Dependencies:** accepted application/engine ADRs and
    canonical contracts in `nabhold/shared`
-   **Follow-on:** ADR-Infra-0022 --- Deployment Rollback and Database
    Change Safety

------------------------------------------------------------------------

## 1. Context

Baobab is a polyrepo/polyglot platform.

Application source and runtime artifacts are owned by repositories such
as:

-   `nabhold/baobab-cp`;
-   `nabhold/baobab-iam`;
-   `nabhold/baobab-trade`;
-   `nabhold/baobab-erp`;
-   `nabhold/baobab-cms`;
-   `nabhold/baobab-pulse`;
-   `nabhold/zuribeans`;
-   future digital estates and engines.

`nabhold/infrastructure` owns Production environment provisioning and
deployment automation, but SHALL NOT become a monorepo containing
application source or rebuilding every application.

A reliable Production release requires a precise contract between:

``` text
Application Repository
        │
        ▼
Immutable Artifact
        │
        ▼
Release Declaration
        │
        ▼
Infrastructure Deployment
        │
        ▼
Runtime Verification
```

Without this contract, deployments become dependent on mutable tags,
branch state, manually copied environment variables and undocumented
cross-repository assumptions.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use **immutable artifact promotion plus version-controlled
release manifests** as the Production application deployment contract.

Application repositories SHALL:

-   build;
-   test;
-   scan;
-   identify;
-   publish;
-   and provide provenance for deployable artifacts.

`nabhold/infrastructure` SHALL:

-   consume approved artifact identities;
-   resolve environment configuration references;
-   render/update runtime deployment definitions;
-   deploy without rebuilding source;
-   verify the resulting runtime.

Production container identity SHALL be the OCI image digest.

------------------------------------------------------------------------

## 3. Core Deployment Flow

``` text
Application Repository
        │
        ▼
 Build / Test / Scan
        │
        ▼
Immutable OCI Artifact
        │
        ▼
GHCR / ECR
        │
        ▼
Release Manifest PR
        │
        ▼
Review / Merge
        │
        ▼
Protected Deployment
        │
        ▼
ECS Task Definition
        │
        ▼
Runtime Verification
```

------------------------------------------------------------------------

## 4. Repository Responsibility Boundary

  -----------------------------------------------------------------------
  Concern                      Application Repo       Infrastructure Repo
  ------------------- ------------------------- -------------------------
  Source code                              Owns                        No

  Unit/domain tests                        Owns                        No

  Container build                          Owns                        No

  SBOM/provenance                          Owns         Verifies/consumes

  OCI artifact                             Owns                  Consumes
  publication                                   

  Production                                 No                      Owns
  VPC/ECS/RDS/etc.                              

  Runtime                   Inputs/requirements Owns deployment rendering
  task/service                                  
  definition                                    

  Environment secret                         No  References/control plane
  values                                        

  Application schema                       Owns    Coordinates deployment
  migration                                                      boundary

  Release manifest            Supplies artifact  Owns environment release
                                       metadata               declaration

  Production                 No direct mutation   Owns governed execution
  deployment                                    

  Post-deploy service              Participates              Orchestrates
  verification                                  
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 5. Immutable Artifact Identity

Production container deployment SHALL reference:

``` text
registry/repository@sha256:<digest>
```

and SHALL NOT rely solely on:

``` text
:latest
:main
:production
:stable
```

Tags MAY remain human-friendly aliases, but digest is authoritative.

------------------------------------------------------------------------

## 6. Build Once, Promote

The same tested artifact SHALL be promoted between environments.

``` text
Build Once
   │
   ├── Development
   │
   ├── Staging
   │
   └── Production
```

Production SHALL NOT rebuild source merely to create a "Production
image."

A rebuild produces a different artifact and therefore requires a new
verification chain.

------------------------------------------------------------------------

## 7. Artifact Metadata

Every Production-bound artifact SHOULD be traceable to:

-   source repository;
-   source commit SHA;
-   build workflow/run;
-   image digest;
-   build timestamp;
-   service version;
-   SBOM;
-   vulnerability/security result;
-   provenance/signature where implemented.

The platform SHOULD be able to answer:

> Which exact source revision produced the running container?

------------------------------------------------------------------------

## 8. Registry Strategy

ADR-Infra-0007 remains authoritative:

-   GHCR is suitable for repository-aligned build/development
    distribution;
-   Amazon ECR is preferred for AWS runtime consumption;
-   promotion between registries SHALL preserve the artifact digest
    where technically supported;
-   the image SHALL not be rebuilt during promotion.

------------------------------------------------------------------------

## 9. Release Manifest

A release manifest SHALL be a version-controlled declaration of the
artifact/configuration intended for a specific environment.

Conceptual example:

``` yaml
apiVersion: infrastructure.baobab/v1
kind: Release
metadata:
  environment: production
  service: baobab-trade
spec:
  image:
    repository: <approved-ecr-repository>
    digest: sha256:...
  source:
    repository: nabhold/baobab-trade
    revision: <git-sha>
  configuration:
    version: <config-version>
  migrations:
    strategy: <approved-strategy>
```

This schema is illustrative. The canonical schema SHALL be
defined/versioned before implementation and SHOULD live in
`nabhold/shared` if cross-repository.

------------------------------------------------------------------------

## 10. Manifest Contains References, Not Secrets

Release manifests SHALL NOT contain plaintext:

-   database passwords;
-   API keys;
-   OAuth secrets;
-   broker passwords;
-   private keys;
-   certificates' private material.

They MAY contain approved references to secret/configuration resources.

``` text
Release Manifest
      │
      ├── image digest
      ├── config reference
      └── secret reference
              │
              ▼
        Secrets Manager
```

------------------------------------------------------------------------

## 11. Environment-Specific Manifest

Development, Staging and Production SHALL have distinct release
declarations.

Production manifest changes SHALL use the governance of ADR-Infra-0020.

Environment-specific differences SHOULD be configuration and
infrastructure references---not separate source-code forks.

------------------------------------------------------------------------

## 12. Promotion

Promotion means changing an environment's approved release declaration
to reference an already verified artifact.

``` text
Staging
  digest A
     │
     │ promote
     ▼
Production
  digest A
```

Promotion SHALL preserve artifact identity.

------------------------------------------------------------------------

## 13. Promotion Evidence

Before Production promotion, the release SHOULD provide evidence of:

-   successful build;
-   required automated tests;
-   vulnerability/security acceptance;
-   Staging deployment where required;
-   Staging verification;
-   migration compatibility;
-   required approvals.

High-risk services MAY require stronger evidence.

------------------------------------------------------------------------

## 14. Artifact Verification

Before deployment, infrastructure SHOULD verify that the referenced
artifact:

-   exists;
-   matches the expected digest;
-   originates from an approved repository/build;
-   satisfies signing/provenance policy where enabled;
-   is not blocked by security policy.

A manifest pointing to a nonexistent or unapproved digest SHALL fail
before runtime deployment.

------------------------------------------------------------------------

## 15. Release Manifest Ownership

`nabhold/infrastructure` SHALL own environment release state.

Application repositories SHALL not directly mutate Production ECS
services.

Application CI MAY create or propose a release-manifest update PR, but
normal Production deployment remains governed by infrastructure review
and protected environments.

------------------------------------------------------------------------

## 16. Proposed Repository Structure

Conceptually:

``` text
deploy/
├── manifests/
│   ├── development/
│   ├── staging/
│   └── production/
├── policies/
├── scripts/
└── verification/
```

Exact structure MAY evolve, but environment release state SHALL remain
explicit and reviewable.

------------------------------------------------------------------------

## 17. One Manifest vs Composite Release

Baobab SHALL support both:

-   independent service releases;
-   coordinated multi-service releases where compatibility requires
    them.

The platform SHALL NOT require all repositories to release in lockstep.

------------------------------------------------------------------------

## 18. Independent Deployability

The normal case SHALL be independent deployment.

``` text
baobab-trade vX
baobab-iam   vY
baobab-cp    vZ
```

A new Trade release SHALL not require rebuilding IAM merely because both
participate in the same platform.

------------------------------------------------------------------------

## 19. Coordinated Release

A coordinated release MAY be required when a change spans:

-   canonical contract;
-   Control Plane;
-   engine capability;
-   database migration;
-   digital estate.

In that case, a composite release declaration SHOULD identify compatible
component versions/digests.

------------------------------------------------------------------------

## 20. Compatibility Before Coordination

Cross-repository changes SHOULD prefer backward/forward compatibility
over synchronized "big bang" deployment.

Preferred:

``` text
Producer v2
  compatible with
Consumer v1 + v2
```

rather than:

``` text
all services must change simultaneously
```

------------------------------------------------------------------------

## 21. Shared Contract Evolution

Canonical contracts in `nabhold/shared` SHALL evolve compatibly
according to their accepted governance.

Application artifacts SHALL declare/verify compatible contract versions
where required.

Infrastructure SHALL not duplicate canonical schemas into deployment
manifests.

------------------------------------------------------------------------

## 22. ECS Task Definition Rendering

Infrastructure SHALL render ECS task definitions from:

-   approved image digest;
-   resource configuration;
-   workload IAM role;
-   task execution role;
-   networking;
-   secret/config references;
-   health configuration;
-   telemetry configuration.

Task definitions SHALL be reproducible.

------------------------------------------------------------------------

## 23. ECS Revision Traceability

Every deployed ECS task-definition revision SHOULD be traceable to:

-   release manifest;
-   image digest;
-   source commit;
-   infrastructure revision.

Runtime inspection SHALL reveal the active artifact.

------------------------------------------------------------------------

## 24. Configuration

Application configuration SHALL be externalized.

Configuration MAY come from:

-   environment-safe manifest values;
-   SSM Parameter Store;
-   Secrets Manager;
-   platform/control-plane resolution;
-   engine-specific approved configuration.

Configuration SHALL not require rebuilding the container image.

------------------------------------------------------------------------

## 25. Configuration Versioning

Material non-secret configuration SHOULD be version-controlled or
otherwise version-identifiable.

Operators SHOULD be able to determine whether a regression resulted
from:

-   image change;
-   infrastructure change;
-   configuration change;
-   secret rotation;
-   database migration.

------------------------------------------------------------------------

## 26. Secret Rotation and Release

Secret rotation SHALL not normally require an application rebuild.

Whether it requires a task restart depends on the application's
secret-loading strategy.

Release automation SHALL account for this without copying secret values
into manifests.

------------------------------------------------------------------------

## 27. Database Migration Ownership

Application schema migrations belong to the owning service repository.

Infrastructure SHALL provide the safe execution environment but SHALL
NOT invent or own application migration semantics.

Examples:

``` text
baobab-trade → Trade schema migration
baobab-iam   → Keycloak/IAM schema lifecycle
baobab-erp   → iDempiere-supported DB lifecycle
```

------------------------------------------------------------------------

## 28. Migration Execution

Where application-controlled migrations are required, they SHOULD run as
a controlled deployment step or one-off ECS task rather than hidden
inside every application replica's startup.

Multiple replicas SHALL not race to perform an unsafe migration.

------------------------------------------------------------------------

## 29. Expand--Migrate--Contract

Backward-compatible database evolution SHOULD use:

``` text
Expand
  │
  ▼
Deploy Compatible Code
  │
  ▼
Migrate / Backfill
  │
  ▼
Verify
  │
  ▼
Contract Later
```

Destructive schema changes SHALL not be coupled casually to the first
deployment of new code.

------------------------------------------------------------------------

## 30. Migration Manifest Metadata

A release manifest MAY identify migration requirements, for example:

``` text
migration required?
migration artifact/version
pre-deploy or post-deploy
compatibility requirement
```

It SHALL not embed database credentials.

------------------------------------------------------------------------

## 31. Engine-Specific Upgrade Rules

Generic deployment automation SHALL respect engine-specific accepted
ADRs.

For example:

-   iDempiere upgrades SHALL follow supported ERP upgrade/migration
    procedures;
-   Keycloak upgrades SHALL follow accepted IAM compatibility rules;
-   Medusa upgrades SHALL follow Trade architecture;
-   Payload upgrades SHALL follow CMS architecture.

One generic "run migration command" abstraction SHALL not override
engine-specific safety.

------------------------------------------------------------------------

## 32. Deployment Strategies

ECS services SHOULD use rolling replacement as the baseline.

Blue/green or canary deployment MAY be used for high-risk services where
operational benefit justifies complexity.

The strategy SHALL be compatible with database and contract evolution.

------------------------------------------------------------------------

## 33. Rolling Deployment

A rolling deployment SHALL preserve healthy capacity according to
ADR-Infra-0017.

``` text
Old Tasks
   │
   ├── New Task starts
   ├── Readiness passes
   ├── Traffic shifts
   └── Old Task stops
```

A new task SHALL not receive normal traffic before readiness succeeds.

------------------------------------------------------------------------

## 34. Blue/Green

Blue/green MAY be selected where:

-   rapid traffic rollback is valuable;
-   both versions can coexist;
-   database compatibility permits;
-   cost is acceptable.

Blue/green does not solve irreversible database migration.

------------------------------------------------------------------------

## 35. Canary

Canary deployment MAY expose a small portion of traffic/work to the new
release.

Promotion SHALL be based on defined health signals:

-   error rate;
-   latency;
-   SLO impact;
-   synthetics;
-   domain verification.

Canary SHALL not be a substitute for tests.

------------------------------------------------------------------------

## 36. Workers

Asynchronous workers SHALL be independently deployable from synchronous
APIs where their lifecycle/scaling differs.

A service release MAY include multiple workload artifacts/entrypoints
where accepted architecture requires it.

Workers SHALL preserve event compatibility during rolling deployment.

------------------------------------------------------------------------

## 37. Scheduled/One-Off Tasks

Migrations, backfills and operational jobs MAY run as controlled ECS
tasks.

They SHALL use:

-   approved image digest;
-   dedicated command;
-   scoped task role;
-   explicit timeout;
-   logs/telemetry;
-   controlled concurrency.

Ad hoc Production shell sessions SHALL not be the normal job execution
model.

------------------------------------------------------------------------

## 38. Deployment Order

Where a coordinated release is unavoidable, deployment order SHALL be
explicit.

Example:

``` text
1. compatible contract
2. database expansion
3. backend producer/consumer
4. dependent service
5. digital estate
6. backfill
7. later contraction
```

The actual order SHALL derive from compatibility analysis.

------------------------------------------------------------------------

## 39. Control Plane Deployment

`baobab-cp` deployment SHALL not erase or bypass persisted desired
state.

Control Plane workers/reconcilers SHALL tolerate rolling deployment and
compatible event versions.

Changes to provisioning semantics SHALL be coordinated with shared
contracts and infrastructure interfaces.

------------------------------------------------------------------------

## 40. IAM Deployment

`baobab-iam` deployment SHALL preserve authentication continuity.

Keycloak/runtime upgrades SHALL account for:

-   database compatibility;
-   realm/client configuration;
-   signing keys;
-   sessions;
-   downstream token compatibility.

IAM release failure can block the entire platform and therefore requires
high deployment scrutiny.

------------------------------------------------------------------------

## 41. Trade Deployment

`baobab-trade` deployment SHALL preserve legal-entity isolation and
B2B/B2C domain independence.

A Trade release SHALL not accidentally apply ZuriBeans-specific
assumptions to Thamani or vice versa.

Tenant capability/configuration remains resolved through accepted
platform mechanisms.

------------------------------------------------------------------------

## 42. ERP Deployment

`baobab-erp` deployment SHALL follow iDempiere-supported lifecycle
procedures and accepted ERP ADRs.

Generic container promotion SHALL not bypass ERP database/application
upgrade requirements.

------------------------------------------------------------------------

## 43. CMS Deployment

`baobab-cms` deployment SHALL coordinate Payload application code,
schema/configuration and object-storage dependencies according to
accepted CMS ADRs.

CMS content SHALL remain external to the immutable application image.

------------------------------------------------------------------------

## 44. Pulse Deployment

`baobab-pulse` deployment SHALL keep model/index/vector/data
dependencies external where appropriate.

A Pulse release SHALL distinguish:

-   application artifact;
-   model/configuration;
-   Haystack pipeline configuration;
-   Qdrant/index state;
-   external data sources.

These SHALL not be conflated into one opaque container version.

------------------------------------------------------------------------

## 45. Digital Estate Deployment

A digital estate such as ZuriBeans SHALL have its own release artifact
and manifest.

Its deployment SHALL not require rebuilding Baobab backend engines.

``` text
ZuriBeans UI
     │
     ▼
Approved API/Gateway Contracts
     │
     ▼
Baobab Capabilities
```

Frontend and backend release lifecycles SHOULD remain independently
deployable where contracts permit.

------------------------------------------------------------------------

## 46. ZuriBeans Release Composition

The ZuriBeans go-live release SHOULD explicitly identify the compatible
set of required platform capabilities without pretending they form one
application binary.

Conceptually:

``` yaml
estate: zuribeans
release:
  frontend: <digest>
dependencies:
  iam: <compatible capability/version>
  trade: <compatible capability/version>
  erp: <compatible capability/version>
  controlPlane: <compatible capability/version>
```

Exact schema SHALL be defined through canonical release contracts.

------------------------------------------------------------------------

## 47. Dependency Pinning

Release declarations SHALL avoid ambiguous dependencies such as:

``` text
use current Trade
use latest IAM
use whatever is in Production
```

Where compatibility depends on a version/interface, that expectation
SHALL be explicit and testable.

------------------------------------------------------------------------

## 48. API Compatibility

Deployment SHALL preserve API compatibility according to accepted
service contracts.

Breaking API changes require coordinated versioning/migration.

Infrastructure SHALL not solve API incompatibility through deployment
ordering alone.

------------------------------------------------------------------------

## 49. Event Compatibility

Publishers and consumers SHALL preserve compatible canonical event
evolution.

During rolling deployment, old and new consumer versions may coexist.

A release SHALL account for this rather than assuming instantaneous
replacement.

------------------------------------------------------------------------

## 50. Feature Flags

Feature flags MAY decouple code deployment from capability activation.

Flags SHALL:

-   have an owner;
-   have safe defaults;
-   be auditable where material;
-   not contain secrets;
-   have cleanup/lifecycle.

Feature flags SHALL not become a permanent substitute for coherent
versioning.

------------------------------------------------------------------------

## 51. Release Verification

After deployment, verification SHALL include relevant:

-   ECS health;
-   task digest;
-   service version;
-   logs/traces;
-   synthetic checks;
-   dependency health;
-   migration status;
-   error/latency behaviour.

A release SHALL not be marked successful solely because task replacement
completed.

------------------------------------------------------------------------

## 52. Release Evidence

For each Production deployment, evidence SHOULD identify:

``` text
Release Manifest
      │
      ├── source revision
      ├── artifact digest
      ├── infrastructure revision
      ├── approvals
      ├── migration result
      └── verification result
```

This evidence SHALL support incident investigation and rollback.

------------------------------------------------------------------------

## 53. Deployment Observability

ADR-Infra-0016 applies.

Release markers SHOULD be visible in operational telemetry.

Operators SHOULD be able to correlate a release with changes in:

-   error rate;
-   latency;
-   saturation;
-   queue backlog;
-   customer-journey SLOs.

------------------------------------------------------------------------

## 54. Failed Deployment

If deployment verification fails:

1.  stop further promotion;
2.  preserve evidence;
3.  determine whether rollback is safe;
4.  account for migrations/external side effects;
5.  execute the approved recovery path.

Blindly redeploying repeatedly is prohibited.

------------------------------------------------------------------------

## 55. Rollback Artifact

The previous approved release manifest/digest SHALL remain identifiable.

Rollback SHOULD normally redeploy the prior known artifact, not rebuild
old source.

Detailed rollback rules are governed by ADR-Infra-0022.

------------------------------------------------------------------------

## 56. Multi-Repository Release Coordination

A cross-repository release SHALL have one explicit coordination record
when atomic operational sequencing is required.

It SHOULD state:

-   participating repositories;
-   artifact digests;
-   compatibility constraints;
-   deployment order;
-   migration steps;
-   verification;
-   rollback boundaries.

This record SHALL not require moving source into one repository.

------------------------------------------------------------------------

## 57. Release Manifest Schema Governance

If the release manifest becomes a cross-repository contract, its schema
SHALL be versioned in `nabhold/shared`.

Infrastructure SHALL consume released schema versions.

Local undocumented YAML structures SHALL not become accidental platform
APIs.

------------------------------------------------------------------------

## 58. Manifest Validation

CI SHALL validate release manifests for:

-   schema;
-   environment;
-   approved repository;
-   valid digest syntax;
-   required metadata;
-   prohibited mutable tags;
-   secret leakage;
-   dependency consistency where machine-checkable.

Invalid manifests SHALL fail before deployment.

------------------------------------------------------------------------

## 59. Manifest Immutability and History

Git history SHALL preserve the sequence of approved environment
releases.

A Production release SHALL be reproducible from:

-   manifest revision;
-   artifact digest;
-   infrastructure revision;
-   external configuration references.

The platform SHALL not rely on an operator remembering what was
deployed.

------------------------------------------------------------------------

## 60. Production Access Boundary

Application repository workflows SHALL NOT need broad Production AWS
permissions merely to publish a release.

Preferred separation:

``` text
Application CI
   │
   ├── publish artifact
   └── propose release

Infrastructure CI
   │
   └── deploy Production
```

This reduces cross-repository blast radius.

------------------------------------------------------------------------

## 61. ZuriBeans Go-Live Gate

Before ZuriBeans Production go-live, the release system SHALL prove:

-   frontend artifact is immutable;
-   required backend artifacts are immutable;
-   manifests contain digests, not `latest`;
-   artifacts are traceable to source;
-   Production infrastructure does not rebuild source;
-   configuration/secrets are external;
-   migrations are controlled;
-   cross-repo compatibility is documented;
-   deployment verification passes;
-   previous release remains identifiable;
-   release evidence is retained.

------------------------------------------------------------------------

## 62. Production Verification

Before declaring this architecture implemented, verify:

-   application repos build their own artifacts;
-   infrastructure consumes rather than rebuilds them;
-   Production uses image digests;
-   release manifests are version-controlled;
-   manifest schema is validated;
-   secrets are references only;
-   environment releases are distinct;
-   promotion preserves artifact identity;
-   ECR/runtime artifact exists before deploy;
-   source commit and digest are traceable;
-   ECS task revisions map to manifests;
-   schema migrations are application-owned and controlled;
-   workers/jobs use approved immutable artifacts;
-   post-deployment verification exists;
-   coordinated releases declare order/compatibility;
-   previous release is recoverable for rollback;
-   ZuriBeans release composition is explicit.

------------------------------------------------------------------------

## 63. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Production deploy from  Rejected                Mutable/untraceable
  `latest`                                        

  Rebuild source for each Rejected                Artifact differs
  environment                                     between stages

  Infrastructure repo     Rejected                Violates polyrepo
  builds all apps                                 ownership

  Application repo        Rejected                Excessive cross-repo
  directly mutates                                privilege
  Production ECS                                  

  Plaintext secrets in    Rejected                Security exposure
  release manifest                                

  Git branch name as      Rejected                Mutable
  release identity                                

  One lockstep platform   Rejected                Destroys independent
  release always                                  deployability

  Hidden migration in     Rejected                Race/safety risk
  every replica startup                           

  Big-bang cross-repo     Rejected                Fragile
  breaking change                                 

  Generic migration       Rejected                Engine incompatibility
  strategy overriding                             
  engine rules                                    

  Deployment complete     Rejected                No service verification
  when tasks start                                

  Rebuild old source for  Rejected                Not same artifact
  rollback                                        

  Undocumented manifest   Rejected                Accidental API
  schema                                          

  Configuration baked     Rejected                Prevents safe promotion
  into image                                      
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 64. Consequences

### Positive

-   Exact Production artifacts are reproducible and traceable.
-   Application and infrastructure repository responsibilities remain
    clean.
-   Build-once/promote prevents environment-specific binary drift.
-   Production deployment no longer depends on mutable tags.
-   Polyrepo services remain independently deployable.
-   Cross-repository releases can still be coordinated explicitly.
-   Database migration ownership remains with the correct service.
-   ZuriBeans receives a concrete, auditable release composition.
-   Rollback can reference previously approved immutable artifacts.

### Costs

-   Release manifest tooling/schema must be built.
-   Artifact promotion/verification adds pipeline steps.
-   Cross-repository compatibility requires discipline.
-   Engine-specific upgrade procedures cannot be hidden behind one
    generic deploy command.
-   Release evidence and manifests require lifecycle management.

These costs are accepted.

------------------------------------------------------------------------

## 65. Decision Rules

> **Application repositories SHALL build, test and publish their own
> deployable artifacts.**

> **`nabhold/infrastructure` SHALL deploy approved artifacts without
> rebuilding application source.**

> **Production container identity SHALL be the OCI digest.**

> **The same verified artifact SHOULD be promoted across environments
> rather than rebuilt.**

> **Environment release state SHALL be expressed through
> version-controlled release manifests.**

> **Release manifests SHALL contain secret/configuration references, not
> plaintext secrets.**

> **Application repositories SHALL NOT require broad Production AWS
> mutation privileges merely to release software.**

> **Production release manifests SHALL be governed through the
> infrastructure change process.**

> **Application schema migrations SHALL remain owned by the relevant
> service/engine and SHOULD follow expand--migrate--contract where
> applicable.**

> **Independent deployment SHALL be the default; coordinated
> multi-repository releases SHALL be explicit exceptions driven by
> compatibility.**

> **Release verification SHALL include runtime/service health, not
> merely successful ECS task replacement.**

> **The previous approved artifact/release SHALL remain identifiable for
> rollback.**

> **ZuriBeans SHALL validate the complete artifact → manifest →
> deployment → verification chain before go-live.**

------------------------------------------------------------------------

## 66. Implementation Implications

The infrastructure repository SHALL evolve toward:

``` text
deploy/
├── manifests/
│   ├── development/
│   ├── staging/
│   └── production/
├── schemas-or-contract-reference/
├── policies/
├── scripts/
└── verification/
```

The cross-repository lifecycle becomes:

``` text
App Repo
   │
   ├── test
   ├── build
   ├── scan
   ├── SBOM/provenance
   └── publish digest
            │
            ▼
Infrastructure Release PR
            │
            ├── validate manifest
            ├── verify artifact
            └── review
                    │
                    ▼
                  Merge
                    │
                    ▼
          Protected Deployment
                    │
                    ▼
                ECS Runtime
                    │
                    ▼
               Verification
```

Implementation SHALL inspect each consuming repository's accepted ADRs
before defining its build, migration, upgrade or release behaviour.

------------------------------------------------------------------------

## 67. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0022 --- Deployment Rollback and Database Change Safety**

It shall define:

-   rollback classes;
-   application rollback;
-   ECS rollback;
-   blue/green rollback;
-   migration compatibility;
-   expand--migrate--contract enforcement;
-   irreversible changes;
-   data backfills;
-   external side effects;
-   failed deployment recovery;
-   rollback decision gates;
-   restore vs rollback;
-   forward-fix criteria;
-   and Production safeguards preventing a code rollback from corrupting
    newer database state.
