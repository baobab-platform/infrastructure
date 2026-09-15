# ADR-Infra-0018 --- Backup, Restore and Data Retention

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0004 --- Terraform State, Locking and Bootstrap
    -   ADR-Infra-0009 --- APISIX and etcd Production Architecture
    -   ADR-Infra-0010 --- PostgreSQL Production Architecture
    -   ADR-Infra-0011 --- Redis Production Architecture
    -   ADR-Infra-0012 --- RabbitMQ Production Architecture
    -   ADR-Infra-0013 --- Infrastructure IAM and Workload Identity
    -   ADR-Infra-0014 --- Secrets, Keys and Certificate Management
    -   ADR-Infra-0015 --- Tenant and Workload Infrastructure Isolation
    -   ADR-Infra-0016 --- Observability and Telemetry Architecture
    -   ADR-Infra-0017 --- SLOs, Health, Capacity and Operational
        Monitoring
-   **Follow-on:** ADR-Infra-0019 --- Availability, Disaster Recovery
    and Business Continuity

------------------------------------------------------------------------

## 1. Context

Baobab production data spans several state classes and technologies:

-   PostgreSQL-backed platform and engine state;
-   Control Plane desired state, mappings and outbox records;
-   Keycloak/IAM data;
-   Medusa/Trade data;
-   iDempiere ERP data;
-   Payload CMS data;
-   RabbitMQ in-flight messages;
-   APISIX configuration stored in etcd;
-   Redis/Valkey disposable or reconstructable projections;
-   object/file storage;
-   Terraform state;
-   secrets, keys and certificate dependencies;
-   observability and audit records.

A platform is not recoverable merely because a backup job reports
success.

Production requires the ability to answer:

> What is authoritative?

> What can be reconstructed?

> What must be backed up?

> How far back can we recover?

> How long may recovery take?

> How do we prove that restoration actually works?

This ADR establishes the backup, restoration and retention architecture.
Cross-region disaster recovery and business continuity are governed
separately by ADR-Infra-0019.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL implement **data-class-aware, encrypted, automated and
regularly tested backup and restoration**.

Every Production stateful component SHALL be classified as one of:

1.  **Authoritative**
2.  **Durable operational**
3.  **Reconstructable**
4.  **Ephemeral**

Backup policy SHALL follow the state classification rather than treating
all storage equally.

A successful backup SHALL NOT be considered sufficient evidence of
recoverability.

> **Restore testing is mandatory.**

------------------------------------------------------------------------

## 3. State Classification

  ------------------------------------------------------------------------------
  Class                   Meaning                        Examples
  ----------------------- ------------------------------ -----------------------
  **Authoritative**       Primary source of              PostgreSQL domain data,
                          business/platform truth        Control Plane state

  **Durable operational** Required operational state not etcd gateway
                          conveniently reconstructed     configuration, selected
                                                         integration state

  **Reconstructable**     Can be rebuilt from            Redis
                          authoritative                  projections/caches
                          sources/events/configuration   

  **Ephemeral**           Safe to lose and recreate      temporary files,
                                                         replaceable task-local
                                                         state
  ------------------------------------------------------------------------------

Classification SHALL be documented for every Production data store.

------------------------------------------------------------------------

## 4. Authoritative Data

Authoritative data SHALL receive the strongest backup and restore
controls.

Examples include:

-   Control Plane PostgreSQL;
-   Trade authoritative databases;
-   IAM/Keycloak database;
-   ERP/iDempiere database;
-   CMS/Payload authoritative database;
-   other domain databases declared authoritative.

A cache, broker or telemetry backend SHALL not silently become
authoritative merely because applications depend on it operationally.

------------------------------------------------------------------------

## 5. Backup Architecture

``` text
Authoritative / Durable State
          │
          ▼
   Automated Backup
          │
          ├── encryption
          ├── retention
          ├── access control
          ├── monitoring
          └── lifecycle
          │
          ▼
   Recovery Repository
          │
          ▼
   Scheduled Restore Test
          │
          ▼
   Verified Recoverability
```

------------------------------------------------------------------------

## 6. RPO and RTO

Every critical stateful service SHALL have approved:

-   **Recovery Point Objective (RPO)** --- maximum acceptable data loss
    measured in time;
-   **Recovery Time Objective (RTO)** --- target time to restore
    service/data after a qualifying failure.

``` text
Failure
  │
  ├──────────────► RTO ──────────────► Service Restored
  │
Last Recoverable Point
  ◄──── RPO ────► Failure
```

Exact RPO/RTO values SHALL be established with owning domains and
business requirements.

Infrastructure SHALL NOT invent one universal RPO/RTO for all Baobab
services.

------------------------------------------------------------------------

## 7. RPO/RTO Drive Architecture

Backup frequency, retention and restoration mechanisms SHALL be derived
from RPO/RTO requirements.

Example:

``` text
Tight RPO
   │
   ├── continuous/PITR capability
   └── frequent durable capture

Tight RTO
   │
   ├── automated restore
   ├── tested runbook
   └── pre-defined infrastructure
```

A daily snapshot cannot satisfy a one-hour RPO.

------------------------------------------------------------------------

## 8. PostgreSQL Baseline

Amazon RDS for PostgreSQL SHALL use automated backups and point-in-time
recovery capabilities appropriate to the accepted RPO.

Production SHALL enable:

-   automated backups;
-   transaction-log-backed point-in-time recovery;
-   encrypted snapshots;
-   retention appropriate to service requirements;
-   deletion protection where appropriate;
-   monitoring of backup health.

Manual snapshots SHALL supplement automated backups at high-risk
operational points where justified.

------------------------------------------------------------------------

## 9. Point-in-Time Recovery

PITR SHALL be the preferred recovery mechanism for many
logical/operational PostgreSQL incidents.

Examples:

-   accidental destructive change;
-   bad migration;
-   application corruption detected after commit;
-   selected operational recovery scenarios.

PITR SHALL be tested, not merely enabled.

------------------------------------------------------------------------

## 10. PostgreSQL Restore Pattern

Restoration SHOULD normally create a separate recovered database
environment first.

``` text
Production DB
    │
    X incident
    │
    ▼
Backup / PITR
    │
    ▼
Recovered DB
    │
    ├── integrity verification
    ├── application verification
    └── controlled cutover
```

Overwriting the only Production database in place before validating
recovery is discouraged.

------------------------------------------------------------------------

## 11. Database-Level Logical Backups

Native logical exports MAY supplement RDS physical/PITR mechanisms when
useful for:

-   selected schema/table recovery;
-   migration;
-   portability;
-   forensic recovery.

Logical dumps SHALL NOT replace RDS automated backups/PITR for critical
Production databases.

------------------------------------------------------------------------

## 12. Engine Database Ownership

Each engine SHALL own recovery correctness for its schema/domain.

Infrastructure restores the database service/data.

The owning engine verifies:

-   schema integrity;
-   migrations;
-   domain invariants;
-   application compatibility;
-   integration consistency.

A database that starts successfully is not necessarily a correctly
restored application.

------------------------------------------------------------------------

## 13. Control Plane Recovery

`baobab-cp` PostgreSQL is authoritative for Control Plane state.

Recovery SHALL preserve consistency among:

-   tenants/contexts;
-   capability bindings;
-   EngineInstance resolution;
-   mappings/external references;
-   desired state;
-   transactional outbox.

After restore, reconciliation workers SHALL be started carefully to
avoid applying stale or duplicated desired-state actions before
integrity is verified.

------------------------------------------------------------------------

## 14. Transactional Outbox Recovery

Outbox records SHALL be restored with the authoritative database
transaction history.

After recovery:

``` text
Restored Outbox
      │
      ▼
Publisher resumes
      │
      ▼
Possible redelivery/republication
      │
      ▼
Idempotent Consumers
```

Consumers SHALL remain correct under duplicate delivery as required by
ADR-Infra-0012.

------------------------------------------------------------------------

## 15. IAM/Keycloak Recovery

Keycloak's authoritative database SHALL be backed up under the
PostgreSQL policy applicable to `baobab-iam`.

Recovery SHALL account for:

-   realms;
-   users;
-   clients;
-   roles/scopes;
-   sessions where applicable;
-   signing-key dependencies;
-   external identity-provider configuration;
-   secret references.

IAM recovery SHALL be tested because a platform whose data is restored
but whose users cannot authenticate is not operationally recovered.

------------------------------------------------------------------------

## 16. Trade Recovery

Baobab Trade recovery SHALL preserve the accepted Medusa/domain
invariants.

Recovery verification SHOULD include, as applicable:

-   customers/accounts;
-   products/catalogue;
-   prices;
-   orders;
-   inventory state;
-   payments references;
-   tax configuration;
-   tenant/legal-entity separation.

External payment-provider truth SHALL be reconciled where required
rather than blindly overwritten from local state.

------------------------------------------------------------------------

## 17. ERP Recovery

iDempiere ERP recovery SHALL include its authoritative PostgreSQL data
and required application configuration.

Verification SHALL include:

-   tenant/client/organization boundaries;
-   accounting data;
-   master data;
-   orders/invoices;
-   integration mappings;
-   application compatibility.

ERP recovery SHALL follow accepted `baobab-erp` ADRs and supported
iDempiere procedures.

------------------------------------------------------------------------

## 18. CMS Recovery

Payload CMS recovery SHALL include its authoritative database and any
external object/file storage required for complete content
reconstruction.

Database backup without referenced media/object assets may be
incomplete.

The CMS restore runbook SHALL verify both metadata and content assets.

------------------------------------------------------------------------

## 19. Object Storage

Production object storage SHALL use appropriate protection such as:

-   versioning;
-   encryption;
-   lifecycle policy;
-   restricted deletion;
-   backup/copy where RPO/RTO requires it.

Versioning is valuable protection but SHALL not automatically be
described as a complete backup strategy.

------------------------------------------------------------------------

## 20. Object/Data Consistency

Where a database references objects:

``` text
Database Record
      │
      ▼
Object Key
      │
      ▼
S3/Object
```

recovery SHALL account for consistency between database and object
versions.

Restore procedures SHALL avoid recovering metadata to a point that
references unavailable objects where this can be prevented.

------------------------------------------------------------------------

## 21. etcd Backup

Production etcd SHALL have automated snapshots.

Snapshots SHALL be:

-   encrypted;
-   stored outside the etcd member's local failure domain;
-   access controlled;
-   retained according to policy;
-   monitored;
-   regularly restored in testing.

etcd member disks alone are not the backup strategy.

------------------------------------------------------------------------

## 22. etcd Restore

An etcd restore test SHALL verify:

``` text
Snapshot
   │
   ▼
Recovered etcd Cluster
   │
   ▼
Authentication/TLS
   │
   ▼
APISIX Reconnect
   │
   ▼
Expected Gateway Configuration
```

A snapshot file that has never produced a working APISIX configuration
is unproven.

------------------------------------------------------------------------

## 23. RabbitMQ Recovery Boundary

RabbitMQ is transport, not the authoritative business database.

Recovery SHALL prioritise:

-   broker availability;
-   topology/configuration;
-   durable in-flight messages where the managed service preserves them;
-   publisher outbox recovery;
-   consumer idempotency;
-   replay/republication from authoritative systems where designed.

The platform SHALL NOT rely on RabbitMQ queues as the only copy of
business truth.

------------------------------------------------------------------------

## 24. RabbitMQ Topology Recovery

Exchanges, queues, bindings, permissions and policies SHALL be
reproducible from approved configuration/application declarations where
practical.

``` text
Broker Lost
   │
   ▼
Recreate Broker
   │
   ▼
Restore/Reapply Topology
   │
   ▼
Restore Credentials
   │
   ▼
Resume Publishers/Consumers
```

Topology reproducibility reduces dependence on opaque broker state.

------------------------------------------------------------------------

## 25. RabbitMQ Message Loss Scenario

If broker recovery cannot preserve every in-flight message, applications
SHALL rely on their authoritative publication/reconciliation design.

For transactional publishers:

``` text
Authoritative DB + Outbox
          │
          ▼
Re-publish safely
```

Exactly-once recovery SHALL not be assumed.

------------------------------------------------------------------------

## 26. Redis/Valkey Recovery

Redis/Valkey state SHALL follow its classification.

For reconstructable cache/projection data:

``` text
Cache Lost
   │
   ▼
Recreate
   │
   ▼
Warm/Rebuild from authoritative sources
```

Snapshots MAY reduce recovery time but are not necessarily required for
correctness.

------------------------------------------------------------------------

## 27. Durable Redis Exception

If a workload declares Redis/Valkey data non-reconstructable, that
decision SHALL trigger architecture review.

The workload SHALL define:

-   why a durable authoritative store is unsuitable;
-   RPO/RTO;
-   snapshot/replication requirements;
-   restore procedure;
-   failure semantics.

Redis SHALL not become durable truth accidentally.

------------------------------------------------------------------------

## 28. Terraform State

Terraform state SHALL be protected according to ADR-Infra-0004 using:

-   remote S3 storage;
-   encryption;
-   versioning;
-   access control;
-   locking;
-   audit.

S3 versioning provides recovery from selected state corruption/deletion
scenarios.

Terraform state SHALL not be backed up by copying it into Git.

------------------------------------------------------------------------

## 29. Terraform State Recovery

State recovery SHALL be deliberate.

``` text
State Incident
    │
    ▼
Stop Automated Applies
    │
    ▼
Inspect Version History
    │
    ▼
Recover Correct State
    │
    ▼
terraform plan
    │
    ▼
Verify No Destructive Drift
```

Blindly recreating state or running apply after state loss is
prohibited.

------------------------------------------------------------------------

## 30. Secrets and Keys

Backups are useless if required secrets or encryption keys are
unavailable.

Recovery planning SHALL include:

-   KMS key availability;
-   Secrets Manager recovery/lifecycle;
-   certificate dependencies;
-   third-party credentials;
-   database credentials;
-   broker credentials.

KMS keys required for retained backups SHALL not be deleted prematurely.

------------------------------------------------------------------------

## 31. KMS Dependency Inventory

Critical backup classes SHALL identify their KMS dependencies.

``` text
Backup
   │
   ▼
KMS Key
   │
   ▼
Recovery Permission
```

Recovery roles SHALL have controlled ability to use required keys
without receiving unnecessary key-administration permissions.

------------------------------------------------------------------------

## 32. Backup Encryption

Production backups SHALL be encrypted at rest.

Backup transfer SHALL use encrypted transport.

Encryption SHALL use approved AWS KMS/key controls where supported.

Backup encryption SHALL not make recovery dependent on undocumented
manual key custody.

------------------------------------------------------------------------

## 33. Backup IAM

Backup creation, deletion and restoration SHALL use dedicated
least-privilege identities where practical.

Normal application workloads SHALL not receive broad backup deletion
permissions.

Recovery identities SHALL be distinct from ordinary runtime roles.

------------------------------------------------------------------------

## 34. Backup Deletion Protection

Critical backups SHOULD be protected against accidental or malicious
deletion.

Controls MAY include:

-   restricted IAM;
-   retention policies;
-   AWS Backup Vault Lock where applicable;
-   S3 Object Lock where applicable;
-   separate backup accounts/vaults where justified.

Immutability controls SHALL be evaluated against legal deletion
requirements.

------------------------------------------------------------------------

## 35. AWS Backup

AWS Backup SHOULD be used where it materially centralises policy,
monitoring, retention, restore testing or cross-resource protection for
supported AWS resources.

It SHALL not be adopted mechanically for a resource where the
service-native backup mechanism provides the required control more
effectively.

The architecture MAY combine service-native backup with AWS Backup.

------------------------------------------------------------------------

## 36. Backup Account Boundary

A dedicated backup/security account SHOULD be considered as the AWS
Organization matures.

Conceptually:

``` text
Production Account
      │
      ▼
Cross-Account Backup
      │
      ▼
Backup / Security Account
```

This can reduce the blast radius of compromised Production credentials.

Initial implementation MAY remain within the Production account if
equivalent controls satisfy the approved risk level.

------------------------------------------------------------------------

## 37. Backup Retention Classes

Retention SHALL be policy-driven.

A practical model MAY include:

  Class         Purpose
  ------------- ----------------------------------------------
  Short-term    operational rollback/PITR
  Medium-term   incident recovery
  Long-term     legal/audit/business retention
  Archive       exceptional regulated/historical requirement

Exact durations SHALL be defined per data class and legal/business
requirement.

------------------------------------------------------------------------

## 38. Retention Is Not One Number

Baobab SHALL NOT impose one universal backup retention period.

Examples differ:

-   transactional business records;
-   infrastructure state;
-   gateway configuration;
-   logs;
-   temporary caches;
-   legal/audit records.

Retention SHALL reflect data purpose and obligations.

------------------------------------------------------------------------

## 39. Data Retention vs Backup Retention

These concepts SHALL remain distinct:

``` text
Application Data Retention
        │
        └── how long business data should exist

Backup Retention
        │
        └── how long recovery copies are retained
```

Deleting a record from the live system does not necessarily remove it
immediately from immutable backup media.

Legal/privacy procedures SHALL account for this distinction.

------------------------------------------------------------------------

## 40. Tenant/Legal-Entity Retention

ZuriBeans and Thamani SHALL retain independent legal-entity data
policies even where their data resides on shared infrastructure.

Shared backup media SHALL not erase logical ownership.

A tenant exit SHALL not permit deletion of shared backups required for
other tenants.

------------------------------------------------------------------------

## 41. Tenant-Level Restore

Where tenants share physical databases, restoring one tenant SHALL NOT
normally require destructive rollback of all other tenants.

Possible recovery mechanisms include:

``` text
PITR to temporary database
       │
       ▼
Extract affected tenant/domain data
       │
       ▼
Validate
       │
       ▼
Controlled repair/import
```

The exact method SHALL be owned by the domain and tested where
tenant-level recovery is required.

------------------------------------------------------------------------

## 42. Shared Database Recovery Risk

Shared physical infrastructure creates a distinction between:

-   infrastructure restore;
-   service/domain restore;
-   tenant-level logical restore.

The platform SHALL not claim tenant-level restore capability until it
has been demonstrated.

------------------------------------------------------------------------

## 43. IsolationProfile and Backup

Stronger IsolationProfiles MAY receive:

-   dedicated backup schedules;
-   dedicated vaults;
-   dedicated keys;
-   longer retention;
-   customer-specific recovery objectives.

Tenant SHALL not imply dedicated backup infrastructure by default.

------------------------------------------------------------------------

## 44. Backup Monitoring

Backup monitoring SHALL identify:

-   missed backups;
-   failed jobs;
-   expired recovery windows;
-   failed snapshots;
-   unexpected backup duration;
-   storage growth;
-   retention failures;
-   restore-test failures.

A backup failure SHALL be actionable and owned.

------------------------------------------------------------------------

## 45. Restore Testing

Restore tests SHALL be scheduled.

Testing SHALL include representative critical systems, not merely the
easiest database.

A restore test SHALL verify:

``` text
Backup exists
   │
   ▼
Restore succeeds
   │
   ▼
Data integrity
   │
   ▼
Application starts
   │
   ▼
Critical operations work
   │
   ▼
Measured recovery time
```

------------------------------------------------------------------------

## 46. Restore Frequency

Critical authoritative systems SHOULD be restored in controlled tests on
a regular schedule.

Frequency SHALL reflect:

-   RPO/RTO;
-   change rate;
-   business criticality;
-   regulatory expectations;
-   platform maturity.

A Production launch SHALL not precede the first successful restore test
of critical authoritative state.

------------------------------------------------------------------------

## 47. Restore Test Environment

Restore tests SHOULD use isolated recovery infrastructure.

Recovered Production data SHALL remain protected.

Where real Production data is used for restore validation, access SHALL
be tightly controlled and it SHALL not be exposed to normal Development
environments.

------------------------------------------------------------------------

## 48. Recovery Integrity

Restore verification SHALL include domain-level integrity where
practical.

Examples:

-   expected record counts/checksums;
-   schema version;
-   tenant isolation;
-   application login;
-   order/invoice retrieval;
-   canonical mappings;
-   gateway route presence.

"Database engine accepted the snapshot" is insufficient.

------------------------------------------------------------------------

## 49. Recovery Sequencing

Baobab SHALL document dependency-aware recovery order.

A conceptual sequence is:

``` text
1. IAM / key / secret dependencies
2. Network / infrastructure foundations
3. Authoritative databases
4. Control Plane
5. Gateway configuration
6. Messaging
7. Core engines/services
8. Digital estates
9. Reconstructable caches/projections
10. Verification
```

The exact order SHALL be validated by service dependencies.

------------------------------------------------------------------------

## 50. Recovery and Reconciliation

After restoration, automated reconcilers, event publishers and consumers
SHALL be resumed carefully.

Potential risks include:

-   duplicate events;
-   stale desired state;
-   external-system divergence;
-   replay storms;
-   repeated payments/actions.

Recovery runbooks SHALL include reconciliation steps.

------------------------------------------------------------------------

## 51. External Systems

Baobab cannot restore third-party systems from its own backups.

Recovery SHALL reconcile with external truth where required, including:

-   payment providers;
-   banks;
-   carriers/logistics providers;
-   tax/customs systems;
-   external identity providers;
-   supplier/customer integrations.

Local restore SHALL not blindly overwrite externally completed actions.

------------------------------------------------------------------------

## 52. Backup Before High-Risk Change

A recoverable backup/snapshot SHOULD be confirmed before high-risk
changes such as:

-   major database migration;
-   major engine upgrade;
-   destructive schema change;
-   major IAM migration;
-   etcd cluster upgrade;
-   bulk data correction.

This SHALL complement, not replace, safe migration design.

------------------------------------------------------------------------

## 53. Recovery Evidence

Production readiness evidence SHALL include:

-   backup policy;
-   latest successful backup;
-   restore-test result;
-   measured restore duration;
-   integrity verification;
-   recovery owner;
-   runbook;
-   unresolved gaps.

Evidence SHALL be retained for audit and operational review.

------------------------------------------------------------------------

## 54. Backup Runbooks

Critical stateful services SHALL have runbooks for:

-   backup failure;
-   PITR;
-   snapshot restore;
-   logical recovery;
-   credential/key dependency;
-   validation;
-   controlled cutover;
-   rollback of recovery;
-   post-recovery reconciliation.

------------------------------------------------------------------------

## 55. Recovery Drills

Recovery drills SHOULD periodically test more than a technical restore.

A drill MAY simulate:

``` text
Incident declaration
      │
      ▼
Recovery authorization
      │
      ▼
Restore
      │
      ▼
Application verification
      │
      ▼
Operational handover
```

ADR-Infra-0019 expands this into disaster recovery and business
continuity.

------------------------------------------------------------------------

## 56. Production Deletion

Destructive deletion of stateful Production resources SHALL require:

-   approval;
-   retention check;
-   dependency check;
-   final backup/snapshot where appropriate;
-   verification that encryption keys remain available;
-   documented decommissioning.

Terraform destroy SHALL not casually remove authoritative data.

------------------------------------------------------------------------

## 57. Decommissioning

When a service or dedicated tenant resource is retired:

``` text
Disable Workload
     │
     ▼
Confirm Retention Requirement
     │
     ▼
Final Backup if Required
     │
     ▼
Revoke Access/Secrets
     │
     ▼
Destroy Resource
     │
     ▼
Retain/Expire Backup by Policy
```

Shared infrastructure SHALL not be destroyed because one tenant leaves.

------------------------------------------------------------------------

## 58. Observability Data

Operational telemetry has its own retention requirements.

CloudWatch logs/traces/metrics SHALL not be retained forever by default.

Security/audit logs MAY require longer retention than diagnostic traces.

ADR-Infra-0016 governs telemetry architecture; this ADR requires
explicit retention and recoverability where telemetry is legally or
operationally significant.

------------------------------------------------------------------------

## 59. Local Development

Local Docker Compose volumes SHALL NOT be treated as Production backup
architecture.

Developers MAY recreate local state freely unless a specific development
workflow requires preservation.

Production backup mechanisms SHALL be implemented independently of local
Compose.

------------------------------------------------------------------------

## 60. Production Verification

Before go-live, verification SHALL demonstrate:

-   every Production store has a state classification;
-   critical stores have approved RPO/RTO;
-   RDS automated backup/PITR is enabled where required;
-   critical PostgreSQL restore has been tested;
-   Control Plane recovery preserves mappings/outbox correctness;
-   IAM/Keycloak recovery permits authentication;
-   Trade and ERP domain integrity is verified after restore;
-   CMS data and object assets can be recovered;
-   etcd snapshots are automated and successfully restored;
-   RabbitMQ recovery does not rely on broker queues as sole business
    truth;
-   Redis/Valkey reconstructability is demonstrated or stronger policy
    exists;
-   Terraform state version recovery is documented/tested;
-   backup encryption and KMS dependencies are verified;
-   backup access is least privilege;
-   backup failures alert;
-   retention is explicit;
-   ZuriBeans legal-entity data remains isolated after recovery;
-   at least one end-to-end recovery exercise has succeeded.

------------------------------------------------------------------------

## 61. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Backup success =        Rejected                Restore may still fail
  recovery proof                                  

  One retention period    Rejected                Data classes differ
  for all data                                    

  Daily snapshots for     Rejected                May not meet required
  every RPO                                       RPO

  Local volumes as        Rejected                Wrong failure domain
  Production backup                               

  RabbitMQ as only event  Rejected                Broker is transport
  record                                          

  Redis as accidental     Rejected                Wrong recovery model
  durable truth                                   

  Terraform state copied  Rejected                Security/governance
  to Git                                          risk

  Database starts =       Rejected                Domain integrity
  application restored                            unverified

  Backup without KMS/key  Rejected                May be undecryptable
  planning                                        

  No restore tests before Rejected                Recovery unproven
  go-live                                         

  Tenant exit destroys    Rejected                Other tenants/retention
  shared backups                                  obligations

  In-place destructive    Rejected                Increases recovery risk
  restore first                                   

  Backup instead of safe  Rejected                Does not prevent
  migrations                                      avoidable failure

  Permanent Production    Rejected                Data-protection risk
  data in Development                             
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 62. Consequences

### Positive

-   Recoverability becomes testable rather than assumed.
-   Authoritative and reconstructable state are clearly distinguished.
-   RPO/RTO drive technical policy.
-   PostgreSQL, etcd, RabbitMQ, Redis and Terraform state receive
    appropriate---not identical---recovery strategies.
-   Tenant/legal-entity boundaries survive backup and restore.
-   Recovery includes keys, secrets and external reconciliation.
-   ZuriBeans go-live requires actual restoration evidence.
-   Provides the foundation for disaster recovery.

### Costs

-   Restore testing requires infrastructure and engineering time.
-   Backup storage and retention create cost.
-   Cross-account/immutable backups may add complexity.
-   Domain teams must participate in integrity verification.
-   Tenant-level logical restore can be complex on shared databases.
-   Recovery runbooks and drills require maintenance.

These costs are accepted.

------------------------------------------------------------------------

## 63. Decision Rules

> **Every Production stateful component SHALL be classified as
> authoritative, durable operational, reconstructable or ephemeral.**

> **Critical authoritative state SHALL have approved RPO and RTO
> objectives.**

> **Backup frequency and retention SHALL derive from recovery
> requirements rather than one platform-wide schedule.**

> **Amazon RDS PostgreSQL SHALL use automated backups and PITR
> appropriate to the accepted RPO.**

> **Production etcd SHALL have encrypted, monitored and restore-tested
> snapshots.**

> **RabbitMQ SHALL remain a transport; authoritative systems/outboxes
> SHALL provide recovery truth where messages must be reconstructed.**

> **Redis/Valkey caches and projections SHOULD be reconstructable; any
> non-reconstructable use requires explicit durability design.**

> **Terraform state SHALL use remote encrypted versioned storage and
> SHALL NOT be backed up in Git.**

> **Backups SHALL remain decryptable; KMS keys and secret dependencies
> are part of recovery architecture.**

> **A backup SHALL NOT be considered proven until restoration and
> application/domain integrity have been tested.**

> **Production go-live SHALL require successful restore evidence for
> critical authoritative state.**

> **Shared infrastructure SHALL preserve tenant/legal-entity ownership
> through recovery; tenant exit SHALL NOT destroy backups required by
> other tenants or retention policy.**

> **Backup and restore SHALL be automated and observable, but
> destructive recovery/cutover SHALL remain controlled.**

------------------------------------------------------------------------

## 64. Implementation Implications

Implementation SHALL progressively establish:

``` text
Backup & Recovery
│
├── PostgreSQL
│   ├── automated backups
│   ├── PITR
│   ├── snapshots
│   └── restore tests
│
├── etcd
│   ├── snapshots
│   ├── encrypted storage
│   └── APISIX recovery test
│
├── RabbitMQ
│   ├── reproducible topology
│   ├── outbox/replay recovery
│   └── broker recovery
│
├── Redis/Valkey
│   ├── rebuild path
│   └── snapshots where justified
│
├── Object Storage
│   ├── versioning
│   ├── lifecycle
│   └── backup where required
│
├── Terraform State
│   ├── S3 versioning
│   └── recovery runbook
│
├── Security
│   ├── KMS
│   ├── backup IAM
│   ├── immutability where justified
│   └── recovery roles
│
└── Governance
    ├── RPO/RTO
    ├── retention classes
    ├── restore schedule
    ├── evidence
    └── recovery drills
```

Implementation SHALL inspect accepted ADRs and recovery guidance in each
affected engine repository before defining engine-specific restore
procedures.

------------------------------------------------------------------------

## 65. Current Technical Validation

This ADR aligns with current AWS managed-service recovery capabilities
as of 2026-09-15.

Implementation SHALL revalidate current AWS documentation for:

-   RDS PostgreSQL automated backups, snapshots and point-in-time
    recovery;
-   AWS Backup support for the selected resources;
-   AWS Backup Vault Lock capabilities;
-   S3 Versioning/Object Lock where used;
-   KMS recovery/key lifecycle implications;
-   Amazon MQ RabbitMQ backup/recovery capabilities;
-   ElastiCache backup/restore capabilities;
-   cross-account backup support;
-   restore-testing automation available through AWS Backup.

Service availability and feature support in `af-south-1` SHALL be
confirmed before implementation.

------------------------------------------------------------------------

## 66. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0019 --- Availability, Disaster Recovery and Business
Continuity**

It shall define:

-   failure domains;
-   Multi-AZ availability;
-   regional disaster scenarios;
-   recovery tiers;
-   cross-region strategy;
-   warm/cold/active-passive decisions;
-   DNS failover;
-   data replication;
-   infrastructure reconstruction;
-   dependency recovery order;
-   IAM/KMS/secrets continuity;
-   RabbitMQ/etcd recovery;
-   operational command structure;
-   disaster declaration;
-   DR exercises;
-   and how Baobab meets business continuity objectives without
    prematurely adopting active-active multi-region architecture.
