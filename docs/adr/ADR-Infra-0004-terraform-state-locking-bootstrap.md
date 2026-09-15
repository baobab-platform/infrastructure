# ADR-Infra-0004 --- Terraform State, Locking and Bootstrap

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0001 --- Environment Provisioner Boundary
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0003 --- Terraform Architecture and Module Strategy
-   **Follow-on:** ADR-Infra-0005 --- Network and Trust-Zone
    Architecture

------------------------------------------------------------------------

## 1. Context

Terraform state is security-sensitive operational data. It may contain
resource identifiers, topology, generated values and, depending on
providers and resources, sensitive values.

Baobab requires independently controlled Development, Staging and
Production environments. State therefore MUST provide:

-   environment isolation;
-   encryption;
-   concurrency protection;
-   restricted access;
-   recovery and version history;
-   auditable CI/CD access;
-   safe bootstrap;
-   future multi-account operation;
-   controlled break-glass recovery.

Local Terraform state SHALL NOT be the authoritative state for shared
AWS environments.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use an **AWS-hosted remote Terraform backend** for shared
environments.

The backend SHALL use:

-   Amazon S3 for state storage;
-   S3 native state locking where supported by the approved Terraform
    version;
-   bucket versioning;
-   server-side encryption with an approved AWS KMS key;
-   TLS for transport;
-   least-privilege IAM;
-   environment-separated state keys and access;
-   GitHub Actions OIDC for normal CI/CD access;
-   logging/auditing of privileged state access.

Legacy DynamoDB-based locking SHALL NOT be introduced for new state
unless required by a supported Terraform compatibility constraint.

------------------------------------------------------------------------

## 3. State Architecture

``` text
                  Terraform Execution
                         │
                    AWS Identity
                         │
                         ▼
                 Remote State Layer
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        S3 State Objects       Native Locking
              │
              ▼
       Versioning + KMS
              │
       ┌──────┼────────┐
       ▼      ▼        ▼
      DEV   STAGING   PROD
     state    state    state
```

Development, Staging and Production MUST NOT share a Terraform state
object.

------------------------------------------------------------------------

## 4. State Segmentation

State SHALL be divided according to security, lifecycle and blast
radius.

Recommended logical segmentation:

``` text
Environment
│
├── foundation
│   ├── network
│   ├── shared IAM
│   └── foundational security
│
├── platform
│   ├── compute
│   ├── gateway
│   └── observability
│
├── data
│   ├── PostgreSQL
│   ├── Redis
│   └── RabbitMQ
│
└── workloads
    └── deployment infrastructure
```

State SHALL NOT be fragmented per individual resource.

State SHALL NOT be consolidated into one Baobab-wide monolithic state.

The final segmentation MAY evolve as implementation exposes genuine
lifecycle boundaries, but environment isolation is mandatory.

------------------------------------------------------------------------

## 5. State Key Convention

State object names MUST be deterministic and environment-aware.

Recommended pattern:

``` text
baobab/{environment}/{stack}/terraform.tfstate
```

Examples:

``` text
baobab/development/foundation/terraform.tfstate
baobab/staging/platform/terraform.tfstate
baobab/production/data/terraform.tfstate
```

Tenant identifiers SHALL NOT appear in state paths unless the state
genuinely represents dedicated tenant infrastructure.

------------------------------------------------------------------------

## 6. Backend Isolation

The preferred target architecture is:

``` text
             Nabhold AWS Organization
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
       DEV          STAGING          PROD
     Account         Account         Account
        │              │              │
        ▼              ▼              ▼
   DEV state      STAGING state    PROD state
```

A dedicated infrastructure/security account MAY host central state if
later justified.

Regardless of physical account placement:

> Production state MUST NOT be writable by Development or Staging
> deployment identities.

------------------------------------------------------------------------

## 7. Bootstrap Problem

Terraform cannot use a remote backend until the backend exists.

Bootstrap SHALL therefore be explicitly separated from normal
environment provisioning.

``` text
Fresh AWS Account
      │
      ▼
Bootstrap Identity
      │
      ▼
Create State Foundation
      │
      ├── S3 state storage
      ├── KMS key
      ├── versioning
      ├── access policy
      └── GitHub OIDC foundation
      │
      ▼
Configure Remote Backend
      │
      ▼
Normal Terraform Operation
```

Bootstrap is an exceptional lifecycle, not the normal deployment path.

------------------------------------------------------------------------

## 8. Bootstrap Structure

The repository SHALL maintain bootstrap configuration separately:

``` text
terraform/
└── bootstrap/
    ├── state/
    └── github-oidc/
```

Bootstrap code SHALL be:

-   minimal;
-   independently reviewable;
-   idempotent where practical;
-   documented through a runbook;
-   protected from accidental destruction.

Bootstrap SHALL NOT provision normal Baobab workloads.

------------------------------------------------------------------------

## 9. Bootstrap Authority

Initial bootstrap MAY require a privileged human or organisational AWS
identity.

After bootstrap:

``` text
Privileged Bootstrap Identity
            │
            ▼
       Foundation Created
            │
            ▼
     Routine Access Removed/
          Restricted
            │
            ▼
      GitHub OIDC Roles
            │
            ▼
    Normal Terraform CI/CD
```

Permanent use of administrator credentials for routine Terraform applies
is prohibited.

------------------------------------------------------------------------

## 10. GitHub Actions OIDC

Normal CI/CD SHALL authenticate to AWS using GitHub Actions OpenID
Connect.

``` text
GitHub Workflow
      │
      ▼
GitHub OIDC Token
      │
      ▼
AWS IAM Trust Policy
      │
      ▼
Environment Terraform Role
      │
      ▼
Remote State + AWS APIs
```

Long-lived AWS access keys SHALL NOT be the standard CI/CD
authentication mechanism.

Trust policies MUST restrict eligible repositories,
branches/environments and workflow contexts as appropriate.

Production role assumption SHALL additionally require the Production
GitHub environment controls defined by the CI/CD governance ADR.

------------------------------------------------------------------------

## 11. State IAM

State permissions SHALL follow least privilege.

  Identity                      Read State    Write State    Delete State   Production
  ------------------ --------------------- -------------- --------------- ------------
  Development CI                  Yes, DEV       Yes, DEV   No by default           No
  Staging CI                  Yes, STAGING   Yes, STAGING   No by default           No
  Production CI                  Yes, PROD      Yes, PROD   No by default          Yes
  PR validation        Only where required             No              No           No
  Break-glass role              Controlled     Controlled      Controlled      Audited

State deletion SHALL require exceptional authority.

------------------------------------------------------------------------

## 12. Encryption

Terraform state SHALL be encrypted at rest using an approved KMS key.

``` text
Terraform State
      │
      ▼
     S3
      │
      ▼
  KMS Encryption
      │
      ▼
Restricted Key Policy
```

KMS permissions SHALL be scoped to authorised Terraform identities and
recovery roles.

Encryption SHALL not depend solely on provider defaults.

------------------------------------------------------------------------

## 13. Versioning and Recovery

State storage SHALL have versioning enabled.

``` text
terraform.tfstate
      │
      ├── Version N
      ├── Version N-1
      ├── Version N-2
      └── ...
```

Versioning exists to support recovery from:

-   accidental state corruption;
-   erroneous state writes;
-   unintended deletion;
-   failed operational intervention.

State version restoration MUST be documented and periodically verified.

------------------------------------------------------------------------

## 14. Locking

Concurrent writes to the same state MUST be prevented.

``` text
Runner A ──┐
           ├──► State Lock ──► Terraform State
Runner B ──┘         │
                     └── waits/fails safely
```

A lock SHALL NOT be forcefully removed merely because a deployment is
slow.

Before force-unlocking, operators MUST establish that the owning
Terraform execution has terminated and document the intervention for
Production.

------------------------------------------------------------------------

## 15. State Is Sensitive

Terraform state MUST be treated as confidential infrastructure data even
when all declared outputs are non-sensitive.

State MUST NOT be:

-   committed to Git;
-   attached to issues or PRs;
-   pasted into logs;
-   uploaded as unrestricted CI artifacts;
-   shared through chat or email;
-   copied into digital-estate repositories.

`.gitignore` SHALL prevent accidental local state commits.

------------------------------------------------------------------------

## 16. Secrets and State

Terraform SHOULD avoid managing secret values where an architecture can
instead reference secret resources.

Preferred:

``` text
Terraform
   │
   ▼
Creates Secret Container/Policy
   │
   ▼
Secrets Manager
   │
   ▼
Workload retrieves secret
```

Avoid:

``` text
Plaintext Secret
      │
      ▼
Terraform Variable
      │
      ▼
Terraform State
```

The dedicated secrets ADR governs secret lifecycle and rotation.

------------------------------------------------------------------------

## 17. Cross-State Dependencies

Cross-state coupling SHALL be minimised.

Where infrastructure must discover another stack, prefer stable
discovery interfaces such as:

-   AWS resource identifiers published through controlled configuration;
-   SSM Parameter Store where appropriate;
-   DNS/service discovery;
-   explicit environment configuration.

Direct `terraform_remote_state` use MAY be permitted where justified,
but MUST NOT become the default integration mechanism.

------------------------------------------------------------------------

## 18. State Migration

Backend or state-layout migrations SHALL be treated as controlled
production changes.

``` text
Current State
     │
     ▼
Backup + Verify
     │
     ▼
Migration Plan
     │
     ▼
Controlled Migration
     │
     ▼
terraform plan
     │
     ▼
Zero Unexpected Change
```

A state migration is successful only when Terraform produces the
expected post-migration plan.

------------------------------------------------------------------------

## 19. Importing Existing Infrastructure

Pre-existing AWS resources that become Terraform-managed SHALL be
imported deliberately.

Operators MUST:

1.  identify the authoritative resource;
2.  write matching Terraform configuration;
3.  import the resource;
4.  execute `terraform plan`;
5.  resolve unexpected differences;
6.  avoid destructive recreation.

Terraform SHALL NOT recreate production infrastructure merely to obtain
state ownership.

------------------------------------------------------------------------

## 20. Break-Glass Recovery

A controlled break-glass procedure SHALL exist for state incidents.

``` text
State Incident
     │
     ▼
Suspend Applies
     │
     ▼
Establish Current AWS Reality
     │
     ▼
Inspect State Versions
     │
     ▼
Restore / Repair
     │
     ▼
terraform plan
     │
     ▼
Peer Review
     │
     ▼
Resume Applies
```

Production state repair SHALL be auditable and documented.

------------------------------------------------------------------------

## 21. State Loss

Loss of Terraform state SHALL NOT automatically trigger resource
recreation.

If state is unavailable:

> **Stop automated applies first.**

Infrastructure reality SHALL be established before recovery, import or
restoration.

Creating replacement resources blindly may cause data loss, duplicated
infrastructure or service disruption.

------------------------------------------------------------------------

## 22. Backend Availability

Terraform state is required for infrastructure change, but SHALL NOT be
placed in the runtime request path of Baobab services.

``` text
Users ──► Baobab Runtime
             │
             X
        Terraform State

CI/CD ──► Terraform State
```

A temporary state-backend outage may prevent infrastructure changes but
MUST NOT cause Baobab runtime services to fail.

------------------------------------------------------------------------

## 23. Local Development

Local-only experimentation MAY use local state when no shared AWS
resources are involved.

Local state SHALL NOT become authoritative for Development, Staging or
Production.

Developers MUST NOT manually copy local state into Production backends.

------------------------------------------------------------------------

## 24. Deletion Protection

The state bucket, KMS key and foundational access mechanisms SHALL
receive strong lifecycle protection.

Terraform configurations SHOULD protect them from accidental destruction
where practical.

Deletion of the Production state foundation SHALL require an explicit,
separately controlled procedure.

------------------------------------------------------------------------

## 25. Auditability

AWS logging SHALL provide evidence for significant state and KMS
operations.

The architecture SHOULD support determining:

-   who accessed Production state;
-   which role was assumed;
-   when state was changed;
-   which workflow performed the change;
-   whether privileged recovery access occurred.

Audit logs SHALL be protected from routine workload identities.

------------------------------------------------------------------------

## 26. Bootstrap Recovery

The bootstrap process SHALL be reproducible from repository
documentation and code.

The recovery model MUST NOT depend on one engineer remembering how the
original AWS account was configured.

Required documentation SHALL include:

-   prerequisites;
-   bootstrap identity requirements;
-   state backend creation;
-   OIDC setup;
-   backend migration;
-   validation;
-   recovery;
-   break-glass access.

------------------------------------------------------------------------

## 27. ZuriBeans Implication

ZuriBeans production deployment SHALL consume the Production
infrastructure state architecture; it SHALL NOT own its own independent
Terraform backend merely because it is the first digital estate.

``` text
Production Infrastructure State
            │
            ▼
    Baobab Infrastructure
            │
      ┌─────┴─────┐
      ▼           ▼
  Platform     ZuriBeans
```

Dedicated tenant state becomes appropriate only where an Accepted
isolation decision creates genuinely independent infrastructure
lifecycle boundaries.

------------------------------------------------------------------------

## 28. Failure Flow

``` text
Terraform Apply Starts
        │
        ▼
Acquire State Lock
        │
   ┌────┴────┐
   │         │
Success    Locked
   │         │
   ▼         ▼
Read State  Wait/Fail
   │
   ▼
Plan/Apply
   │
   ▼
Write State
   │
   ▼
Release Lock
   │
   ▼
Audit + Verify
```

Failure to acquire the lock MUST NOT cause an unlocked apply.

------------------------------------------------------------------------

## 29. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Local state for shared  Rejected                Unsafe,
  environments                                    non-collaborative and
                                                  difficult to recover

  State committed to Git  Rejected                Security and
                                                  concurrency risk

  One state for all       Rejected                Excessive blast radius
  environments                                    

  One state per resource  Rejected                Operational
                                                  fragmentation

  Unencrypted state       Rejected                State is sensitive

  Routine administrator   Rejected                Violates least
  credentials                                     privilege

  Long-lived AWS keys for Rejected                OIDC is preferred
  GitHub Actions                                  

  New DynamoDB lock table Rejected                Native S3 locking is
  by default                                      preferred for supported
                                                  Terraform versions

  Automatic force-unlock  Rejected                Risk of concurrent
                                                  state corruption

  State as application    Rejected                Couples runtime to
  configuration                                   provisioning internals

  Tenant state per tenant Rejected                Tenant does not imply
  by default                                      physical infrastructure
                                                  boundary
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 30. Consequences

### Positive

-   Safe collaborative Terraform execution.
-   Strong Development/Staging/Production separation.
-   Reduced risk of concurrent state corruption.
-   Recoverable state history.
-   No routine long-lived AWS deployment credentials.
-   Auditable Production infrastructure access.
-   Supports future AWS account separation.
-   Provides a stable foundation for subsequent Terraform modules.

### Costs

-   Bootstrap requires careful privileged setup.
-   State IAM and KMS policies add operational complexity.
-   State segmentation requires discipline.
-   Recovery procedures must be tested.
-   Cross-stack dependencies require explicit design.

These costs are accepted.

------------------------------------------------------------------------

## 31. Decision Rules

The following rules are authoritative:

> **Shared AWS environments SHALL use remote Terraform state.**

> **Development, Staging and Production SHALL NOT share Terraform
> state.**

> **Terraform state SHALL be encrypted, versioned, access-controlled and
> protected against concurrent writes.**

> **S3 native state locking SHALL be preferred for supported Terraform
> versions; new DynamoDB locking infrastructure SHALL not be introduced
> without a compatibility reason.**

> **GitHub Actions SHALL normally authenticate to AWS through OIDC
> rather than long-lived AWS access keys.**

> **Production state SHALL NOT be writable by Development or Staging
> identities.**

> **Terraform state SHALL be treated as confidential even when outputs
> are marked non-sensitive.**

> **State loss SHALL stop automated applies until infrastructure reality
> and recovery strategy are established.**

> **Persistent state repair or migration SHALL conclude with a reviewed
> Terraform plan showing no unexplained infrastructure change.**

> **ZuriBeans SHALL consume the Baobab Production infrastructure
> architecture rather than establish an independent
> infrastructure-control model.**

------------------------------------------------------------------------

## 32. Implementation Implications

Implementation of this ADR SHALL establish at minimum:

``` text
terraform/bootstrap/
├── state/
└── github-oidc/
```

and provide:

-   remote S3 state storage;
-   native state locking;
-   KMS encryption;
-   bucket versioning;
-   restrictive bucket policies;
-   environment-specific state paths;
-   OIDC trust;
-   environment Terraform roles;
-   Production access separation;
-   state recovery documentation;
-   force-unlock procedure;
-   state migration procedure;
-   import procedure;
-   break-glass procedure;
-   verification tooling.

No Production application infrastructure SHALL depend on undocumented
manually created state foundations.

------------------------------------------------------------------------

## 33. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0005 --- Network and Trust-Zone Architecture**

It shall define:

-   VPC architecture;
-   Availability Zone strategy;
-   public and private subnet design;
-   ingress, application, data and management trust zones;
-   routing;
-   NAT and outbound access;
-   VPC endpoints;
-   security groups;
-   network ACL policy;
-   APISIX placement;
-   private data services;
-   workload-to-service connectivity;
-   administrative access;
-   DNS boundaries;
-   future multi-region implications;
-   and the network controls required to enforce Baobab's default-deny
    infrastructure model.
