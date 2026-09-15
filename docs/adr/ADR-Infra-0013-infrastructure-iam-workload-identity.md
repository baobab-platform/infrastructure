# ADR-Infra-0013 --- Infrastructure IAM and Workload Identity

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:** ADR-Infra-0001, 0002, 0003, 0004, 0005, 0006, 0007,
    0009, 0010, 0011, 0012
-   **Follow-on:** ADR-Infra-0014 --- Secrets, Keys and Certificate
    Management

## 1. Context

Baobab requires two distinct identity planes:

1.  **Infrastructure/workload identity** --- AWS IAM identities
    controlling AWS resources and infrastructure operations.
2.  **Application identity** --- users, service clients, roles, scopes
    and authorization governed by `baobab-iam` and Keycloak.

These planes SHALL remain separate. Production must securely support
GitHub Actions, Terraform, ECS/Fargate workloads, registries, Secrets
Manager, KMS, RDS, ElastiCache, Amazon MQ, telemetry, backups,
infrastructure administration and future cross-account operation without
relying on long-lived shared cloud credentials.

## 2. Decision

Baobab SHALL use **AWS IAM roles and temporary credentials** as the
default infrastructure and workload identity mechanism.

The architecture SHALL use:

-   GitHub Actions → AWS federation through **OIDC**;
-   separate deployment roles by environment;
-   distinct ECS **task execution roles** and **application task
    roles**;
-   workload-specific application roles;
-   least-privilege resource policies;
-   environment/account separation;
-   controlled human federation;
-   tightly governed break-glass access;
-   explicit cross-account trust;
-   auditable role assumption.

Long-lived AWS access keys SHALL NOT be the normal authentication
mechanism for CI/CD, workloads or human administration.

## 3. Identity Planes

``` text
                     BAOBAB IDENTITY
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
       AWS Infrastructure          Application IAM
          Identity                 baobab-iam
             │                     Keycloak
             ▼                           ▼
     AWS resources/actions       users/clients/roles/
                                 application access
```

AWS IAM SHALL NOT replace Keycloak. Keycloak SHALL NOT grant Terraform
or ECS workloads AWS administrative permissions.

## 4. Principal Classes

  Principal              Purpose
  ---------------------- -------------------------------
  GitHub CI role         Validation/build integration
  Terraform plan role    Read/plan infrastructure
  Terraform apply role   Approved environment mutation
  ECS execution role     ECS runtime bootstrap
  ECS task role          Application AWS API access
  Backup role            Backup/recovery operations
  Observability role     Telemetry access
  Human operator role    Controlled administration
  Break-glass role       Exceptional emergency access

These SHALL not collapse into one platform administrator identity.

## 5. Environment Separation

Development, Staging and Production SHALL use distinct IAM trust and
permission boundaries.

``` text
GitHub
  ├──► Development Role ──► Development
  ├──► Staging Role ──────► Staging
  └──► Production Role ───► Production
```

A Development role SHALL NOT have Production deployment permissions.
Where environments use separate AWS accounts, roles SHALL reside within
or be explicitly trusted by the relevant account. If accounts are
initially shared, equivalent logical separation SHALL be preserved for
later migration.

## 6. GitHub Actions OIDC

GitHub Actions SHALL federate to AWS using OIDC.

``` text
GitHub Workflow
      │ OIDC token
      ▼
AWS IAM OIDC Provider
      │
      ▼
AssumeRoleWithWebIdentity
      │
      ▼
Temporary AWS Credentials
```

OIDC trust policies SHALL restrict assumptions to approved organization,
repository, ref/branch, GitHub Environment, workflow identity and
audience as appropriate. Arbitrary repositories SHALL NOT be able to
assume Production roles.

## 7. Production Deployment Trust

Production deployment SHALL follow:

``` text
PR → Validate/Plan → Merge → Protected Production Environment
   → Required Approval → OIDC Role Assumption → Apply/Deploy
```

Untrusted pull-request code SHALL never receive Production mutation
credentials.

Terraform plan and apply SHOULD use different permission levels. A
universal permanent `AdministratorAccess` Terraform role is prohibited
as the steady-state model.

## 8. Permission Boundaries and Guardrails

IAM permission boundaries SHOULD constrain roles capable of creating or
modifying IAM identities where this materially reduces
privilege-escalation risk.

Where AWS Organizations is used, Service Control Policies SHOULD define
high-risk account-level ceilings. SCPs and permission boundaries
complement, but do not replace, least-privilege IAM policies.

Guardrails SHOULD protect audit infrastructure, protected backups,
environment boundaries and sensitive data services while preserving
documented recovery paths.

## 9. ECS Execution Role

Each ECS workload SHALL distinguish its **task execution role** from its
application task role.

The execution role MAY permit:

-   ECR image pulls;
-   supported runtime log bootstrap;
-   startup secret retrieval where ECS integration requires it.

Application code SHALL not use the execution role as its AWS identity.

## 10. ECS Task Role

Application containers SHALL use workload-specific ECS task roles.

``` text
Application Container
       │
       ▼
ECS Task Role
       ├── Secrets Manager
       ├── S3 where required
       ├── KMS where required
       └── explicitly approved AWS APIs
```

A universal shared Baobab task role is prohibited.

Conceptually:

``` text
cp-task-role
trade-task-role
iam-task-role
cms-task-role
pulse-task-role
zuribeans-task-role
```

Exact names SHALL follow infrastructure naming conventions.

## 11. Workload Least Privilege

An application SHALL receive only AWS permissions required by its
responsibilities.

Being part of Baobab SHALL not grant access to every AWS service or
every tenant's resources.

A normal response to `AccessDenied` SHALL be to determine the required
minimal permission---not to attach broad administrator privileges.

## 12. Service-to-Service Identity

AWS IAM SHALL govern AWS resource access. Baobab API authorization SHALL
use the approved application IAM architecture.

``` text
Service A
   ├── AWS API ─────► AWS IAM
   └── Baobab API ──► baobab-iam / application authorization
```

Possession of an AWS task role SHALL not authorize arbitrary Baobab API
calls.

## 13. Keycloak Boundary

`baobab-iam`/Keycloak owns application identities including users,
service clients, application roles/scopes and tenant-aware authorization
constructs defined by IAM ADRs.

AWS IAM owns infrastructure identities.

AWS IAM users SHALL NOT substitute for Baobab application users, and
Keycloak SHALL NOT substitute for AWS workload identity.

## 14. Data-Service Identity

Database access SHALL follow ADR-Infra-0010. Where RDS IAM
authentication is used, the AWS role and PostgreSQL role remain distinct
authorization layers.

Where ElastiCache supports compatible IAM authentication, workload roles
MAY participate; otherwise workload-specific cache credentials SHALL
come from approved secret storage.

Amazon MQ management access through AWS IAM and RabbitMQ protocol-level
user authorization SHALL remain distinct.

## 15. APISIX Identity

AWS IAM governs infrastructure access surrounding APISIX. APISIX
administrative credentials and gateway authentication remain separate.

The Control Plane reconciler SHALL receive only permissions required to
manage approved APISIX configuration. Possession of an AWS task role
SHALL not imply APISIX administrator access.

## 16. Secrets and KMS Access

Secrets SHALL be accessible only to approved workload roles.

``` text
trade-task-role ──► production/baobab-trade/*
iam-task-role   ──► production/baobab-iam/*
```

Wildcard access to all Production secrets is prohibited for normal
workloads.

KMS permissions SHALL be scoped to required keys and operations. Key
administrators and key users SHOULD be separated. Detailed secret/key
architecture is governed by ADR-Infra-0014.

## 17. S3 and Registry Access

S3 permissions SHALL be constrained by bucket, prefix where practical,
action, environment and purpose. Routine workload policies equivalent to
`s3:*` on `*` are prohibited.

Registry access follows ADR-Infra-0007:

``` text
CI Publisher ──► push approved artifact
ECS Execution ─► pull approved artifact
```

Runtime workloads SHALL not receive registry administration or deletion
rights.

## 18. Cross-Account Access

Cross-account access SHALL use explicit role assumption and trust.

``` text
Source Account Role
       │
       ▼
Target Account Trust Policy
       │
       ▼
Target Scoped Role
```

Trust SHALL identify the principal, actions, resources, conditions and
environment. Implicit organization-wide Production write access is
prohibited.

## 19. Human Access

Human AWS access SHOULD use federation through the approved
organizational identity mechanism/AWS IAM Identity Center rather than
IAM users with permanent keys.

Privileged human access SHALL require strong authentication/MFA and role
assumption.

Role categories MAY include ReadOnly, Operator, Security, Database
Administrator, Infrastructure Administrator and Break Glass.

## 20. IAM Users and Root

IAM users SHALL NOT be the normal identity model. Any exceptional IAM
user requires explicit justification, minimal permissions, owner,
credential rotation, monitoring and periodic review.

AWS root credentials SHALL not be used for normal administration. Root
access is reserved for operations that explicitly require it, protected
with strong MFA and recovery controls.

## 21. Break-Glass Access

Production SHALL maintain controlled emergency access.

``` text
Incident → Authorised Escalation → Break-Glass Role
         → Time-Bounded Privilege → Audited Action
         → Revoke/Review
```

Break-glass access SHALL be exceptional, strongly authenticated,
auditable and tested before an actual emergency. It SHALL NOT become a
routine deployment path.

## 22. Session and Role-Chaining Policy

Role sessions SHALL be bounded to durations appropriate to the
operation. Production deployment sessions SHOULD be short-lived.

Role chaining SHALL be minimized. Cross-account trust paths SHALL be
documented and reviewable.

## 23. Naming and Tags

IAM roles SHOULD follow:

``` text
baobab-{environment}-{workload}-{purpose}
```

Examples:

``` text
baobab-production-trade-task
baobab-production-cp-task
baobab-production-infrastructure-apply
```

Supported IAM resources SHOULD carry mandatory infrastructure tags such
as Platform, Environment, ManagedBy, Repository, Service, Owner,
CostCentre and DataClassification where meaningful.

## 24. Infrastructure Role Separation

Production SHOULD distinguish:

``` text
Infrastructure Plan
Infrastructure Apply
Application Deployment
Security Administration
Backup/Recovery
Read-Only Audit
```

Deploying an approved application image digest SHOULD require a narrower
role than full Terraform infrastructure administration.

## 25. Terraform State

Only approved infrastructure roles SHALL write Terraform state.

Application task roles SHALL have no Terraform state access. Production
state SHALL not be exposed to arbitrary non-Production identities.

## 26. Audit

AWS identity activity SHALL be auditable through CloudTrail and approved
AWS audit mechanisms.

Audit coverage SHALL include relevant:

-   role assumptions;
-   IAM changes;
-   infrastructure mutations;
-   KMS operations where supported;
-   privileged administrative actions.

Audit data SHALL be protected from casual modification by the identities
being audited.

## 27. Access Reviews and Analysis

Production roles, policies and trusts SHALL be periodically reviewed
for:

-   unused permissions;
-   unused roles;
-   stale trust;
-   obsolete workflows;
-   excessive wildcards;
-   expired exceptions;
-   cross-account access;
-   break-glass configuration.

AWS IAM Access Analyzer and related AWS capabilities SHOULD be used to
identify unintended external access and policy-refinement opportunities.

## 28. Policy Testing

IAM tests SHALL verify both expected allows and expected denies.

``` text
Expected Allow
      +
Expected Deny
```

For example, a ZuriBeans role SHALL be tested to confirm it cannot
access Thamani-only resources where physical resource separation exists.

## 29. Tenant Isolation

AWS IAM MAY contribute to physical workload isolation but SHALL not
become Baobab's primary logical tenant authorization system.

``` text
AWS IAM
  └── workload/resource identity

Baobab IAM + Application
  └── tenant/legal-entity authorization
```

Tenant context SHALL not be inferred solely from an ECS task role.

Tenant SHALL NOT imply AWS account, role hierarchy or dedicated
infrastructure identity. Dedicated roles MAY follow an accepted
IsolationProfile under ADR-Infra-0015.

## 30. ZuriBeans Go-Live

ZuriBeans SHALL validate the complete workload-identity chain:

``` text
GitHub Actions
      │ OIDC
      ▼
Scoped Deployment Role
      │
      ▼
ECS Service
      ├── Execution Role ──► image/log startup
      └── Task Role ───────► ZuriBeans-approved AWS resources
```

ZuriBeans SHALL NOT receive Thamani roles, infrastructure-administrator
privileges, unrestricted Production secret access, broad Terraform
permissions or APISIX administrator access merely because it is a
digital estate.

## 31. Control Plane Provisioner Identity

Where `baobab-cp` reconciles approved infrastructure-adjacent desired
state, it SHALL use capability-scoped provisioner identities.

``` text
baobab-cp
    │
    ▼
Scoped Provisioner Identity
    │
    ▼
Approved Capability
```

The Control Plane SHALL NOT receive a universal Production
infrastructure-administrator role.

## 32. No Credential Transitivity

A workload's ability to call another service SHALL not allow it to
inherit that service's AWS permissions.

``` text
ZuriBeans ──calls──► Trade ──► Trade AWS permissions
```

ZuriBeans retains its own identity and does not inherit the Trade task
role.

Temporary AWS credentials SHALL not be logged, persisted to shared
volumes, returned through APIs or propagated downstream.

## 33. Infrastructure as Code

Terraform SHALL manage IAM infrastructure, including where applicable:

``` text
terraform/modules/iam/
├── GitHub OIDC provider
├── environment deployment roles
├── Terraform plan/apply roles
├── ECS execution roles
├── workload task roles
├── permission boundaries
├── cross-account roles
├── observability roles
├── backup/recovery roles
└── policy attachments
```

Policies SHALL be composed from explicit workload requirements rather
than repository names alone.

## 34. Bootstrap Boundary

IAM bootstrap SHALL be minimal and separately controlled.

``` text
Initial Trusted Administrator
        │
        ▼
Bootstrap OIDC / State / Core Roles
        │
        ▼
Normal Federated Operations
```

Routine infrastructure changes SHALL use federated operational roles
after bootstrap.

## 35. Production Verification

Before go-live, verification SHALL demonstrate:

-   GitHub Actions authenticates through OIDC;
-   normal workflows require no long-lived AWS keys;
-   Development identities cannot deploy Production;
-   untrusted PRs cannot assume Production mutation roles;
-   execution and task roles are distinct;
-   workload task roles are least privilege;
-   ZuriBeans cannot read unrelated Production secrets/resources;
-   application roles cannot access Terraform state;
-   Production role assumptions are audited;
-   human privileged access requires strong authentication;
-   break-glass access works and is auditable;
-   cross-account trusts are explicit;
-   expected-deny tests pass.

## 36. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Long-lived AWS keys in  Rejected                Avoidable credential
  GitHub Secrets                                  risk

  One CI role for all     Rejected                Weak environment
  environments                                    isolation

  Production apply from   Rejected                Supply-chain privilege
  untrusted PR                                    risk

  One shared ECS task     Rejected                Excessive lateral
  role                                            privilege

  Application using       Rejected                Blurs runtime identity
  execution role                                  

  `AdministratorAccess`   Rejected                Excessive privilege
  for normal Terraform                            

  AWS IAM as Baobab user  Rejected                Wrong identity plane
  IAM                                             

  Keycloak as AWS         Rejected                Wrong identity plane
  infrastructure IAM                              

  IAM users for normal    Rejected                Federation preferred
  human access                                    

  Root for routine        Rejected                Excessive privilege
  administration                                  

  Tenant = AWS            Rejected                Wrong tenancy model
  account/role hierarchy                          

  Wildcard Production     Rejected                Cross-workload exposure
  secret access                                   

  Network reachability as Rejected                Network is not identity
  authorization                                   
  -----------------------------------------------------------------------

## 37. Consequences

### Positive

-   Removes long-lived AWS credentials from normal CI/CD.
-   Strong environment separation.
-   Workload-specific AWS identities.
-   Clear execution-role/task-role boundary.
-   Preserves Keycloak as application IAM.
-   Reduces lateral movement.
-   Supports future multi-account operation.
-   Provides auditable Production access.
-   Gives ZuriBeans a production-grade identity chain without
    platform-wide privileges.

### Costs

-   More roles and policies must be maintained.
-   Least-privilege design requires testing.
-   OIDC trust requires careful configuration.
-   Cross-account deployment becomes explicit.
-   Permission boundaries/SCPs add governance complexity.
-   Break-glass procedures require operational testing.
-   Access reviews become an ongoing responsibility.

These costs are accepted.

## 38. Decision Rules

> **AWS IAM roles with temporary credentials SHALL be Baobab's default
> infrastructure and workload identity mechanism.**

> **GitHub Actions SHALL use OIDC federation to AWS rather than
> long-lived AWS access keys for normal CI/CD.**

> **Development, Staging and Production SHALL have separate deployment
> trust and permissions.**

> **Untrusted pull-request workflows SHALL NOT receive Production
> mutation credentials.**

> **ECS task execution roles and application task roles SHALL be
> distinct.**

> **Each independently operated workload SHALL use a scoped task role
> rather than a universal Baobab role.**

> **AWS IAM SHALL govern infrastructure/resource identity;
> `baobab-iam`/Keycloak SHALL govern application identity and
> authorization.**

> **Normal workloads SHALL NOT receive infrastructure-administrator
> permissions.**

> **Human AWS administration SHOULD use federation and role assumption
> rather than long-lived IAM-user credentials.**

> **Break-glass access SHALL be exceptional, strongly authenticated,
> time-bounded where practical and auditable.**

> **Tenant SHALL NOT imply AWS account, IAM hierarchy or dedicated
> infrastructure identity.**

> **Control Plane provisioner identities SHALL be capability-scoped
> rather than universal Production administrators.**

## 39. Implementation Implications

Implementation SHALL progressively establish:

``` text
AWS IAM
├── GitHub OIDC
│   ├── development roles
│   ├── staging roles
│   └── production roles
├── Terraform
│   ├── plan roles
│   └── apply roles
├── ECS
│   ├── execution roles
│   └── workload task roles
├── Operations
│   ├── read-only
│   ├── operator
│   ├── security
│   └── break-glass
└── Scoped Capabilities
    ├── secrets
    ├── KMS
    ├── backup
    ├── observability
    └── approved provisioner access
```

IAM implementation SHALL be reviewed alongside affected workload ADRs
and actual required AWS actions.

## 40. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0014 --- Secrets, Keys and Certificate Management**

It shall define AWS Secrets Manager, SSM Parameter Store boundaries, KMS
key architecture, secret ownership and naming, rotation, application
retrieval, Terraform state avoidance, ACM and internal certificates, key
administration, break-glass secret access, audit and secret lifecycle
requirements across Baobab workloads.
