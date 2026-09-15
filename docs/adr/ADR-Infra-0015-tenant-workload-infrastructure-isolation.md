# ADR-Infra-0015 --- Tenant and Workload Infrastructure Isolation

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0001 --- Environment Provisioner Boundary
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0003 --- Terraform Architecture and Module Strategy
    -   ADR-Infra-0005 --- Network and Trust-Zone Architecture
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0008 --- DNS, TLS, Edge and API Gateway Architecture
    -   ADR-Infra-0010 --- PostgreSQL Production Architecture
    -   ADR-Infra-0011 --- Redis Production Architecture
    -   ADR-Infra-0012 --- RabbitMQ Production Architecture
    -   ADR-Infra-0013 --- Infrastructure IAM and Workload Identity
    -   ADR-Infra-0014 --- Secrets, Keys and Certificate Management
-   **Platform Authorities:** accepted tenancy, Context,
    IsolationProfile, EngineInstance, CapabilityBinding and provisioning
    decisions in `nabhold/baobab-cp` and canonical contracts in
    `nabhold/shared`
-   **Follow-on:** ADR-Infra-0016 --- Observability and Telemetry
    Architecture

------------------------------------------------------------------------

## 1. Context

Baobab is a multi-tenant, multi-market platform of independently
operated engines and digital estates.

Its default tenant boundary is the **legal entity**, but a tenant is not
synonymous with:

-   AWS account;
-   AWS region;
-   VPC;
-   ECS cluster;
-   APISIX deployment;
-   PostgreSQL instance;
-   Redis/Valkey deployment;
-   RabbitMQ broker;
-   engine process;
-   digital estate;
-   market.

The platform must support Nabhold-owned legal entities such as ZuriBeans
and Thamani, the holding company, and future external Baobab customers
without creating a complete AWS stack for every tenant by default.

At the same time, logical sharing must never erase legal-entity,
security, regulatory, data-residency, workload or blast-radius
boundaries.

The infrastructure layer therefore requires an explicit mapping from
**logical tenancy and workload requirements** to **physical isolation
outcomes**.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use **IsolationProfile** as the authoritative policy
abstraction for mapping an approved tenant/workload context to
infrastructure isolation.

The default architecture SHALL be **shared platform infrastructure with
explicit logical isolation**.

Physical isolation SHALL increase only when justified by:

-   data classification;
-   legal/regulatory requirement;
-   contractual commitment;
-   security risk;
-   workload incompatibility;
-   availability/blast-radius requirement;
-   scale/noisy-neighbour evidence;
-   engine limitation;
-   data residency;
-   accepted customer requirement.

> **Tenant SHALL NOT imply dedicated AWS infrastructure.**

> **Shared infrastructure SHALL NOT imply shared application data,
> credentials, authorization or legal-entity operations.**

------------------------------------------------------------------------

## 3. Fundamental Distinctions

The following identities SHALL remain distinct:

``` text
Legal Entity
    │
    └── default Tenant boundary

Tenant
    │
    ├── Context
    ├── IsolationProfile
    ├── CapabilityBindings
    └── EngineInstance resolution

Digital Estate
    │
    └── user/customer-facing experience

Market
    │
    └── commercial/regulatory operating context

AWS Region
    │
    └── physical cloud placement
```

Therefore:

``` text
Tenant ≠ Legal Entity ≠ Digital Estate ≠ Market ≠ AWS Region
```

The legal entity is the default tenant boundary, but the concepts remain
separately modelled.

------------------------------------------------------------------------

## 4. Platform Resolution

Infrastructure SHALL consume approved platform resolution rather than
independently infer tenancy.

Conceptually:

``` text
Request / Provisioning Intent
          │
          ▼
        Context
          │
          ▼
   CapabilityBinding
          │
          ▼
    EngineInstance
          │
          ▼
   IsolationProfile
          │
          ▼
Infrastructure Outcome
```

`nabhold/infrastructure` SHALL NOT become a second tenant registry.

------------------------------------------------------------------------

## 5. Isolation Dimensions

Isolation SHALL be evaluated across multiple dimensions.

  Dimension    Examples
  ------------ ---------------------------------------------------------
  Identity     IAM roles, Keycloak clients/scopes
  Compute      shared cluster, separate ECS service, dedicated compute
  Network      shared VPC, SG separation, dedicated VPC
  Database     rows, schema, database, instance
  Cache        namespace/ACL, deployment
  Messaging    permissions/vhost, broker
  Secrets      workload/tenant secret scope
  Encryption   shared or dedicated KMS key
  Gateway      shared APISIX, dedicated gateway
  Storage      prefix/bucket/account
  Region       shared region, dedicated regional placement
  Account      shared environment account, dedicated AWS account

Isolation SHALL not be represented by one boolean such as
`dedicated=true`.

------------------------------------------------------------------------

## 6. IsolationProfile Model

The canonical IsolationProfile remains a platform/control-plane concept.
Infrastructure SHALL implement its approved physical consequences.

The infrastructure architecture SHALL support at least these classes:

  -----------------------------------------------------------------------------------
  Profile                    Meaning                          Typical Physical
                                                              Outcome
  -------------------------- -------------------------------- -----------------------
  **Shared**                 Normal multi-tenant/platform     shared platform
                             sharing                          resources, logical
                                                              isolation

  **Data-Isolated**          stronger persistent-data         separate
                             boundary                         schema/database/cache
                                                              namespace/credentials
                                                              as required

  **Instance-Isolated**      dedicated engine/data runtime    dedicated
                                                              EngineInstance and
                                                              selected dedicated data
                                                              resources

  **Environment-Isolated**   dedicated infrastructure         dedicated
                             environment                      compute/network/data
                                                              plane, potentially
                                                              account/VPC

  **Region-Isolated**        jurisdiction/latency/residency   approved dedicated
                             placement                        regional deployment
  -----------------------------------------------------------------------------------

Names in canonical contracts SHALL take precedence if they differ; this
ADR defines the infrastructure semantics, not a competing schema.

------------------------------------------------------------------------

## 7. Escalation Principle

Isolation SHALL escalate deliberately:

``` text
Shared
   │
   ▼
Data-Isolated
   │
   ▼
Instance-Isolated
   │
   ▼
Environment-Isolated
   │
   ▼
Region-Isolated
```

A higher level SHALL be selected only when the lower level cannot
satisfy the accepted requirement.

Cost alone SHALL not weaken a mandatory security or regulatory boundary.

------------------------------------------------------------------------

## 8. Default Shared Profile

The default Baobab production topology MAY host multiple legal entities
and digital estates on shared platform infrastructure.

``` text
Production Account / Region
          │
          ├── Shared Edge / APISIX
          ├── Shared ECS Platform
          ├── Shared Managed Data Infrastructure
          └── Independent Workloads
                ├── ZuriBeans
                ├── Thamani
                └── Future Estate
```

Sharing is permitted only with enforced identity, application, data and
secret boundaries.

------------------------------------------------------------------------

## 9. Legal-Entity Independence

ZuriBeans and Thamani are independent legal entities.

Common ownership by Nabhold SHALL NOT permit:

-   shared business records by default;
-   shared runtime credentials;
-   implicit cross-tenant database access;
-   implicit event consumption;
-   shared authorization merely because both are subsidiaries;
-   automatic cross-estate administrative access.

``` text
Nabhold Parent
   ├── ZuriBeans Tenant
   └── Thamani Tenant

ZuriBeans Data  X  Thamani Data
       unless explicit authorised business integration
```

------------------------------------------------------------------------

## 10. Digital Estate Boundary

A digital estate is not itself the infrastructure isolation unit.

A digital estate SHALL resolve through its tenant/context/capability
relationships.

ZuriBeans may consume Trade, IAM, ERP, CMS, Pulse and Control Plane
capabilities without receiving ownership of the underlying platform
infrastructure.

``` text
ZuriBeans Digital Estate
        │
        ▼
Capability Resolution
        │
        ├── Trade EngineInstance
        ├── IAM EngineInstance
        ├── ERP EngineInstance
        └── other approved capabilities
```

------------------------------------------------------------------------

## 11. Compute Isolation

The default compute boundary SHALL be:

``` text
Shared ECS Environment
       │
       ├── independent ECS service
       ├── independent task definition
       ├── independent task role
       ├── independent security group
       └── independent scaling/deployment
```

Unrelated workloads SHALL NOT be placed in one ECS task merely because
they share a tenant or platform.

ECS cluster SHALL remain a scheduling boundary, not a tenant-security
boundary.

------------------------------------------------------------------------

## 12. Dedicated Compute

Dedicated compute MAY be required where:

-   workload resource behaviour creates unacceptable contention;
-   licensing requires it;
-   security requirements demand stronger runtime separation;
-   customer contract requires it;
-   engine compatibility requires a different compute model;
-   failure blast radius must be isolated.

Dedicated compute SHALL not automatically imply dedicated
VPC/account/database unless the IsolationProfile requires those
dimensions too.

------------------------------------------------------------------------

## 13. Network Isolation

Default:

``` text
Shared Environment VPC
       │
       ├── Ingress Zone
       ├── Application Zone
       ├── Data Zone
       └── Management Zone
```

Workload isolation SHALL primarily use:

-   security groups;
-   private subnets;
-   explicit ingress/egress;
-   workload identity;
-   application authorization.

A VPC per tenant is prohibited as the default.

------------------------------------------------------------------------

## 14. Dedicated Network

A dedicated VPC or equivalent network boundary MAY be selected for:

-   regulatory segmentation;
-   contractual isolation;
-   high-risk workloads;
-   dedicated environment;
-   materially different connectivity;
-   regional deployment;
-   accepted customer requirement.

Network isolation SHALL not substitute for application authentication or
tenant authorization.

------------------------------------------------------------------------

## 15. PostgreSQL Isolation

PostgreSQL isolation MAY occur at several levels:

``` text
RDS
 ├── shared database / tenant-aware rows
 ├── separate schema
 ├── separate logical database
 └── separate RDS deployment
```

Selection SHALL follow the owning engine's architecture and
IsolationProfile.

A database per tenant SHALL NOT be the universal default.

A service SHALL never gain cross-service database access merely because
the physical RDS deployment is shared.

------------------------------------------------------------------------

## 16. Data Isolation Rules

Where multiple tenants share tables/data structures:

-   tenant/legal-entity context SHALL be explicit;
-   all access paths SHALL enforce it;
-   uniqueness constraints SHOULD include tenant context where
    semantically required;
-   integration tests SHALL prove cross-tenant denial;
-   database defence-in-depth such as RLS MAY be used where compatible.

Where an engine cannot safely provide required logical isolation, the
profile SHALL escalate to a stronger physical boundary.

------------------------------------------------------------------------

## 17. ERP Isolation

ERP isolation SHALL respect iDempiere's accepted architecture and Baobab
ERP ADRs.

Infrastructure SHALL NOT force a generic PostgreSQL tenancy pattern onto
iDempiere if the engine's supported organization/client/data model
requires a different mapping.

Where stronger isolation is required, dedicated ERP EngineInstances
and/or database resources MAY be provisioned.

------------------------------------------------------------------------

## 18. Trade Isolation

Baobab Trade SHALL preserve ZuriBeans B2B and Thamani B2C as independent
legal-entity operations.

Shared Medusa/Trade infrastructure is permitted only where the accepted
Trade architecture can prove required tenant isolation.

If engine/module behaviour cannot provide that assurance for a
capability, that capability SHALL use a stronger EngineInstance/data
isolation profile.

------------------------------------------------------------------------

## 19. IAM Isolation

Application IAM isolation belongs to `baobab-iam`.

Infrastructure SHALL provide independent runtime identity, secrets and
data boundaries required by the accepted IAM architecture.

AWS IAM role possession SHALL not define Baobab tenant membership.

------------------------------------------------------------------------

## 20. Redis/Valkey Isolation

Default cache isolation MAY use:

-   service ownership;
-   ACL/user separation;
-   tenant-aware key namespaces;
-   application authorization.

Redis logical database numbers SHALL NOT be treated as strong tenant
isolation.

Dedicated ElastiCache deployments MAY be selected by stronger
IsolationProfiles.

------------------------------------------------------------------------

## 21. RabbitMQ Isolation

Default broker sharing MAY use:

-   workload-specific users;
-   exchange/queue permissions;
-   virtual hosts where useful;
-   canonical tenant/legal-entity context.

Virtual host alone SHALL NOT be treated as the complete tenant-security
model.

Broker per tenant SHALL not be the default.

------------------------------------------------------------------------

## 22. APISIX Isolation

A shared APISIX traffic plane MAY serve multiple digital estates and
tenants.

Isolation SHALL be enforced through:

-   hostname/path ownership;
-   authenticated principal;
-   capability authorization;
-   tenant/context validation;
-   upstream ownership;
-   route governance.

Hostname alone SHALL NOT prove tenant authorization.

Dedicated APISIX deployments require an accepted isolation need.

------------------------------------------------------------------------

## 23. Secrets Isolation

Secrets SHALL follow ADR-Infra-0014.

Each workload receives only required secrets.

Tenant-specific integration secrets SHALL be scoped to that
tenant/integration.

ZuriBeans SHALL NOT read Thamani credentials and vice versa.

Shared infrastructure SHALL not imply shared secrets.

------------------------------------------------------------------------

## 24. KMS Isolation

Dedicated KMS keys MAY be used when required by:

-   data classification;
-   customer contract;
-   regulatory boundary;
-   blast-radius reduction;
-   independent key lifecycle.

A KMS key per tenant SHALL NOT be the default.

Key isolation SHALL follow actual cryptographic ownership requirements.

------------------------------------------------------------------------

## 25. Object Storage Isolation

Object storage MAY isolate data through:

``` text
shared bucket + tenant/service prefix
separate bucket
separate account
```

The choice SHALL consider IAM policy, data classification, lifecycle,
audit, residency and blast radius.

Prefix isolation SHALL be backed by IAM/resource policies; naming
convention alone is insufficient.

------------------------------------------------------------------------

## 26. Messaging and Event Context

Canonical events that are tenant/legal-entity scoped SHALL carry
explicit context according to `nabhold/shared` contracts.

``` text
Event
 ├── event identity
 ├── producer
 ├── tenant/legal-entity context
 ├── correlation
 └── domain payload
```

Infrastructure routing SHALL not silently strip or invent tenant
context.

------------------------------------------------------------------------

## 27. Noisy-Neighbour Controls

Shared infrastructure SHALL include controls against one workload
degrading others.

Controls MAY include:

-   ECS CPU/memory reservations and limits;
-   independent autoscaling;
-   database connection budgets;
-   API rate limits;
-   RabbitMQ queue/backlog limits;
-   cache memory policy;
-   workload quotas;
-   alarms.

Repeated contention is a valid trigger to escalate isolation.

------------------------------------------------------------------------

## 28. Availability and Blast Radius

Isolation decisions SHALL consider failure propagation.

Example:

``` text
Shared Component Failure
       │
       ├── affects Tenant A
       ├── affects Tenant B
       └── affects Tenant C
```

If the shared failure domain violates accepted SLOs or contractual
obligations, stronger instance/environment isolation SHALL be
considered.

High availability and tenant isolation are related but distinct
concerns.

------------------------------------------------------------------------

## 29. Data Residency

Market SHALL NOT automatically determine region.

When a tenant requires data placement:

``` text
Tenant / Workload
      │
      ▼
Residency Requirement
      │
      ▼
IsolationProfile
      │
      ▼
Approved Region
```

Region-Isolated placement SHALL be based on law, contract,
classification, latency, availability and recovery requirements.

------------------------------------------------------------------------

## 30. Dedicated Environment Criteria

A dedicated environment SHOULD be considered when one or more of the
following cannot be satisfied safely in shared infrastructure:

-   mandatory regulatory isolation;
-   contractual dedicated-environment commitment;
-   high-impact security classification;
-   incompatible networking;
-   incompatible maintenance lifecycle;
-   extreme workload scale;
-   unacceptable shared blast radius;
-   customer-controlled encryption/networking requirement;
-   residency requirement;
-   engine limitation.

Dedicated environment is an escalation, not the starting point.

------------------------------------------------------------------------

## 31. Dedicated AWS Account

A tenant-specific AWS account MAY be used only where environment
isolation still does not provide sufficient governance or where
contract/regulation explicitly requires account-level separation.

``` text
Default:
Production Account
   └── multiple isolated workloads

Exception:
Dedicated Customer Account
   └── approved isolated environment
```

Account-per-tenant SaaS architecture is rejected as the default.

------------------------------------------------------------------------

## 32. EngineInstance

`EngineInstance` SHALL represent the resolved deployable/operational
instance of an engine capability.

Multiple tenants MAY resolve to a shared EngineInstance where policy
permits.

A tenant MAY resolve to a dedicated EngineInstance where its
IsolationProfile requires it.

``` text
Tenant A ─┐
Tenant B ─┼──► Shared Trade EngineInstance

Tenant C ─────► Dedicated Trade EngineInstance
```

Infrastructure SHALL provision physical resources from the resolved
desired state rather than assume one instance per tenant.

------------------------------------------------------------------------

## 33. CapabilityBinding

A `CapabilityBinding` determines which approved capability
implementation/instance is available in context.

Infrastructure SHALL NOT infer that every tenant receives every engine.

``` text
Context
   │
   ▼
CapabilityBinding
   │
   ├── IAM
   ├── Trade
   └── ERP
```

Provisioning SHALL be capability-driven.

------------------------------------------------------------------------

## 34. Tenant Onboarding

Tenant onboarding SHALL separate logical provisioning from physical
provisioning.

``` text
Tenant Onboarding
      │
      ▼
Create/Approve Context
      │
      ▼
Resolve Capabilities
      │
      ▼
Resolve IsolationProfile
      │
      ▼
Reuse Existing Infrastructure?
      │
   ┌──┴───┐
  Yes     No
   │       │
   ▼       ▼
Bind     Provision Approved
        Physical Resources
```

Most tenant onboarding SHOULD reuse approved shared infrastructure.

------------------------------------------------------------------------

## 35. Provisioning Ownership

`baobab-cp` owns approved tenant-level desired state and resolution.

`nabhold/infrastructure` owns declarative physical environment
provisioning.

Therefore:

``` text
Control Plane
  "what capability/isolation is required"
             │
             ▼
Infrastructure
  "how approved physical resources are provisioned"
```

The Control Plane SHALL NOT own Terraform, VPCs or cloud server
lifecycle.

Infrastructure SHALL NOT own tenant business rules.

------------------------------------------------------------------------

## 36. Provisioning Interface

Any future automated bridge between Control Plane and infrastructure
SHALL use a narrowly scoped, auditable provisioning interface.

The Control Plane SHALL NOT receive unrestricted Terraform-state or
AWS-administrator access.

Provisioner identities SHALL follow ADR-Infra-0013.

------------------------------------------------------------------------

## 37. IsolationProfile Change

Changing a tenant/workload IsolationProfile is a controlled migration,
not a simple metadata edit.

Example:

``` text
Shared
  │
  ▼
Instance-Isolated
  │
  ├── provision target
  ├── migrate data/config
  ├── verify
  ├── switch bindings/routes
  └── retire old allocation
```

The platform SHALL preserve rollback/recovery and avoid silent
destructive moves.

------------------------------------------------------------------------

## 38. Downgrading Isolation

Moving from stronger to weaker isolation SHALL require explicit
approval.

Before consolidation, the platform SHALL assess:

-   data separation;
-   credentials;
-   encryption;
-   routing;
-   retention;
-   backups;
-   audit;
-   contractual constraints.

Cost savings alone SHALL not silently override an accepted isolation
requirement.

------------------------------------------------------------------------

## 39. Isolation Metadata

Infrastructure resources SHOULD be tagged or otherwise attributable to:

-   environment;
-   service;
-   EngineInstance;
-   IsolationProfile where useful;
-   tenant only where the resource is specifically
    attributable/dedicated.

Shared resources SHALL not be falsely tagged as belonging exclusively to
one tenant.

------------------------------------------------------------------------

## 40. Cost Attribution

Shared infrastructure costs SHOULD be attributable through workload
metrics, tags and allocation models where practical.

Cost attribution SHALL NOT force unnecessary physical isolation.

A dedicated resource may improve accounting but is not justified solely
because chargeback is easier.

------------------------------------------------------------------------

## 41. Security Testing

Production isolation testing SHALL include negative tests.

Examples:

``` text
ZuriBeans principal → Thamani resource = DENY
Thamani principal   → ZuriBeans secret = DENY
Tenant A API context → Tenant B record = DENY
Unbound capability   → Engine access = DENY
```

Successful happy-path tests alone do not prove tenant isolation.

------------------------------------------------------------------------

## 42. Cross-Tenant Administration

Platform administrators MAY require operational visibility across
tenants, but this SHALL be role-controlled and auditable.

Business users of one tenant SHALL NOT gain cross-tenant access through
platform administration roles.

Support impersonation, if ever introduced, requires separate IAM
governance and audit.

------------------------------------------------------------------------

## 43. Explicit Inter-Entity Business Relationships

If ZuriBeans sells to Thamani, or future Baobab tenants transact with
each other, the relationship SHALL be represented as an explicit
business interaction.

``` text
ZuriBeans Tenant
      │
      │ approved order/invoice/trade contract
      ▼
Thamani Tenant
```

It SHALL NOT be implemented by bypassing isolation and directly sharing
internal tables or credentials.

------------------------------------------------------------------------

## 44. Shared Engine Does Not Mean Shared Domain Record

A shared Trade EngineInstance MAY serve multiple tenants while each
tenant retains independent:

-   customers;
-   products where applicable;
-   prices;
-   orders;
-   inventory;
-   payments;
-   tax configuration;
-   integrations.

The engine's accepted domain model determines exact implementation.

------------------------------------------------------------------------

## 45. Infrastructure Drift

Manual creation of dedicated tenant resources outside the approved
IsolationProfile/provisioning process is drift.

Persistent exceptions SHALL be reconciled into declarative
infrastructure and platform metadata.

------------------------------------------------------------------------

## 46. Deprovisioning

Tenant deprovisioning SHALL distinguish:

``` text
Logical Deprovisioning
    ├── disable bindings/access
    ├── revoke identities/secrets
    └── preserve required records

Physical Deprovisioning
    ├── only dedicated resources
    ├── retention/backup checks
    └── controlled destruction
```

Removing one tenant SHALL NOT destroy shared infrastructure used by
others.

------------------------------------------------------------------------

## 47. Data Retention on Exit

Tenant exit SHALL not imply immediate physical deletion of all records.

Retention/deletion SHALL follow:

-   legal requirements;
-   contract;
-   data classification;
-   backup policy;
-   audit requirements;
-   owning-domain rules.

Shared backup media SHALL be handled through the accepted retention
architecture rather than ad hoc tenant deletion.

------------------------------------------------------------------------

## 48. ZuriBeans Initial Profile

ZuriBeans SHALL be the first Production validation of this isolation
architecture.

Its initial deployment SHOULD use shared Baobab platform infrastructure
where accepted engine ADRs permit, while preserving independent:

-   tenant/legal-entity context;
-   IAM/application authorization;
-   workload roles;
-   secrets;
-   business data;
-   capability bindings;
-   digital-estate routing;
-   operational telemetry.

ZuriBeans SHALL not receive a dedicated AWS account/VPC/broker/cache
merely because it is the first estate.

------------------------------------------------------------------------

## 49. Thamani

Thamani SHALL be onboarded as a separate legal-entity tenant.

ZuriBeans implementation choices SHALL NOT become implicit Thamani
defaults where their business models differ.

In particular:

``` text
ZuriBeans = B2B
Thamani   = B2C
```

Shared Baobab capabilities MAY be reused, but tenant data, policies and
operational identities remain independent.

------------------------------------------------------------------------

## 50. Future External Customers

The same model SHALL support external Baobab customers.

A customer may begin on Shared/Data-Isolated infrastructure and later
migrate to stronger isolation without changing the fundamental platform
contract.

This is essential for Baobab's future SaaS model.

------------------------------------------------------------------------

## 51. Production Verification

Before go-live, verification SHALL demonstrate:

-   tenant/context resolution is explicit;
-   IsolationProfile resolves deterministically;
-   shared resources are not treated as tenant-owned;
-   ZuriBeans cannot access Thamani resources;
-   workload roles and secrets are isolated;
-   database isolation tests pass;
-   cache namespace/ACL isolation passes;
-   RabbitMQ permissions/event context isolation passes;
-   APISIX route/context isolation passes;
-   unbound capabilities are denied;
-   deprovisioning one tenant does not destroy shared resources;
-   stronger isolation can be provisioned without redefining tenant
    identity;
-   infrastructure resources correspond to approved platform resolution.

------------------------------------------------------------------------

## 52. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  AWS account per tenant  Rejected                Excessive
  by default                                      cost/complexity

  VPC per tenant by       Rejected                Tenant does not imply
  default                                         network

  ECS cluster per tenant  Rejected                Cluster is scheduling
  by default                                      boundary

  Database instance per   Rejected                Unnecessary physical
  tenant by default                               sprawl

  Redis deployment per    Rejected                Logical isolation
  tenant by default                               normally sufficient

  RabbitMQ broker per     Rejected                Excessive operational
  tenant by default                               cost

  APISIX deployment per   Rejected                Shared gateway can
  tenant by default                               isolate routes/context

  Tenant inferred from    Rejected                Not sufficient
  hostname/IP                                     authorization

  Shared credentials      Rejected                Breaks independence
  across legal entities                           

  One boolean isolation   Rejected                Isolation is
  flag                                            multidimensional

  Infrastructure as       Rejected                Control Plane owns
  tenant registry                                 logical desired state

  Control Plane directly  Rejected                Violates provisioner
  owning Terraform                                boundary

  Cost-driven downgrade   Rejected                Can violate
  without review                                  security/contract

  Common parent = shared  Rejected                Legal entities remain
  business data                                   independent
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 53. Consequences

### Positive

-   Prevents infrastructure-per-tenant sprawl.
-   Preserves strong legal-entity boundaries.
-   Provides a clear path from shared SaaS to dedicated regulated
    workloads.
-   Aligns physical provisioning with Control Plane resolution.
-   Keeps `nabhold/infrastructure` out of tenant business logic.
-   Supports ZuriBeans now and Thamani/future customers later.
-   Allows isolation to vary by capability rather than forcing
    whole-stack duplication.
-   Makes noisy-neighbour, security and residency escalation explicit.
-   Supports future migration between isolation levels.

### Costs

-   Isolation must be tested across several layers.
-   Engine-specific tenancy capabilities must be understood.
-   IsolationProfile migrations require careful orchestration.
-   Shared infrastructure requires disciplined authorization and
    observability.
-   Dedicated profiles increase cost.
-   Cross-repo resolution contracts become operationally important.

These costs are accepted.

------------------------------------------------------------------------

## 54. Decision Rules

> **The legal entity SHALL remain Baobab's default tenant boundary.**

> **Tenant SHALL NOT imply AWS account, region, VPC, ECS cluster,
> database instance, cache deployment, RabbitMQ broker, APISIX
> deployment or complete infrastructure stack.**

> **IsolationProfile SHALL be the authoritative policy abstraction for
> mapping approved logical context to infrastructure isolation.**

> **Shared platform infrastructure SHALL be the default where security,
> regulation, workload compatibility and SLOs permit it.**

> **Shared infrastructure SHALL NOT imply shared data, credentials,
> authorization or business operations.**

> **Physical isolation SHALL escalate only when an accepted requirement
> justifies it.**

> **Isolation SHALL be multidimensional; one boolean isolation flag is
> insufficient.**

> **`baobab-cp` SHALL own tenant-level desired state and resolution;
> `nabhold/infrastructure` SHALL own physical provisioning.**

> **Multiple tenants MAY resolve to one EngineInstance, and one tenant
> MAY resolve to dedicated EngineInstances where its IsolationProfile
> requires it.**

> **ZuriBeans and Thamani SHALL remain independent legal-entity tenants
> regardless of common ownership by Nabhold.**

> **Cross-tenant business relationships SHALL use explicit
> contracts/APIs/events rather than bypassing isolation.**

> **Deprovisioning a tenant SHALL NOT destroy shared infrastructure used
> by other tenants.**

------------------------------------------------------------------------

## 55. Implementation Implications

Infrastructure SHALL be able to express:

``` text
Isolation
│
├── Shared
│   ├── shared VPC
│   ├── shared ECS cluster
│   ├── independent services/roles/SGs
│   └── logical data isolation
│
├── Data-Isolated
│   ├── separate schema/database
│   ├── scoped credentials
│   └── stronger cache/storage boundaries
│
├── Instance-Isolated
│   ├── dedicated EngineInstance
│   ├── dedicated data resources where required
│   └── independent scaling/lifecycle
│
├── Environment-Isolated
│   ├── dedicated network/compute/data plane
│   └── optional dedicated AWS account
│
└── Region-Isolated
    └── approved regional placement
```

Terraform modules SHALL accept approved isolation inputs without
embedding tenant business rules.

Implementation SHALL consult accepted ADRs in `baobab-cp`, `shared`, and
each affected engine repository before mapping an IsolationProfile to
physical resources.

------------------------------------------------------------------------

## 56. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0016 --- Observability and Telemetry Architecture**

It shall define:

-   OpenTelemetry;
-   metrics;
-   logs;
-   traces;
-   correlation;
-   environment/service/tenant telemetry dimensions;
-   collector topology;
-   AWS observability backends;
-   dashboards;
-   retention;
-   sensitive-data controls;
-   cross-service trace propagation;
-   infrastructure telemetry;
-   engine telemetry;
-   digital-estate telemetry;
-   and how observability remains useful across shared and dedicated
    IsolationProfiles.
