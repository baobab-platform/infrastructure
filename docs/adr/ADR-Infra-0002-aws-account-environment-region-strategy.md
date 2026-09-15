# ADR-Infra-0002 --- AWS Account, Environment and Region Strategy

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:** ADR-Infra-0001 --- Environment Provisioner Boundary

------------------------------------------------------------------------

## 1. Context

Baobab is a multi-tenant, multi-digital-estate platform supporting
independent legal entities and potentially external customers.

ZuriBeans is the first production digital estate, but infrastructure
decisions MUST support future estates such as Thamani without coupling
infrastructure topology to a particular tenant.

The platform requires clear separation between:

-   development, staging, and production;
-   AWS infrastructure and Baobab logical tenancy;
-   markets and deployment regions;
-   human, CI/CD, and workload access;
-   current South African deployment and future regional expansion.

A business operating in a country does **not** automatically require
infrastructure to be deployed in that country.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL adopt an **environment-isolated AWS architecture**,
initially hosted in **AWS Africa (Cape Town), `af-south-1`**.

Production infrastructure SHALL be logically and operationally isolated
from non-production infrastructure.

The target account model is:

``` text
Nabhold AWS Organization
│
├── Security / Management
│   └── Organisation-wide governance and audit
│
├── Development
│   └── af-south-1
│
├── Staging
│   └── af-south-1
│
└── Production
    └── af-south-1
        │
        ├── Baobab Platform
        ├── Shared Engines
        └── Digital Estates
            ├── ZuriBeans
            ├── Thamani
            └── Future tenants
```

**Separate AWS accounts SHOULD be used for Development, Staging, and
Production.**

Where account availability initially prevents full separation,
infrastructure MAY temporarily operate under fewer accounts, but
Terraform structure, IAM policies, state, and deployment workflows MUST
preserve the same environment boundaries so migration to separate
accounts does not require architectural redesign.

------------------------------------------------------------------------

## 3. Environment Model

  -------------------------------------------------------------------------------------------
  Environment   Purpose                         Production Data    Public Access Deployment
  ------------- ------------------------- --------------------- ---------------- ------------
  Local         Developer                                    No    Loopback only Docker
                workstation/Codespaces                                           Compose

  Development   Integration/development                      No       Controlled Terraform

  Staging       Production-equivalent       Sanitised/synthetic       Controlled Terraform
                validation                                                       

  Production    Live Baobab workloads                       Yes Through approved Terraform
                                                                         ingress 
  -------------------------------------------------------------------------------------------

Production data MUST NOT be copied into Development.

Production data used outside Production requires an explicitly approved
sanitisation/anonymisation process.

------------------------------------------------------------------------

## 4. Environment Isolation

``` text
                    GitHub Actions
                         │
                    OIDC Federation
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
        DEV Role     STAGING Role    PROD Role
            │            │            │
            ▼            ▼            ▼
       ┌────────┐    ┌────────┐    ┌────────┐
       │  DEV   │    │STAGING │    │  PROD  │
       │Account │    │Account │    │Account │
       └────────┘    └────────┘    └────────┘
            X────────────X────────────X
                No implicit trust
```

Environment credentials SHALL NOT be shared.

Development identities SHALL NOT implicitly assume Staging or Production
roles.

Production deployment SHALL require a protected GitHub environment and
explicit approval according to the infrastructure CI/CD ADR.

------------------------------------------------------------------------

## 5. Region Strategy

### 5.1 Initial Region

`af-south-1` --- AWS Africa (Cape Town) SHALL be the initial production
region.

Development and Staging SHOULD also use `af-south-1` where this improves
production parity.

### 5.2 Markets Are Not Regions

The following relationship is explicitly rejected:

``` text
Uganda market ──────────X──────────> Uganda/East Africa deployment required

South Africa market ────X──────────> Separate South African tenant stack required
```

Instead:

``` text
Business Market
      │
      ▼
Residency + Regulation + Latency
+ Availability + Cost + Risk
      │
      ▼
Infrastructure Placement Decision
```

`Market`, `Tenant`, `LegalEntity`, `DigitalEstate`, and AWS `Region` are
therefore **different architectural concepts**.

------------------------------------------------------------------------

## 6. Multi-Region Expansion

A second region SHALL NOT be introduced merely because Baobab enters
another market.

Expansion requires an explicit architectural assessment covering:

  Criterion          Required Assessment
  ------------------ ----------------------------------------
  Data residency     Legal/regulatory requirement
  Latency            User and system performance
  Availability       Regional failure requirements
  DR                 RPO/RTO requirements
  Data sovereignty   Permitted storage/processing locations
  Integration        Location of external systems
  Cost               Replication and operational overhead
  Complexity         Distributed-system consequences

Any active-active, active-passive, or regional data-placement strategy
requires a subsequent ADR.

------------------------------------------------------------------------

## 7. Tenant Versus Infrastructure Boundary

A Baobab tenant SHALL NOT automatically receive:

-   an AWS account;
-   VPC;
-   database server;
-   RabbitMQ cluster;
-   Redis deployment;
-   APISIX instance;
-   compute cluster; or
-   AWS region.

Default topology:

``` text
AWS Production Account
        │
        └── af-south-1
             │
             ├── Shared Platform Infrastructure
             │
             ├── Baobab Control Plane
             │
             ├── Shared/isolated EngineInstances
             │
             └── Digital Estates
                  │
                  ├── ZuriBeans
                  ├── Thamani
                  └── Future Tenant
```

Physical isolation SHALL instead be determined by the tenant/workload
**IsolationProfile**, risk, regulatory requirements, and capability
requirements.

The detailed mapping is governed by ADR-Infra-0015.

------------------------------------------------------------------------

## 8. Availability Zones

Production architecture SHOULD use multiple Availability Zones wherever
the selected AWS service and workload justify high availability.

``` text
                    af-south-1
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
        AZ-A           AZ-B          AZ-C
          │             │             │
      workloads     workloads     optional/
      + data        + data        service-specific
          └─────────────┬─────────────┘
                        │
                  Baobab Services
```

Multi-AZ does **not** constitute disaster recovery against complete
regional failure.

Regional disaster recovery is governed separately.

------------------------------------------------------------------------

## 9. Infrastructure Naming

Resources MUST expose environment and workload ownership without
embedding mutable business assumptions.

Recommended pattern:

``` text
baobab-{environment}-{service}-{resource}
```

Examples:

``` text
baobab-prod-cp-db
baobab-prod-apisix
baobab-staging-rabbitmq
baobab-dev-redis
```

Tenant identifiers MAY be incorporated where the resource is genuinely
tenant-dedicated:

``` text
baobab-prod-zuribeans-{resource}
```

They MUST NOT be added merely because a workload processes tenant data.

------------------------------------------------------------------------

## 10. Mandatory Resource Metadata

Terraform-managed AWS resources that support tagging MUST carry at
least:

  Tag                    Example
  ---------------------- --------------------------
  `Platform`             `baobab`
  `Environment`          `production`
  `ManagedBy`            `terraform`
  `Repository`           `nabhold/infrastructure`
  `Service`              `baobab-cp`
  `Owner`                `nabhold`
  `DataClassification`   `confidential`
  `CostCentre`           appropriate value

Tenant/DigitalEstate tags SHALL be added only when resources are
specifically attributable to them.

Detailed cost governance belongs to ADR-Infra-0024.

------------------------------------------------------------------------

## 11. Terraform Environment Boundary

Terraform SHALL represent environments explicitly.

``` text
terraform/
├── bootstrap/
├── modules/
│   └── ...
└── environments/
    ├── development/
    ├── staging/
    └── production/
```

Environment separation SHALL NOT depend solely on Terraform workspaces.

Each environment SHALL have independently controlled:

-   state;
-   AWS identity;
-   configuration;
-   secrets;
-   deployment permissions;
-   approval policy.

The detailed Terraform architecture is defined by ADR-Infra-0003.

------------------------------------------------------------------------

## 12. Deployment Promotion

Infrastructure and applications SHALL progress toward Production through
controlled promotion:

``` text
       Change
         │
         ▼
   Pull Request
         │
   validate / plan
         │
         ▼
    Development
         │
         ▼
      Staging
         │
   verification
         │
   approval gate
         │
         ▼
    Production
```

A pull request originating from an untrusted context MUST NOT possess
Production apply permissions.

Production changes MUST be auditable.

------------------------------------------------------------------------

## 13. Security Principles

The account/environment architecture SHALL enforce:

1.  least privilege;
2.  no shared human credentials;
3.  workload identity rather than static credentials;
4.  GitHub Actions → AWS authentication through OIDC;
5.  separate Production deployment roles;
6.  encrypted infrastructure state;
7.  protected Production environments;
8.  auditable privileged operations;
9.  controlled break-glass access;
10. default separation between environments.

Long-lived AWS access keys in GitHub Secrets SHOULD NOT be used for
normal deployment.

------------------------------------------------------------------------

## 14. ZuriBeans Go-Live Implication

ZuriBeans SHALL be the **first production validation workload**, not the
architectural owner of the infrastructure.

Therefore:

``` text
              Baobab Infrastructure
                       │
              production capability
                       │
                       ▼
                ZuriBeans Go-Live
                       │
                       ▼
              validates architecture
                       │
                       ▼
        ┌──────────────┴──────────────┐
        ▼                             ▼
     Thamani                    Future Estates
```

Infrastructure MUST NOT be designed in a manner that makes ZuriBeans
assumptions platform-wide requirements.

------------------------------------------------------------------------

## 15. Consequences

### 15.1 Positive

-   Strong Production/non-production isolation.
-   Clear path to multiple AWS accounts.
-   ZuriBeans does not become hard-coded into platform infrastructure.
-   Market expansion remains independent from cloud-region expansion.
-   Terraform can evolve toward multi-region deployment without
    restructuring the repository.
-   IAM blast radius is materially reduced.
-   Staging can serve as a meaningful Production gate.

### 15.2 Costs

-   Multiple accounts increase governance and deployment complexity.
-   Cross-account IAM must be managed carefully.
-   Environment-specific Terraform state is required.
-   Production parity increases non-production infrastructure cost.
-   Future multi-region operation will require explicit data and
    failover architecture.

These costs are accepted.

------------------------------------------------------------------------

## 16. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Single undifferentiated Rejected                Excessive blast radius
  AWS account                                     

  Production via Docker   Rejected                Local Compose is
  Compose                                         development
                                                  infrastructure

  AWS account per tenant  Rejected                Confuses logical
  by default                                      tenancy with physical
                                                  infrastructure

  VPC per tenant by       Rejected                Cost and operational
  default                                         complexity

  Region per business     Rejected                Market ≠ infrastructure
  market                                          placement

  Terraform               Rejected                Insufficient
  workspace-only                                  environment boundary
  isolation                                       

  Kubernetes/EKS by       Rejected                No demonstrated
  default                                         requirement; remains
                                                  deferred

  Long-lived AWS CI       Rejected                OIDC/workload identity
  credentials                                     preferred
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 17. Decision Rules

The following invariants are authoritative for subsequent
implementation:

> **Environment ≠ Tenant ≠ Legal Entity ≠ Digital Estate ≠ Market ≠ AWS
> Region.**

> **Production SHALL be isolated from non-production.**

> **`af-south-1` is Baobab's initial production region.**

> **A new market does not automatically create a new region.**

> **A new tenant does not automatically create a new AWS infrastructure
> stack.**

> **Production infrastructure SHALL be provisioned declaratively through
> `nabhold/infrastructure`.**

> **Terraform and deployment architecture MUST preserve the ability to
> separate Development, Staging, and Production AWS accounts.**

------------------------------------------------------------------------

## 18. Follow-on Decision

The next dependency is:

**ADR-Infra-0003 --- Terraform Architecture and Module Strategy**

It shall turn the boundaries established by this ADR into the actual
Infrastructure-as-Code design, including:

-   Terraform module philosophy;
-   environment composition;
-   provider and version pinning;
-   dependency management;
-   state boundaries;
-   inputs and outputs;
-   validation and testing;
-   module reuse;
-   environment-specific configuration;
-   and rules preventing Terraform from becoming another source of
    Baobab business logic.
