# ADR-Infra-0003 --- Terraform Architecture and Module Strategy

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0001 --- Environment Provisioner Boundary
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
-   **Follow-on:** ADR-Infra-0004 --- Terraform State, Locking and
    Bootstrap

------------------------------------------------------------------------

## 1. Context

`nabhold/infrastructure` is the authoritative repository for declarative
environment provisioning and deployment infrastructure for the Baobab
ecosystem.

ADR-Infra-0002 establishes separate Local, Development, Staging, and
Production environments, with AWS `af-south-1` as the initial production
region.

Terraform therefore requires an architecture that:

-   supports explicit environment isolation;
-   promotes reuse without coupling environments;
-   supports multiple AWS accounts;
-   permits future regional expansion;
-   prevents configuration drift;
-   supports automated CI/CD validation and deployment;
-   provides stable infrastructure contracts to Baobab workloads;
-   avoids embedding Baobab business or tenant-management logic in
    Terraform;
-   remains understandable enough to operate and recover manually when
    necessary.

Terraform SHALL be treated as production software.

------------------------------------------------------------------------

## 2. Decision

Terraform SHALL be the authoritative Infrastructure-as-Code mechanism
for AWS environments managed by `nabhold/infrastructure`.

The architecture SHALL use:

1.  reusable infrastructure modules;
2.  explicit environment compositions;
3.  isolated state boundaries;
4.  pinned Terraform and provider versions;
5.  typed and validated inputs;
6.  deliberate module outputs;
7.  automated formatting, validation, linting, security and policy
    checks;
8.  plan-before-apply workflows;
9.  immutable reviewed changes;
10. minimal reliance on imperative provisioning scripts.

Terraform workspaces SHALL NOT be the primary mechanism for separating
Development, Staging, and Production.

------------------------------------------------------------------------

## 3. Architecture

``` text
                    nabhold/infrastructure
                            │
            ┌───────────────┴────────────────┐
            │                                │
        bootstrap/                       modules/
            │                                │
     state + OIDC +                  reusable building
     foundational IAM                    blocks
            │                                │
            └───────────────┬────────────────┘
                            │
                            ▼
                       environments/
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        development       staging      production
              │             │             │
              ▼             ▼             ▼
          AWS Dev       AWS Staging     AWS Prod
```

The separation between `modules/` and `environments/` is mandatory.

------------------------------------------------------------------------

## 4. Repository Structure

The target Terraform structure SHALL be:

``` text
terraform/
├── bootstrap/
│   ├── state/
│   └── github-oidc/
│
├── modules/
│   ├── network/
│   ├── iam/
│   ├── kms/
│   ├── secrets/
│   ├── dns/
│   ├── certificates/
│   ├── postgres/
│   ├── redis/
│   ├── rabbitmq/
│   ├── compute/
│   ├── apisix/
│   ├── telemetry/
│   └── backup/
│
└── environments/
    ├── development/
    ├── staging/
    └── production/
```

Additional modules MAY be introduced when justified by an Accepted ADR
or clear infrastructure requirement.

The repository SHALL NOT create speculative modules merely because an
AWS service might be useful later.

------------------------------------------------------------------------

## 5. Module Responsibility

A Terraform module SHALL represent a coherent infrastructure capability.

  Module           Responsibility
  ---------------- -------------------------------------------------------
  `network`        VPC, subnets, routing, endpoints and network controls
  `iam`            AWS roles and infrastructure permissions
  `kms`            Encryption keys and policies
  `secrets`        Secret infrastructure and access policy
  `dns`            Hosted zones and DNS resources
  `certificates`   Managed TLS certificates
  `postgres`       PostgreSQL infrastructure
  `redis`          Redis infrastructure
  `rabbitmq`       RabbitMQ infrastructure
  `compute`        Selected production compute platform
  `apisix`         APISIX and supporting infrastructure
  `telemetry`      Infrastructure supporting logs, metrics and traces
  `backup`         Backup policies, vaults and lifecycle configuration

Modules SHOULD encapsulate infrastructure complexity, but MUST NOT
conceal architectural decisions that should instead be governed by ADRs.

------------------------------------------------------------------------

## 6. Composition Model

Modules SHALL NOT independently determine the environment in which they
execute.

Environment compositions SHALL assemble modules.

``` text
Environment Composition
        │
        ├── network
        ├── IAM
        ├── KMS
        ├── secrets
        ├── data services
        ├── compute
        ├── gateway
        ├── telemetry
        └── backup
```

For example:

``` hcl
module "network" {
  source = "../../modules/network"

  environment = local.environment
  region      = local.region
  cidr_block  = var.vpc_cidr
}

module "postgres" {
  source = "../../modules/postgres"

  environment = local.environment
  subnet_ids  = module.network.data_subnet_ids
}
```

Environment-specific values SHALL remain in environment compositions or
their controlled variable sources.

------------------------------------------------------------------------

## 7. Environment Isolation

Each environment SHALL have an independent Terraform root.

``` text
environments/
│
├── development/
│   └── independent root + state
│
├── staging/
│   └── independent root + state
│
└── production/
    └── independent root + state
```

The following is prohibited:

``` text
One Terraform root
       │
       ▼
workspace = dev/staging/prod
       │
       ▼
entire Baobab infrastructure
```

Terraform workspaces MAY be used for narrowly scoped technical purposes
where explicitly justified, but SHALL NOT constitute Baobab's principal
environment isolation mechanism.

------------------------------------------------------------------------

## 8. Environment Configuration

Environment differences SHALL be explicit.

``` text
development
├── smaller capacity
├── reduced redundancy
└── non-production policies

staging
├── production-like topology
├── controlled capacity
└── production validation

production
├── high availability
├── backup
├── monitoring
├── stronger controls
└── production capacity
```

Environment compositions SHOULD use the same reusable modules wherever
practical.

Production SHALL NOT use a fundamentally different module implementation
simply because it is Production.

------------------------------------------------------------------------

## 9. Provider Strategy

AWS providers SHALL be configured at the environment composition level.

Modules SHOULD NOT define their own provider credentials.

``` text
GitHub Actions
      │
      ▼
AWS OIDC
      │
      ▼
Environment Deployment Role
      │
      ▼
Terraform AWS Provider
      │
      ▼
Modules
```

Modules MUST inherit or explicitly receive approved provider
configurations.

Static AWS credentials SHALL NOT be embedded in Terraform files,
`.tfvars`, repository secrets files, container images, modules, or
scripts.

------------------------------------------------------------------------

## 10. Version Management

Terraform and provider versions SHALL be constrained and deliberately
upgraded.

Each Terraform root SHALL declare its required Terraform and provider
versions.

``` hcl
terraform {
  required_version = "~> 1.x"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> <approved-major.minor>"
    }
  }
}
```

Exact supported versions SHALL follow the repository's environment
contract and automated dependency governance.

Major version upgrades SHALL NOT occur implicitly.

Provider lock files SHALL be committed where appropriate.

------------------------------------------------------------------------

## 11. Input Design

Module variables SHALL have explicit types and descriptions, use
validation where meaningful, avoid unnecessary defaults, and distinguish
required from optional configuration.

``` hcl
variable "environment" {
  description = "Baobab deployment environment."
  type        = string

  validation {
    condition = contains(
      ["development", "staging", "production"],
      var.environment
    )

    error_message = "Unsupported Baobab environment."
  }
}
```

Security-sensitive configuration MUST fail closed rather than silently
selecting permissive defaults.

------------------------------------------------------------------------

## 12. Output Design

Module outputs SHALL expose only information required by other
infrastructure components or deployment automation.

``` text
network
   │
   ├── private_subnet_ids
   ├── data_subnet_ids
   └── vpc_id
          │
          ▼
      consumers
```

Modules MUST NOT expose credentials through Terraform outputs.

Sensitive outputs, where unavoidable, MUST be explicitly marked
`sensitive`.

Terraform state SHALL nevertheless be treated as sensitive because
`sensitive = true` does not remove values from state.

------------------------------------------------------------------------

## 13. Dependency Management

Dependencies SHOULD flow through explicit module outputs and inputs.

``` text
network
   │
   ▼
compute
   │
   ▼
application deployment
```

Implicit dependencies SHOULD be avoided.

`depends_on` SHALL be used only where Terraform cannot infer the
dependency correctly.

Remote-state dependencies between independently managed stacks SHOULD be
minimised.

Where cross-stack information is required, stable infrastructure
discovery mechanisms SHOULD be preferred over extensive Terraform state
coupling.

------------------------------------------------------------------------

## 14. Tenant Boundary

Terraform SHALL NOT become Baobab's tenant-management system.

Terraform MUST NOT implement tenant lifecycle state machines,
CanonicalEntity resolution, CapabilityBinding resolution, business
Context resolution, customer onboarding workflows, commerce logic, ERP
business logic, IAM user lifecycle, or market-selection logic.

These belong to their respective Baobab platform components.

``` text
Baobab Control Plane
        │
        │ desired infrastructure requirement
        ▼
Approved Infrastructure Interface
        │
        ▼
nabhold/infrastructure
        │
        ▼
Physical Infrastructure
```

Terraform MAY provision infrastructure required by an approved
`IsolationProfile`, but it SHALL NOT decide the tenant's business-level
isolation policy.

------------------------------------------------------------------------

## 15. Resource Naming and Tagging

Modules SHALL consume common naming and tagging conventions.

``` text
                 Common Metadata
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
      network       postgres       compute
         │             │             │
         └─────────────┼─────────────┘
                       ▼
              Consistent AWS estate
```

Mandatory metadata defined by ADR-Infra-0002 SHALL be propagated
wherever the AWS resource supports tagging.

Modules SHALL NOT independently invent incompatible naming conventions.

------------------------------------------------------------------------

## 16. Security by Default

Terraform modules MUST prefer secure defaults.

  Concern                  Default
  ------------------------ -------------------------------------
  Public database access   Disabled
  Encryption at rest       Enabled
  TLS                      Required where supported
  Public subnets           Only where architecturally required
  IAM                      Least privilege
  Security groups          Deny unless required
  Secrets                  External secret management
  Storage encryption       Enabled
  Logging                  Enabled where appropriate
  Deletion protection      Production-sensitive resources

A module MUST NOT make a resource publicly accessible merely to simplify
deployment.

------------------------------------------------------------------------

## 17. Lifecycle Protection

Production stateful resources SHALL receive appropriate lifecycle
safeguards.

Where appropriate:

``` hcl
lifecycle {
  prevent_destroy = true
}
```

However, `prevent_destroy` SHALL NOT be treated as a substitute for
backups, IAM controls, protected deployment environments, plan review,
or recovery procedures.

Destructive production changes SHALL require deliberate review.

------------------------------------------------------------------------

## 18. Terraform Validation Pipeline

Every Terraform change SHALL pass automated validation before merge.

``` text
Pull Request
     │
     ▼
terraform fmt
     │
     ▼
terraform validate
     │
     ▼
lint
     │
     ▼
security scanning
     │
     ▼
policy checks
     │
     ▼
terraform plan
     │
     ▼
review
     │
     ▼
merge
```

The exact tooling MAY evolve, but equivalent controls MUST remain.

------------------------------------------------------------------------

## 19. Plan and Apply Separation

Pull requests MAY initialise Terraform, validate, lint, scan, execute
policy checks, and generate plans.

Untrusted pull requests MUST NOT perform Production applies.

``` text
PR
 │
 ├── Validate ──► Allowed
 ├── Scan ──────► Allowed
 ├── Plan ──────► Controlled
 │
 └── Apply PROD ──X
```

Production apply SHALL occur only through an authorised post-merge
workflow with appropriate GitHub environment protection and AWS role
assumption.

------------------------------------------------------------------------

## 20. Policy as Code

Critical infrastructure rules SHOULD become machine-enforceable where
practical.

Examples include:

-   databases cannot be publicly accessible;
-   encryption cannot be disabled;
-   mandatory tags must exist;
-   Production resources require approved configuration;
-   unrestricted ingress is prohibited except where explicitly approved;
-   sensitive storage must be encrypted;
-   Production backup requirements cannot be disabled casually.

ADRs remain the architectural source of truth.

Policy-as-code SHALL enforce rather than replace ADR decisions.

------------------------------------------------------------------------

## 21. Testing Strategy

Terraform quality SHALL be established progressively through four
levels:

  Level                        Purpose
  ---------------------------- --------------------------------------
  Static validation            Syntax and configuration correctness
  Security/policy validation   Architectural and security rules
  Plan validation              Expected infrastructure changes
  Deployment verification      Actual infrastructure behaviour

Critical reusable modules SHOULD receive automated tests where the risk
justifies them.

Production readiness SHALL not be inferred merely because
`terraform validate` succeeds.

------------------------------------------------------------------------

## 22. Imperative Scripts

Terraform SHALL be preferred for declarative infrastructure.

Scripts MAY be used for bootstrap operations, verification, migration
assistance, operational recovery, and tasks Terraform cannot safely
model.

Scripts SHALL NOT silently become a parallel infrastructure provisioning
system.

``` text
Terraform
   +
20 shell scripts
   +
manual AWS Console
   +
tribal knowledge
        │
        ▼
Unknown infrastructure state
```

Desired pattern:

``` text
              Terraform
                  │
        authoritative desired state
                  │
                  ▼
                 AWS
                  │
                  ▼
         verification tooling
```

------------------------------------------------------------------------

## 23. Manual AWS Changes

Manual Production changes through the AWS Console or CLI SHALL be
exceptional.

Permitted cases include incident response, break-glass recovery,
emergency containment, and explicitly documented bootstrap operations.

Any persistent manual infrastructure change MUST subsequently be
reconciled into Terraform.

``` text
Emergency Manual Change
          │
          ▼
      Stabilise
          │
          ▼
      Document
          │
          ▼
Reconcile Terraform
          │
          ▼
     Verify State
```

------------------------------------------------------------------------

## 24. Drift Management

Terraform drift SHALL be considered an operational defect unless
explicitly justified.

Scheduled or deployment-triggered drift detection SHOULD eventually
identify differences between:

``` text
Terraform Desired State
          │
          ▼
       compare
          │
          ▼
AWS Actual State
```

Unexpected Production drift SHALL generate an operational investigation
rather than automatic destructive reconciliation.

------------------------------------------------------------------------

## 25. State Boundaries

Terraform state SHALL NOT contain the entire Baobab ecosystem in one
monolithic state file.

State SHOULD be divided according to lifecycle, security and
blast-radius boundaries.

``` text
AWS Account
│
├── foundational state
│
├── network/platform state
│
├── data-service state
└── workload/deployment state
```

State fragmentation MUST nevertheless remain manageable.

Creating a separate state file for every trivial resource is equally
undesirable.

The exact state architecture, backend, encryption and locking mechanism
is governed by ADR-Infra-0004.

------------------------------------------------------------------------

## 26. Cross-Environment Reuse

Reusable modules MAY be shared across environments.

Environment state MUST NOT be shared.

``` text
                    modules/
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
         DEV         STAGING       PROD
          │            │            │
       state A       state B       state C
```

This provides implementation consistency without compromising
environment isolation.

------------------------------------------------------------------------

## 27. Multi-Region Readiness

Modules SHOULD accept region-sensitive inputs where appropriate.

They MUST NOT assume that `af-south-1` will remain Baobab's only region
forever.

However, modules SHALL NOT introduce speculative multi-region
replication before an Accepted regional architecture decision exists.

``` text
Today
  │
  ▼
af-south-1
  │
  │ architecture remains region-capable
  ▼
Future ADR
  │
  ▼
Additional Region(s)
```

------------------------------------------------------------------------

## 28. ZuriBeans Implication

ZuriBeans is the first production validation workload.

Terraform SHALL therefore permit:

``` text
Infrastructure Modules
        │
        ▼
Production Environment
        │
        ├── Baobab Platform Services
        │
        ├── Required Engines
        │
        └── ZuriBeans Workloads
```

Terraform modules MUST NOT contain ZuriBeans-specific business
assumptions.

Where a resource genuinely belongs exclusively to ZuriBeans, the
environment composition MAY declare that workload explicitly.

This distinction allows subsequent estates such as Thamani to consume
the same infrastructure architecture without copying or rewriting
modules.

------------------------------------------------------------------------

## 29. Module Evolution

A reusable module is an internal infrastructure API.

Changes to module inputs, outputs or behaviour SHALL therefore consider
downstream consumers.

Breaking module changes SHOULD be explicit, reviewed, include migration
instructions where required, and avoid simultaneous uncontrolled changes
across environments.

Module interfaces SHOULD remain small and intentional.

------------------------------------------------------------------------

## 30. Documentation Requirements

Each substantial module SHOULD document purpose, architectural
assumptions, required inputs, important optional inputs, outputs,
security behaviour, dependencies, operational implications, and examples
where useful.

Documentation MUST NOT duplicate an ADR where the ADR already defines
the architectural decision.

Instead, module documentation SHALL reference the relevant ADR.

------------------------------------------------------------------------

## 31. Decision Flow

``` text
New Infrastructure Requirement
             │
             ▼
Is architecture already governed
by an Accepted ADR?
        │             │
       Yes            No
        │             │
        │             ▼
        │       Architectural decision
        │       required?
        │          │       │
        │         Yes      No
        │          │       │
        │          ▼       │
        │       Write ADR  │
        │          │       │
        └──────────┴───────┘
                   │
                   ▼
        Identify/Create Module
                   │
                   ▼
        Environment Composition
                   │
                   ▼
              CI Validation
                   │
                   ▼
             Terraform Plan
                   │
                   ▼
                Review
                   │
                   ▼
             Controlled Apply
                   │
                   ▼
              Verification
```

------------------------------------------------------------------------

## 32. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Terraform               Rejected                Weak environment
  workspace-only                                  isolation
  environments                                    

  One monolithic          Rejected                Excessive blast radius
  Terraform root                                  and coupling

  Copy Terraform for      Rejected                Configuration drift and
  every environment                               maintenance burden

  Tenant-specific         Rejected                Tenant does not imply
  Terraform stacks by                             physical infrastructure
  default                                         

  AWS Console as normal   Rejected                Non-reproducible and
  provisioning mechanism                          difficult to audit

  Shell scripts as        Rejected                Weak desired-state
  primary IaC                                     management

  Modules containing      Rejected                Violates infrastructure
  business logic                                  boundary

  Unpinned providers      Rejected                Uncontrolled
                                                  infrastructure changes

  Automatic Production    Rejected                Security and governance
  apply from PRs                                  risk

  Separate module for     Rejected                Excessive abstraction
  every AWS resource                              and complexity

  Premature multi-region  Rejected                Architecture not yet
  Terraform                                       justified
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 33. Consequences

### Positive

-   Consistent infrastructure across environments.
-   Reduced Terraform duplication.
-   Smaller change blast radius.
-   Explicit Production boundaries.
-   Improved reviewability.
-   Stronger security controls.
-   Easier automated testing.
-   Supports future AWS account and region expansion.
-   Prevents infrastructure from absorbing Baobab business logic.
-   Provides reusable infrastructure for ZuriBeans, Thamani and future
    estates.

### Costs

-   Requires module/interface discipline.
-   CI pipelines become more sophisticated.
-   State management requires deliberate design.
-   Cross-stack dependencies must be controlled.
-   Engineers must understand both modules and environment compositions.

These costs are accepted.

------------------------------------------------------------------------

## 34. Decision Rules

The following rules are authoritative:

> **Terraform is the authoritative IaC mechanism for Baobab AWS
> infrastructure.**

> **Reusable modules define infrastructure capabilities; environment
> compositions instantiate them.**

> **Development, Staging and Production SHALL have independent Terraform
> roots and state.**

> **Terraform workspaces SHALL NOT be the principal
> environment-isolation mechanism.**

> **Terraform SHALL NOT become a tenant-management or Baobab
> business-logic engine.**

> **Infrastructure modules SHALL use secure defaults and fail closed
> where security is concerned.**

> **Untrusted pull requests SHALL NOT apply Production infrastructure.**

> **Persistent manual AWS changes SHALL be reconciled into Terraform.**

> **Terraform drift is an operational defect unless explicitly
> authorised.**

> **Infrastructure modules SHALL remain reusable across ZuriBeans,
> Thamani and future Baobab digital estates.**

> **Multi-region capability SHALL be architecturally possible but SHALL
> NOT be implemented speculatively.**

------------------------------------------------------------------------

## 35. Implementation Implications

Implementation following this ADR SHALL establish, at minimum:

``` text
terraform/
├── bootstrap/
├── modules/
└── environments/
    ├── development/
    ├── staging/
    └── production/
```

Before Production provisioning begins, the repository SHALL also
establish:

-   Terraform version policy;
-   AWS provider policy;
-   provider lock management;
-   module conventions;
-   environment composition conventions;
-   common naming/tagging;
-   formatting;
-   validation;
-   linting;
-   security scanning;
-   policy validation;
-   plan review;
-   protected Production apply;
-   drift-management strategy.

Actual Production resources SHOULD NOT be provisioned merely to
demonstrate the Terraform structure.

They SHALL be introduced according to the Accepted ADR governing each
infrastructure capability.

------------------------------------------------------------------------

## 36. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0004 --- Terraform State, Locking and Bootstrap**

It shall define:

-   the remote state backend;
-   encryption;
-   state locking;
-   state segmentation;
-   bootstrap sequencing;
-   AWS account prerequisites;
-   IAM access to state;
-   GitHub Actions OIDC bootstrap;
-   state recovery;
-   state backup/versioning;
-   cross-environment restrictions;
-   break-glass procedures;
-   and the process by which `nabhold/infrastructure` establishes the
    secure foundation required to provision the rest of Baobab.
