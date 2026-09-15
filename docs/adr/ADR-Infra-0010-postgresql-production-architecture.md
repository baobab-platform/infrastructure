# ADR-Infra-0010 --- PostgreSQL Production Architecture

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0005 --- Network and Trust-Zone Architecture
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0009 --- APISIX and etcd Production Architecture
-   **Follow-on:** ADR-Infra-0011 --- Redis Production Architecture

------------------------------------------------------------------------

## 1. Context

PostgreSQL is Baobab's principal relational database technology and
supports several independently owned platform workloads.

Production must support:

-   Baobab Control Plane;
-   Medusa-based Baobab Trade;
-   Payload-based Baobab CMS where PostgreSQL is selected;
-   Keycloak/Baobab IAM;
-   other approved PostgreSQL-backed services;
-   ZuriBeans and future digital estates through their owning services.

The database architecture must preserve legal-entity and tenant
isolation without turning every tenant into a physical AWS database
deployment.

It must also provide high availability, encryption, backup,
point-in-time recovery, controlled credentials, observability, safe
schema evolution and predictable operational ownership.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use **Amazon RDS for PostgreSQL** as the default managed
PostgreSQL production service.

The initial baseline SHALL be **PostgreSQL 17**, subject to controlled
minor-version maintenance and later major-version ADR/change governance.

Production SHALL use an RDS **Multi-AZ architecture** appropriate to the
workload's availability requirements.

Aurora PostgreSQL SHALL NOT be the default initial database platform.

It MAY be reconsidered where measured scale, availability, read topology
or operational requirements demonstrate a material advantage.

------------------------------------------------------------------------

## 3. Why RDS PostgreSQL

``` text
Baobab Workloads
      │
      ▼
Private DB Endpoint
      │
      ▼
Amazon RDS PostgreSQL
      │
      ├── managed backups
      ├── Multi-AZ
      ├── PITR
      ├── monitoring
      ├── encryption
      └── managed maintenance
```

RDS PostgreSQL provides the required PostgreSQL compatibility while
reducing the operational burden of self-managed database hosts.

Self-managed PostgreSQL on ECS/EC2 is not justified for the initial
platform.

------------------------------------------------------------------------

## 4. Regional Baseline

Production SHALL initially run in:

``` text
AWS Region: af-south-1
```

PostgreSQL 17 and RDS Multi-AZ PostgreSQL capabilities are available in
the Africa (Cape Town) region.

A new Baobab business market SHALL NOT automatically create another
PostgreSQL region.

Regional database placement follows the region/residency decisions
defined by ADR-Infra-0002.

------------------------------------------------------------------------

## 5. High-Level Topology

``` text
                 Private Application Zone
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
       baobab-cp       baobab-trade    baobab-iam
           │               │               │
           └───────────────┼───────────────┘
                           │
                     TLS connection
                           │
                           ▼
                 ┌───────────────────┐
                 │ RDS PostgreSQL 17 │
                 │   Private Only    │
                 └─────────┬─────────┘
                           │
                     Multi-AZ / backup
                           │
                           ▼
                     AWS-managed
                     durability
```

The diagram is conceptual; independent database instances/clusters MAY
be used where isolation, lifecycle or engine requirements justify them.

------------------------------------------------------------------------

## 6. Database Ownership Boundary

A database SHALL have a clearly identified owning service.

Examples:

  Database           Logical Owner
  ------------------ ----------------
  Control Plane DB   `baobab-cp`
  Trade DB           `baobab-trade`
  IAM/Keycloak DB    `baobab-iam`
  CMS DB             `baobab-cms`
  Other engine DB    Owning engine

One service SHALL NOT casually query another service's private database.

``` text
Service A ──► Service A DB

Service B ──X──► Service A DB
```

Cross-domain integration SHALL use approved APIs/events rather than
shared-table coupling.

------------------------------------------------------------------------

## 7. Database Server Sharing

Baobab MAY share an RDS deployment across compatible databases where
risk, scale and isolation requirements permit.

However:

> **Shared RDS infrastructure does not mean shared database ownership.**

Separate RDS deployments SHOULD be used where required by:

-   engine compatibility;
-   failure isolation;
-   maintenance lifecycle;
-   security;
-   regulatory requirements;
-   materially different scaling;
-   accepted IsolationProfile.

------------------------------------------------------------------------

## 8. Tenant Boundary

Tenant SHALL NOT imply RDS instance.

Default:

``` text
RDS Infrastructure
      │
      ├── service-owned database
      │      │
      │      ├── tenant-aware schemas/data
      │      └── application-enforced isolation
      │
      └── other service-owned databases
```

Physical database isolation SHALL be selected by the approved
tenant/workload `IsolationProfile`, not by tenant existence alone.

Detailed physical isolation policy is governed by ADR-Infra-0015.

------------------------------------------------------------------------

## 9. Legal-Entity Isolation

ZuriBeans and Thamani are independent legal entities and SHALL remain
logically isolated even where infrastructure is shared.

Application and data models SHALL preserve legal-entity boundaries.

Infrastructure SHALL not assume:

``` text
same parent company = same operational data
```

Database access roles, schema design, tenant identifiers and service
authorization SHALL preserve this separation.

------------------------------------------------------------------------

## 10. Network Placement

RDS SHALL run in private Data Zone subnets.

``` text
Application SG
      │
      │ TCP 5432 only where required
      ▼
PostgreSQL SG
```

Production PostgreSQL SHALL NOT:

-   receive a public IP;
-   allow `0.0.0.0/0`;
-   be reachable directly from the Internet;
-   be exposed for administrative convenience.

------------------------------------------------------------------------

## 11. Multi-AZ Availability

Production databases supporting critical services SHALL use Multi-AZ
deployment.

The selected RDS Multi-AZ model SHALL be based on workload requirements.

``` text
             Production RDS
                  │
          ┌───────┴───────┐
          ▼               ▼
       Primary          Standby/
        AZ-A            Multi-AZ
```

Where RDS Multi-AZ DB clusters are selected, their additional topology
and reader capabilities SHALL be used intentionally rather than merely
because available.

Multi-AZ availability SHALL NOT be represented as regional disaster
recovery.

------------------------------------------------------------------------

## 12. RDS Instance vs Multi-AZ DB Cluster

Both supported RDS PostgreSQL Multi-AZ models MAY be valid.

Selection SHALL consider:

-   availability objective;
-   failover behaviour;
-   read requirements;
-   cost;
-   workload characteristics;
-   connection topology;
-   operational simplicity.

The initial implementation SHOULD prefer the least complex model that
meets the workload SLO.

A more expensive topology SHALL not be selected without operational
value.

------------------------------------------------------------------------

## 13. Aurora Position

Aurora PostgreSQL is deferred as the default.

It MAY be evaluated if Baobab later requires:

-   materially higher read scale;
-   Aurora-specific availability characteristics;
-   advanced replication/topology requirements;
-   measured performance advantages;
-   operational capabilities that justify migration cost.

PostgreSQL compatibility alone is not sufficient reason to adopt Aurora.

------------------------------------------------------------------------

## 14. Encryption at Rest

Production RDS storage SHALL be encrypted using AWS KMS.

Encryption SHALL cover, as supported by RDS:

-   database storage;
-   automated backups;
-   snapshots;
-   replicas derived from encrypted databases.

KMS access SHALL follow least privilege.

Encryption SHALL be enabled from initial provisioning rather than added
as an afterthought.

------------------------------------------------------------------------

## 15. Encryption in Transit

Production application connections SHALL use TLS.

``` text
Application
     │
     │ TLS
     ▼
RDS PostgreSQL
```

TLS verification SHOULD validate the RDS endpoint and trusted CA where
supported by the application driver.

The platform SHALL not rely merely on network privacy for database
confidentiality.

------------------------------------------------------------------------

## 16. Authentication

Applications SHALL use dedicated database identities.

The RDS master/admin account SHALL NOT be used by normal application
runtime.

Supported patterns MAY include:

-   IAM database authentication;
-   database credentials stored and rotated through AWS Secrets Manager;
-   RDS Proxy authentication mechanisms where selected.

The authentication method SHALL be chosen per workload compatibility and
operational requirements.

------------------------------------------------------------------------

## 17. IAM Database Authentication

IAM database authentication SHOULD be preferred where:

-   the client/runtime supports it reliably;
-   connection-token lifecycle is operationally appropriate;
-   driver/tooling compatibility is proven.

IAM database authentication SHALL not be forced onto a workload whose
framework or connection-pool behaviour makes it operationally unsafe.

Each database user SHALL use one coherent authentication model.

------------------------------------------------------------------------

## 18. Database Credentials

Where password authentication is required:

``` text
Application Task Role
        │
        ▼
AWS Secrets Manager
        │
        ▼
DB Credential
        │
        ▼
RDS PostgreSQL
```

Credentials SHALL NOT be:

-   committed to Git;
-   embedded in images;
-   placed in plaintext task definitions;
-   shared across unrelated services;
-   exposed to digital estates that do not own the database.

Rotation SHALL be supported.

------------------------------------------------------------------------

## 19. Least Privilege

Each workload SHALL receive only the database privileges required for
its function.

Separate roles SHOULD exist where useful for:

-   application runtime;
-   migrations;
-   read-only reporting;
-   administration;
-   backup/recovery operations.

Example:

``` text
Migration Role ──► DDL + controlled migration rights
Runtime Role   ──► application DML only
Read Role      ──► approved read access
```

Application runtime roles SHOULD NOT routinely own schemas or possess
superuser-equivalent privileges.

------------------------------------------------------------------------

## 20. RDS Proxy

RDS Proxy MAY be introduced for workloads that benefit materially from:

-   connection pooling;
-   connection surge protection;
-   faster recovery of application connections during database failover;
-   IAM-based client authentication;
-   reduced database connection pressure.

``` text
ECS Tasks
   │
   ▼
RDS Proxy
   │
   ▼
PostgreSQL
```

RDS Proxy SHALL NOT be mandatory for every service.

------------------------------------------------------------------------

## 21. Proxy Compatibility

Before enabling RDS Proxy, implementation SHALL test workload behaviour
for connection pinning and session-state assumptions.

Applications that depend heavily on session state, temporary objects or
connection-specific behaviour may reduce proxy multiplexing benefits.

Proxy adoption SHALL therefore be measured, not assumed.

------------------------------------------------------------------------

## 22. Connection Pooling

Every long-running service SHALL define a database connection strategy.

Connection pools SHALL be bounded.

``` text
Task Count
    ×
Pool Size
    ≤
Safe DB Connection Budget
```

Autoscaling policies SHALL consider database connection capacity.

Scaling ECS tasks without connection limits can exhaust PostgreSQL
before CPU becomes the bottleneck.

------------------------------------------------------------------------

## 23. Connection Budget

Production capacity planning SHALL account for:

-   PostgreSQL maximum connections;
-   administrative reserve;
-   migrations;
-   monitoring;
-   background workers;
-   API services;
-   autoscaling;
-   failover conditions.

The platform SHALL avoid assigning each service an arbitrary large
connection pool.

------------------------------------------------------------------------

## 24. Database Naming

Database names SHALL identify owning service/domain rather than tenant
by default.

Conceptual examples:

``` text
baobab_cp
baobab_trade
baobab_iam
baobab_cms
```

Exact names SHALL follow repository conventions and PostgreSQL naming
constraints.

Tenant-specific databases MAY exist where the IsolationProfile requires
them.

------------------------------------------------------------------------

## 25. Schema Ownership

Schema ownership belongs to the service that owns the database contract.

Infrastructure SHALL provision database infrastructure and foundational
access but SHALL NOT define application tables.

``` text
nabhold/infrastructure
        │
        └── RDS + network + KMS + foundational access

Application Repository
        │
        └── schema migrations + domain tables
```

Terraform SHALL NOT manage normal application schema evolution.

------------------------------------------------------------------------

## 26. Migrations

Schema migrations SHALL be versioned in the owning application
repository.

Production migrations SHALL be:

-   reviewed;
-   tested against representative Staging data;
-   observable;
-   backward-compatible where rolling deployments require coexistence;
-   separated from uncontrolled application startup where risk justifies
    it.

The preferred evolution model is **expand → migrate → contract** for
breaking schema changes.

------------------------------------------------------------------------

## 27. Migration Flow

``` text
Schema Change
    │
    ▼
Application PR
    │
    ▼
Migration Tests
    │
    ▼
Development
    │
    ▼
Staging
    │
    ▼
Compatibility Verification
    │
    ▼
Production Migration
    │
    ▼
Application Deployment
    │
    ▼
Post-deploy Verification
```

Exact ordering MAY differ for backward-compatible expand/contract
releases, but SHALL be deliberate.

------------------------------------------------------------------------

## 28. Migration Locks

Long-running or table-locking migrations SHALL be identified before
Production execution.

Migration design SHOULD avoid:

-   unbounded table rewrites;
-   long exclusive locks;
-   irreversible destructive changes in the same release as dependent
    code;
-   silent migration execution by every horizontally scaled task.

Only one authorised migration execution SHOULD own a migration step
where concurrency would be unsafe.

------------------------------------------------------------------------

## 29. Backups

Production RDS SHALL enable automated backups.

Backup retention SHALL satisfy the recovery objectives defined by
ADR-Infra-0018.

Manual snapshots SHALL be taken where required for:

-   major upgrades;
-   high-risk migrations;
-   controlled release checkpoints;
-   retention beyond automated-backup windows.

Backups SHALL be encrypted.

------------------------------------------------------------------------

## 30. Point-in-Time Recovery

Production SHALL support RDS point-in-time recovery within the
configured retention window.

``` text
Operational Database
       │
       ▼
Automated Backups + Logs
       │
       ▼
Restore to Selected Time
       │
       ▼
New RDS Instance
       │
       ▼
Validate
```

A point-in-time restore creates a recovery database; it SHALL not be
treated as an in-place undo button.

------------------------------------------------------------------------

## 31. Restore Testing

Backup success does not prove recoverability.

Production readiness SHALL include periodic restore tests that verify:

-   database restoration;
-   application connectivity;
-   schema integrity;
-   representative queries;
-   required secrets/access;
-   recovery timing.

RPO/RTO acceptance is governed by ADR-Infra-0018 and ADR-Infra-0019.

------------------------------------------------------------------------

## 32. Deletion Protection

Production databases SHALL enable deletion protection where supported
and appropriate.

Terraform lifecycle safeguards SHOULD additionally protect critical
database resources from accidental destruction.

Destructive replacement of a Production database SHALL require explicit
review.

`terraform apply` SHALL not casually replace a stateful database because
of a configuration refactor.

------------------------------------------------------------------------

## 33. Snapshot on Destruction

Where a controlled database deletion is genuinely approved, a final
snapshot SHOULD be required unless the approved data-destruction policy
explicitly prohibits retention.

Deletion and retention requirements SHALL align with legal and
data-governance obligations.

------------------------------------------------------------------------

## 34. Maintenance

RDS maintenance windows SHALL be explicitly configured.

Minor-version upgrades SHOULD be deliberate and validated.

Automatic maintenance SHALL not be allowed to create unknown
compatibility risk for critical engines.

Major PostgreSQL upgrades require:

-   compatibility review;
-   extension review;
-   driver review;
-   migration rehearsal;
-   backup;
-   rollback/recovery plan.

------------------------------------------------------------------------

## 35. Extensions

PostgreSQL extensions SHALL be enabled only when required and supported
by the selected RDS PostgreSQL version.

Application repositories SHALL document extension dependencies.

A service SHALL not assume superuser access to install arbitrary
extensions at runtime.

------------------------------------------------------------------------

## 36. Parameter Groups

Production SHALL use explicit RDS parameter groups where non-default
database behaviour is required.

Parameter changes SHALL be:

-   version controlled;
-   reviewed;
-   tested;
-   classified as dynamic or reboot-requiring;
-   monitored after rollout.

Copying local `postgresql.conf` assumptions into RDS is prohibited.

------------------------------------------------------------------------

## 37. Observability

Production PostgreSQL monitoring SHOULD include:

-   CPU;
-   memory pressure;
-   storage capacity;
-   IOPS/latency;
-   active connections;
-   connection saturation;
-   locks;
-   deadlocks;
-   transaction rates;
-   replication/failover health;
-   slow/expensive queries;
-   backup health.

Enhanced monitoring and Performance Insights-equivalent/current AWS
database performance capabilities SHOULD be enabled where justified.

------------------------------------------------------------------------

## 38. Database Logs

Relevant PostgreSQL logs SHALL be exported to the approved observability
platform where supported.

Logging SHALL balance diagnostic value against:

-   sensitive-data exposure;
-   storage cost;
-   performance;
-   retention requirements.

SQL parameter values containing sensitive data SHALL not be logged
indiscriminately.

------------------------------------------------------------------------

## 39. Alerts

Actionable alerts SHOULD cover conditions such as:

-   storage exhaustion risk;
-   sustained high CPU;
-   connection saturation;
-   replication/failover degradation;
-   backup failure;
-   abnormal database restart;
-   excessive latency;
-   critical certificate/connection failures.

Alerts SHALL identify ownership and response expectations.

------------------------------------------------------------------------

## 40. Read Replicas

Read replicas MAY be introduced where measured read workloads justify
them.

They SHALL NOT be created by default.

Applications using replicas SHALL explicitly tolerate replication lag
and eventual consistency.

A read replica SHALL not silently become the source for operations
requiring read-after-write consistency.

------------------------------------------------------------------------

## 41. Analytics Workloads

Heavy analytical workloads SHOULD NOT compete indefinitely with
operational transaction processing.

Where Baobab Pulse, reporting or future analytics materially affect OLTP
performance, architecture SHOULD use:

-   replicas;
-   extracts;
-   events;
-   dedicated analytical stores;
-   other approved data pipelines.

The Production transactional database SHALL not become a universal
analytics warehouse.

------------------------------------------------------------------------

## 42. Cross-Service Queries

Direct cross-service SQL joins are prohibited as an integration pattern.

Rejected:

``` text
Trade Service
    │
    └── SQL JOIN IAM tables
```

Preferred:

``` text
Trade Service
    │
    ├── API
    └── canonical event/data contract
```

This preserves domain ownership and independent evolution.

------------------------------------------------------------------------

## 43. Multi-Tenant Query Safety

Tenant-aware applications SHALL make tenant/legal-entity context
explicit in database operations.

Defence-in-depth MAY include PostgreSQL capabilities such as Row-Level
Security where compatible with the owning service architecture.

However, infrastructure SHALL NOT impose RLS generically without
service-level design and tests.

Tenant isolation SHALL be verified through application and database
integration tests.

------------------------------------------------------------------------

## 44. Administrative Access

Routine Production administration SHALL use controlled private access.

The database SHALL not be made public temporarily for troubleshooting.

Administrative actions SHALL be:

-   authenticated;
-   least privilege;
-   auditable;
-   time-bounded where appropriate.

The master/admin account SHALL be reserved for exceptional
administration and bootstrap operations.

------------------------------------------------------------------------

## 45. Break-Glass Access

A controlled break-glass database procedure SHALL exist.

``` text
Incident
   │
   ▼
Authorised Escalation
   │
   ▼
Temporary Privileged Access
   │
   ▼
Audited Intervention
   │
   ▼
Revoke / Rotate
   │
   ▼
Incident Record
```

Break-glass credentials SHALL not become normal operator credentials.

------------------------------------------------------------------------

## 46. Data Residency

Database placement SHALL respect accepted residency and jurisdiction
decisions.

The fact that ZuriBeans may trade in Uganda and South Africa does not
automatically mean its database must be replicated into both
countries/markets.

Placement decisions SHALL consider:

-   law/regulation;
-   contractual obligations;
-   data classification;
-   latency;
-   availability;
-   recovery;
-   cost.

------------------------------------------------------------------------

## 47. ZuriBeans Go-Live

ZuriBeans SHALL consume PostgreSQL only through the Baobab services that
own the relevant data.

Conceptually:

``` text
ZuriBeans
    │
    ▼
APISIX
    │
    ├──► baobab-trade ──► Trade PostgreSQL
    ├──► baobab-iam   ──► IAM PostgreSQL
    └──► baobab-cp    ──► CP PostgreSQL
```

ZuriBeans SHALL NOT receive direct credentials to all platform
databases.

Its B2B data SHALL remain isolated from Thamani's B2C data even where
shared infrastructure is used.

------------------------------------------------------------------------

## 48. Failure Behaviour

``` text
Application
    │
    ▼
DB connection
    │
 ┌──┴─────┐
 │        │
Healthy  Failure/Failover
 │        │
 ▼        ▼
Serve    bounded retry/
         reconnect
```

Applications SHALL:

-   use bounded connection timeouts;
-   avoid infinite retry storms;
-   tolerate expected failover/reconnection behaviour;
-   expose dependency degradation through health/telemetry.

Retry policy SHALL respect transaction safety.

------------------------------------------------------------------------

## 49. Disaster Recovery Boundary

Multi-AZ protects against selected availability failures within the
region.

It does NOT provide regional disaster recovery.

Cross-region database recovery/replication is governed by
ADR-Infra-0019.

The backup architecture SHALL nevertheless preserve the ability to
implement accepted regional recovery objectives later.

------------------------------------------------------------------------

## 50. Infrastructure as Code

Terraform SHALL manage RDS infrastructure, including where applicable:

``` text
terraform/modules/postgres/
├── DB subnet group
├── security group
├── RDS instance/cluster
├── KMS encryption
├── parameter group
├── backup policy
├── maintenance settings
├── monitoring
├── deletion protection
├── secrets/IAM integration
├── optional RDS Proxy
└── operational outputs
```

Terraform SHALL NOT manage application tables or ordinary domain
migrations.

------------------------------------------------------------------------

## 51. Production Verification

Before go-live, verification SHALL demonstrate:

-   database is private;
-   only authorised security groups can connect;
-   TLS connections succeed and insecure paths are rejected according to
    policy;
-   runtime does not use master credentials;
-   backups are enabled;
-   PITR is available;
-   restore succeeds;
-   deletion protection is active;
-   monitoring/alerts work;
-   Multi-AZ failover behaviour is understood/tested;
-   application connection pools remain within safe limits;
-   tenant/legal-entity isolation tests pass;
-   migration and rollback procedures are documented.

------------------------------------------------------------------------

## 52. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  PostgreSQL containers   Rejected                Wrong
  on Fargate                                      durability/operations
                                                  model

  Self-managed PostgreSQL Rejected                Unnecessary operational
  on EC2 by default                               burden

  Aurora PostgreSQL as    Deferred                No demonstrated need
  default                                         yet

  Public RDS endpoint     Rejected                Violates trust-zone
                                                  architecture

  One RDS instance per    Rejected                Tenant does not imply
  tenant by default                               physical DB

  One shared application  Rejected                Breaks domain ownership
  schema for every                                
  service                                         

  Cross-service SQL       Rejected                Tight coupling
  integration                                     

  Application use of RDS  Rejected                Excessive privilege
  master user                                     

  Unlimited connection    Rejected                Database exhaustion
  pools                                           risk

  Terraform-managed       Rejected                Wrong lifecycle
  application tables                              boundary

  Backups without restore Rejected                Unproven recovery
  tests                                           

  Multi-AZ described as   Rejected                Does not cover regional
  DR                                              loss

  Automatic read replicas Rejected                Cost/complexity without
  everywhere                                      evidence
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 53. Consequences

### Positive

-   Managed PostgreSQL operations.
-   PostgreSQL 17 baseline aligned with Baobab.
-   Strong private-network posture.
-   Multi-AZ production availability.
-   Native backup and PITR.
-   Explicit service/database ownership.
-   Preserves tenant/legal-entity isolation without database-per-tenant
    sprawl.
-   Supports IAM/Secrets Manager authentication patterns.
-   Clear schema-migration ownership.
-   Practical ZuriBeans go-live foundation.

### Costs

-   RDS introduces AWS service dependency.
-   Multi-AZ increases cost.
-   Database topology requires workload-specific sizing.
-   Connection management must be engineered carefully.
-   IAM authentication is not universally suitable.
-   Restore/failover testing requires operational effort.
-   Future Aurora or cross-region migration may require additional work.

These costs are accepted.

------------------------------------------------------------------------

## 54. Decision Rules

The following rules are authoritative:

> **Amazon RDS for PostgreSQL SHALL be Baobab's default managed
> Production PostgreSQL platform.**

> **PostgreSQL 17 SHALL be the initial Production major-version
> baseline.**

> **Critical Production databases SHALL use an appropriate RDS Multi-AZ
> architecture.**

> **Production PostgreSQL SHALL be private and encrypted at rest and in
> transit.**

> **Application workloads SHALL NOT use the RDS master/admin account for
> routine runtime access.**

> **Database ownership SHALL follow service/domain ownership.**

> **Terraform SHALL own database infrastructure but SHALL NOT own
> ordinary application schema migrations.**

> **Tenant SHALL NOT imply RDS instance.**

> **ZuriBeans and Thamani SHALL remain logically isolated legal-entity
> workloads even when infrastructure is shared.**

> **Connection pools SHALL be bounded and included in capacity
> planning.**

> **Backups SHALL be accompanied by tested restoration and point-in-time
> recovery procedures.**

> **Multi-AZ SHALL NOT be treated as regional disaster recovery.**

> **Aurora PostgreSQL remains an evidence-driven future option rather
> than the default.**

------------------------------------------------------------------------

## 55. Current AWS Validation

At the time of this ADR:

-   AWS documents RDS for PostgreSQL 17 support in Africa (Cape Town).
-   AWS documents Multi-AZ PostgreSQL support in Africa (Cape Town),
    including PostgreSQL 17.
-   RDS PostgreSQL supports SSL/TLS connections and enforcement.
-   RDS supports automated backups, snapshots and point-in-time restore.
-   RDS Proxy supports PostgreSQL connection pooling and IAM/Secrets
    Manager authentication patterns.

These capabilities SHALL still be revalidated against current AWS
documentation immediately before implementation because regional
features and service behaviour can evolve.

------------------------------------------------------------------------

## 56. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0011 --- Redis Production Architecture**

It shall define:

-   managed Redis/Valkey service selection;
-   ElastiCache topology;
-   cache versus authoritative-state boundaries;
-   Multi-AZ/failover;
-   encryption;
-   authentication;
-   tenant isolation;
-   eviction policy;
-   persistence requirements;
-   key naming;
-   TTL policy;
-   connection management;
-   observability;
-   backup where required;
-   and failure behaviour for Baobab workloads.
