# ADR-Infra-0019 --- Availability, Disaster Recovery and Business Continuity

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0005 --- Network and Trust-Zone Architecture
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0008 --- DNS, TLS, Edge and API Gateway Architecture
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
    -   ADR-Infra-0018 --- Backup, Restore and Data Retention
-   **Follow-on:** ADR-Infra-0020 --- CI/CD and Infrastructure Change
    Governance

------------------------------------------------------------------------

## 1. Context

Baobab's initial Production region is AWS Cape Town (`af-south-1`).

Production availability and disaster recovery are different concerns:

-   **High availability (HA)** reduces interruption from failures inside
    the active region.
-   **Disaster recovery (DR)** restores service after failures exceeding
    the active architecture's normal fault tolerance.
-   **Business continuity (BC)** defines how critical business
    operations continue or recover during severe disruption.

Multi-AZ architecture does not by itself provide regional disaster
recovery.

Likewise, backups do not by themselves provide an acceptable recovery
time.

Baobab requires a deliberate architecture that protects critical
services without prematurely adopting the operational complexity of
active-active multi-region systems.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL adopt:

1.  **Multi-AZ resilience within the primary Production region** for
    critical workloads where supported and justified.
2.  **Tiered disaster-recovery objectives** based on service
    criticality.
3.  **Infrastructure-as-code reconstruction** as a core recovery
    capability.
4.  **Encrypted, tested backups** as defined by ADR-Infra-0018.
5.  **Active-passive regional recovery** as the default future regional
    DR model when regional DR is required.
6.  **No active-active multi-region architecture by default.**
7.  **Regular DR exercises and documented business-continuity
    procedures** before claiming a DR capability.

The first Production release MAY operate primarily in `af-south-1` if
accepted business RPO/RTO and risk assessment permit it, but the
architecture SHALL preserve a tested path toward secondary-region
recovery.

------------------------------------------------------------------------

## 3. Failure Domains

Baobab SHALL explicitly distinguish failure domains.

``` text
Failure
  │
  ├── Process / Container
  ├── ECS Task / Service
  ├── Availability Zone
  ├── Managed-Service Node
  ├── VPC / Network Component
  ├── AWS Account / IAM Control
  ├── AWS Region
  ├── External Provider
  └── Organization / Operational Process
```

Recovery mechanisms SHALL match the failure domain.

------------------------------------------------------------------------

## 4. Failure Scope vs Recovery

  Failure                    Primary Response
  -------------------------- ------------------------------------
  Single task                ECS replacement
  Single service instance    Service redundancy/autoscaling
  AZ impairment              Multi-AZ placement/failover
  Database node failure      RDS managed failover
  Cache node failure         managed replica/failover
  RabbitMQ node failure      broker cluster resilience
  APISIX instance loss       multiple gateway tasks
  etcd member loss           quorum
  Region unavailable         DR activation
  Data corruption            restore/PITR
  Credential compromise      revoke/rotate
  Bad deployment             rollback
  External provider outage   degrade/retry/continuity procedure

DR SHALL not be invoked for failures that normal HA should absorb.

------------------------------------------------------------------------

## 5. Availability Zones

Critical Production workloads SHOULD span at least two Availability
Zones where the selected AWS service and architecture support it.

Conceptually:

``` text
                 Production VPC
          ┌─────────────┴─────────────┐
          ▼                           ▼
        AZ-A                         AZ-B
     ECS tasks                    ECS tasks
        │                            │
        └────────── ALB ─────────────┘
                 │
           Managed Data
           Multi-AZ where
             required
```

AZ placement SHALL avoid unnecessary single-AZ dependencies.

------------------------------------------------------------------------

## 6. ECS Availability

Critical ECS services SHALL normally run more than one task when service
objectives require continued operation through task failure.

Tasks SHOULD be distributable across multiple AZs.

Application state SHALL remain external so tasks can be replaced.

A critical service whose only Production task is lost SHALL not require
manual server repair.

------------------------------------------------------------------------

## 7. Deployment Availability

Production deployments SHOULD preserve healthy capacity during
replacement.

Deployment configuration SHALL consider:

-   minimum healthy percentage;
-   maximum replacement capacity;
-   startup time;
-   readiness;
-   rollback/circuit-breaker behaviour;
-   AZ distribution.

A deployment SHALL not intentionally remove all healthy instances
simultaneously unless the service objective explicitly permits downtime.

------------------------------------------------------------------------

## 8. RDS Availability

Critical Production PostgreSQL SHALL use an RDS Multi-AZ topology
appropriate to the service's SLO/RTO.

Managed failover SHALL be tested at the application level.

Applications SHALL:

-   reconnect safely;
-   use bounded retry;
-   avoid assuming permanent connection identity;
-   tolerate short failover interruption.

Multi-AZ protects regional availability; it is not regional DR.

------------------------------------------------------------------------

## 9. ElastiCache Availability

Critical Redis/Valkey deployments SHALL use replicas/Multi-AZ failover
where cache availability materially affects the service objective.

Applications SHALL remain correct after cache failover.

Where cache data is reconstructable, temporary cache loss SHOULD degrade
performance rather than corrupt authoritative state.

------------------------------------------------------------------------

## 10. RabbitMQ Availability

Critical Production RabbitMQ SHALL use the cluster architecture defined
in ADR-Infra-0012.

Applications SHALL tolerate:

-   connection interruption;
-   broker failover;
-   redelivery;
-   duplicate delivery.

Quorum queues, publisher confirms and idempotent consumers provide
message-delivery resilience but do not create regional DR.

------------------------------------------------------------------------

## 11. APISIX Availability

APISIX SHALL run with sufficient independent instances for the accepted
gateway availability objective.

``` text
ALB
 ├── APISIX Task A
 └── APISIX Task B
```

Loss of one gateway instance SHALL not require DNS change.

APISIX shall remain stateless with configuration sourced from its
approved control/configuration plane.

------------------------------------------------------------------------

## 12. etcd Availability

Production etcd SHALL use an odd-number quorum architecture as defined
by ADR-Infra-0009.

The initial critical topology is expected to use three voting members
where implementation validation confirms the selected AWS deployment
model.

Members SHALL be distributed to avoid one ordinary failure domain
eliminating quorum.

------------------------------------------------------------------------

## 13. etcd Quorum vs Traffic

Loss of etcd quorum is serious even if APISIX continues serving existing
configuration.

``` text
etcd Quorum Lost
      │
      ├── existing gateway traffic may continue
      └── configuration mutation/reconciliation impaired
```

Operational monitoring SHALL distinguish traffic availability from
configuration-plane availability.

------------------------------------------------------------------------

## 14. Edge Availability

Route 53, ACM, ALB and approved AWS edge protections SHALL be configured
to avoid unnecessary single-instance dependencies.

Public services SHALL use health-aware target routing.

DNS architecture SHALL preserve the ability to support future DR
failover without redesigning the public naming model.

------------------------------------------------------------------------

## 15. High Availability Is Not DR

Authoritative rule:

``` text
Multi-AZ
   ≠
Multi-Region
   ≠
Backup
   ≠
Disaster Recovery
   ≠
Business Continuity
```

Each solves a different class of failure.

------------------------------------------------------------------------

## 16. Recovery Tiers

Baobab SHALL classify services into recovery tiers.

A baseline model:

  ------------------------------------------------------------------------------------
  Tier                    Description                    Example Character
  ----------------------- ------------------------------ -----------------------------
  **DR-0**                Essential platform/customer    IAM, edge, critical
                          path                           transactional services

  **DR-1**                High-priority business service ERP/Trade supporting critical
                                                         operation

  **DR-2**                Important but delay-tolerant   CMS/intelligence/background
                                                         processing

  **DR-3**                Reconstructable/non-critical   disposable
                                                         projections/dev-support state
  ------------------------------------------------------------------------------------

Exact assignments SHALL be approved by service owners.

------------------------------------------------------------------------

## 17. Recovery Objectives

Each DR tier SHALL map to approved:

-   RTO;
-   RPO;
-   recovery priority;
-   recovery mechanism;
-   minimum continuity procedure.

This ADR intentionally does not invent universal numerical RTO/RPO
targets.

The business/domain owners SHALL define the acceptable interruption and
data-loss tolerance.

------------------------------------------------------------------------

## 18. Regional DR Strategy

When regional DR is required, Baobab SHALL prefer **active-passive**
recovery initially.

``` text
             Normal Operation
                    │
                    ▼
          Primary: af-south-1
                    │
          replicated/backed-up
              recovery assets
                    │
                    ▼
            Secondary Region
             passive/standby
```

The secondary region MAY be cold, pilot-light or warm depending on the
recovery tier.

------------------------------------------------------------------------

## 19. No Default Active-Active

Active-active multi-region is rejected as the initial default because it
materially increases complexity in:

-   data consistency;
-   tenant routing;
-   event ordering;
-   database writes;
-   IAM;
-   caches;
-   brokers;
-   external integrations;
-   observability;
-   deployments;
-   failure arbitration;
-   cost.

Active-active MAY be reconsidered only through a future ADR supported by
concrete requirements.

------------------------------------------------------------------------

## 20. Cold Recovery

Cold recovery means most compute is reconstructed after disaster from:

-   Terraform;
-   immutable images;
-   configuration;
-   backups;
-   secret/key recovery mechanisms.

It has lower steady-state cost but longer RTO.

Cold recovery MAY be acceptable for lower recovery tiers.

------------------------------------------------------------------------

## 21. Pilot-Light Recovery

Pilot-light recovery maintains selected critical foundations in the
secondary region while application capacity is largely
scaled/provisioned during activation.

Potential retained foundations include:

-   network;
-   IAM roles;
-   KMS;
-   secret replication where approved;
-   backup access;
-   DNS/certificate prerequisites.

Pilot-light MAY be used when cold recovery cannot meet RTO.

------------------------------------------------------------------------

## 22. Warm Standby

Warm standby maintains a reduced but functional secondary environment.

``` text
Primary Region
  full capacity
       │
       ▼
Secondary Region
 reduced capacity
 ready to scale
```

Warm standby MAY be selected for DR-0/DR-1 services where justified by
RTO and cost.

------------------------------------------------------------------------

## 23. Recovery Pattern Selection

Recovery architecture SHALL be selected by objective:

``` text
Longer RTO ───────────────► Shorter RTO
   Cold       Pilot Light      Warm
 lower cost                   higher cost
```

The most expensive DR model SHALL not be chosen merely because it
appears more sophisticated.

------------------------------------------------------------------------

## 24. Secondary Region Selection

A secondary AWS region SHALL NOT be selected solely because a tenant
operates commercially there.

Selection SHALL consider:

-   service availability;
-   data residency;
-   latency;
-   regulatory requirements;
-   AWS regional dependencies;
-   recovery distance;
-   cost;
-   operational capability.

The decision SHALL be documented before regional DR implementation.

------------------------------------------------------------------------

## 25. Infrastructure Reconstruction

Terraform SHALL make core infrastructure reproducible.

Regional recovery SHOULD be capable of rebuilding:

``` text
VPC / Network
IAM
KMS / Secrets dependencies
DNS / certificates
Compute
Data services
APISIX
Telemetry
Backup integrations
```

Manual console-only configuration that cannot be reconstructed SHALL be
treated as DR debt.

------------------------------------------------------------------------

## 26. Immutable Artifacts

Application recovery SHALL deploy previously approved immutable image
digests.

DR SHALL not require rebuilding source code from arbitrary branch state.

``` text
Approved Digest
      │
      ▼
Secondary ECR / Accessible Registry
      │
      ▼
Recovered ECS Service
```

Artifact availability SHALL be included in DR planning.

------------------------------------------------------------------------

## 27. Container Registry Continuity

Production-bound images required for recovery SHALL remain available if
the primary regional deployment path is impaired.

Options MAY include:

-   ECR cross-region replication;
-   controlled copy during DR preparation;
-   GHCR as an additional source where policy permits.

Exact mechanism SHALL be validated under ADR-Infra-0007.

------------------------------------------------------------------------

## 28. Data Recovery

Regional recovery SHALL use the mechanisms defined by ADR-Infra-0018.

Depending on service and RPO:

-   cross-region backup copy;
-   database snapshot/PITR recovery;
-   replica/promotion where supported and justified;
-   object replication;
-   configuration reconstruction.

No data mechanism SHALL be labelled DR until its recovery has been
tested.

------------------------------------------------------------------------

## 29. PostgreSQL Regional Recovery

PostgreSQL regional DR MAY use:

-   cross-region snapshot/backup copy;
-   AWS Backup cross-region copy;
-   cross-region replication/standby architecture where justified.

The selected mechanism SHALL satisfy the approved RPO/RTO and engine
compatibility.

Multi-AZ RDS alone SHALL NOT be presented as regional PostgreSQL DR.

------------------------------------------------------------------------

## 30. Object Storage Regional Recovery

Critical object data MAY require cross-region replication or recoverable
backup copies.

Selection SHALL account for:

-   object/database consistency;
-   retention;
-   legal placement;
-   deletion propagation;
-   encryption keys;
-   recovery order.

Automatic replication SHALL not bypass legal deletion or residency
requirements.

------------------------------------------------------------------------

## 31. RabbitMQ Regional Recovery

RabbitMQ regional DR SHALL NOT assume synchronous cross-region broker
clustering.

The preferred recovery model SHALL rely on:

-   authoritative domain state;
-   transactional outboxes;
-   reproducible broker topology;
-   idempotent consumers;
-   replay/republication where required.

A new broker MAY be established in the recovery region.

------------------------------------------------------------------------

## 32. etcd Regional Recovery

APISIX/etcd recovery SHALL use:

-   reproducible APISIX infrastructure;
-   protected etcd snapshots;
-   approved configuration desired state;
-   validation before public cutover.

Cross-region etcd quorum stretching SHALL NOT be the default.

------------------------------------------------------------------------

## 33. Redis/Valkey Regional Recovery

Reconstructable caches SHOULD be rebuilt in the recovery region.

Cross-region cache replication SHALL only be introduced where
RTO/business requirements justify it.

Cache recovery SHALL not delay authoritative service restoration
unnecessarily.

------------------------------------------------------------------------

## 34. IAM Continuity

A regional disaster SHALL not prevent operators from authenticating to
AWS recovery infrastructure.

DR planning SHALL verify:

-   AWS federation;
-   environment/recovery roles;
-   GitHub OIDC;
-   break-glass access;
-   task roles;
-   cross-account trust.

Recovery identities SHALL be tested before an incident.

------------------------------------------------------------------------

## 35. Key Continuity

Encrypted recovery assets require usable KMS keys.

DR SHALL account for:

-   multi-Region keys where justified;
-   independent regional keys;
-   cross-region backup encryption;
-   key policies;
-   recovery-role access.

A backup copied to another region but not decryptable there is not a
valid DR asset.

------------------------------------------------------------------------

## 36. Secret Continuity

Secrets required in the recovery region SHALL be available through an
approved mechanism.

Secrets SHALL NOT be copied manually into documents or runbooks.

Replication SHALL be limited to secrets required by the DR architecture
and shall preserve least privilege.

------------------------------------------------------------------------

## 37. Certificate Continuity

Recovery SHALL account for:

-   public DNS;
-   ACM certificates;
-   validation records;
-   private CA dependencies;
-   internal mTLS.

A secondary environment that cannot establish trusted TLS is not ready
for cutover.

------------------------------------------------------------------------

## 38. DNS Failover

Route 53 SHALL preserve a controlled mechanism for future regional
failover.

Conceptually:

``` text
Client
  │
  ▼
Route 53
  │
  ├── Primary healthy ──► Primary Region
  │
  └── DR activated ─────► Recovery Region
```

Failover SHALL be deliberate and based on tested health/activation
policy.

------------------------------------------------------------------------

## 39. Automatic vs Manual Regional Failover

Initial regional DR SHOULD prefer **controlled/manual authorization**
for full regional failover unless automated failover has been proven
safe.

A transient metric anomaly SHALL not automatically move the entire
platform to another region.

Automation MAY assist detection and execution while retaining explicit
disaster declaration/cutover control.

------------------------------------------------------------------------

## 40. Disaster Declaration

Regional DR SHALL begin with an explicit disaster declaration.

Authority SHALL be defined.

``` text
Severe Incident
      │
      ▼
Assess Failure Scope
      │
      ▼
Can HA recover?
  ┌───┴───┐
 Yes      No
  │        │
 normal    ▼
response  Declare Disaster
           │
           ▼
        DR Runbook
```

------------------------------------------------------------------------

## 41. Recovery Command Structure

Business continuity SHALL define roles such as:

-   Incident Commander;
-   Infrastructure Recovery Lead;
-   Application/Domain Leads;
-   Security/IAM Lead;
-   Communications Lead;
-   Business Decision Owner.

One individual MAY hold multiple roles in a small team, but
responsibilities SHALL be explicit.

------------------------------------------------------------------------

## 42. Recovery Priority

Recovery SHALL follow dependency and business priority.

A conceptual sequence:

``` text
1. Recovery identity / security access
2. Network / foundational infrastructure
3. Keys / secrets / certificates
4. Authoritative data
5. IAM
6. Control Plane
7. APISIX / gateway configuration
8. Trade and critical business services
9. Messaging / downstream consumers
10. ERP and supporting services
11. Digital estates
12. Caches/projections/background services
13. Full verification
```

The exact sequence SHALL be validated against accepted service
dependencies.

------------------------------------------------------------------------

## 43. Business Continuity

Technical recovery and business continuity SHALL be linked.

For each DR-0/DR-1 business capability, the owner SHOULD define:

-   maximum tolerable outage;
-   manual workaround if any;
-   transaction backlog handling;
-   customer communication;
-   reconciliation after restoration;
-   external partner coordination.

A technically restored platform with unreconciled business transactions
may still be operationally unsafe.

------------------------------------------------------------------------

## 44. Cross-Border Operations

ZuriBeans may conduct B2B operations across borders.

A market outage, customs integration outage or external
logistics/payment outage does not necessarily constitute Baobab regional
disaster.

Business-continuity plans SHALL distinguish:

``` text
Baobab infrastructure disaster
External provider outage
Market/regulatory disruption
Business operational disruption
```

Each may require a different response.

------------------------------------------------------------------------

## 45. Tenant Isolation During DR

Recovery SHALL preserve IsolationProfile and legal-entity boundaries.

ZuriBeans recovery SHALL NOT grant access to Thamani data or
credentials.

A DR environment SHALL not weaken tenant isolation simply because it is
temporary.

------------------------------------------------------------------------

## 46. IsolationProfile Escalation

A tenant with stronger recovery requirements MAY receive a stronger
IsolationProfile and DR tier.

Examples:

-   dedicated database recovery;
-   dedicated backup vault;
-   warm standby;
-   dedicated environment.

Tenant SHALL not receive dedicated DR infrastructure by default.

------------------------------------------------------------------------

## 47. Shared Infrastructure Recovery

For shared infrastructure, recovery SHALL consider all dependent tenants
before cutover.

A recovery decision for ZuriBeans SHALL not corrupt or roll back Thamani
or another tenant sharing the same physical resource.

Logical tenant-level recovery and regional infrastructure recovery SHALL
remain distinct.

------------------------------------------------------------------------

## 48. External Dependencies

DR planning SHALL inventory critical external dependencies such as:

-   DNS;
-   GitHub/GHCR;
-   payment providers;
-   identity providers;
-   customs/tax services;
-   email/SMS providers;
-   logistics integrations.

For each critical dependency, continuity behaviour SHALL be known:

``` text
Retry
Degrade
Queue
Manual process
Alternate provider
Fail closed
```

------------------------------------------------------------------------

## 49. GitHub Dependency

GitHub Actions is the normal deployment automation path, but DR SHALL
consider GitHub unavailability.

Recovery SHALL document which operations can be performed through
controlled local/alternative tooling using the same Terraform and
immutable artifacts without bypassing governance.

Emergency tooling SHALL remain auditable and least privilege.

------------------------------------------------------------------------

## 50. Observability During DR

The recovery environment SHALL expose sufficient telemetry to determine
whether recovery is succeeding.

At minimum:

-   infrastructure creation status;
-   service/task health;
-   database health;
-   gateway health;
-   authentication;
-   error rates;
-   critical synthetic journeys.

Observability SHALL not be deferred until after customer cutover.

------------------------------------------------------------------------

## 51. Recovery Health Gate

Before traffic cutover:

``` text
Infrastructure Ready
      │
      ▼
Data Restored
      │
      ▼
IAM / CP / Gateway Healthy
      │
      ▼
Critical Services Healthy
      │
      ▼
Synthetic Tests Pass
      │
      ▼
Business Reconciliation Acceptable
      │
      ▼
Authorised Cutover
```

"Containers are running" is insufficient.

------------------------------------------------------------------------

## 52. Failback

Returning to the original region after DR SHALL be treated as another
controlled migration.

Failback SHALL address:

-   data divergence;
-   queued events;
-   external transactions;
-   DNS;
-   secrets;
-   active writers;
-   rollback;
-   verification.

Automatic immediate failback is discouraged.

------------------------------------------------------------------------

## 53. Split-Brain Prevention

Regional DR SHALL ensure only the intended region performs authoritative
writes unless the domain explicitly supports multi-writer operation.

``` text
Primary Writer
      │
      X disaster
      │
      ▼
Promote Recovery Writer
```

The architecture SHALL prevent accidental simultaneous independent
authoritative writers.

------------------------------------------------------------------------

## 54. DR Testing

DR SHALL be exercised regularly.

Tests SHOULD progress through:

1.  tabletop exercise;
2.  component recovery;
3.  isolated regional reconstruction;
4.  data restore;
5.  application verification;
6.  controlled end-to-end DR exercise.

A written plan that has never been exercised SHALL not be described as a
proven DR capability.

------------------------------------------------------------------------

## 55. DR Exercise Evidence

Each exercise SHALL record:

-   scenario;
-   start/end time;
-   measured RTO;
-   achieved RPO;
-   failed steps;
-   manual interventions;
-   data-integrity findings;
-   security findings;
-   runbook corrections;
-   follow-up actions.

------------------------------------------------------------------------

## 56. Game Days

Controlled resilience game days SHOULD test failures that normal HA is
expected to absorb before escalating to full DR.

Examples:

-   ECS task loss;
-   AZ scheduling disruption;
-   RDS failover;
-   cache failover;
-   RabbitMQ node disruption;
-   APISIX task loss;
-   etcd member loss.

This validates the boundary between HA and DR.

------------------------------------------------------------------------

## 57. Production Go-Live

Before initial ZuriBeans Production go-live, the platform SHALL
demonstrate:

-   Multi-AZ architecture for critical components where required;
-   tested RDS failover behaviour where applicable;
-   tested critical backups/restores;
-   etcd quorum and snapshot recovery;
-   RabbitMQ node-failure/reconnect behaviour;
-   APISIX instance-loss tolerance;
-   documented regional disaster procedure;
-   identified recovery tiers;
-   documented recovery dependencies;
-   recovery identities and break-glass access;
-   artifact availability;
-   business continuity ownership.

A full warm secondary region is not mandatory unless approved RTO/RPO
requires it.

------------------------------------------------------------------------

## 58. Regional DR Readiness Levels

Baobab MAY track maturity as:

  -----------------------------------------------------------------------
  Level                               Meaning
  ----------------------------------- -----------------------------------
  **DR-Aware**                        architecture/runbooks/backups
                                      support future recovery

  **DR-Reconstructable**              secondary-region
                                      infrastructure/data restore tested

  **DR-Ready**                        recovery objectives demonstrated in
                                      exercise

  **DR-Continuous**                   regularly exercised and maintained
  -----------------------------------------------------------------------

Marketing or contractual claims SHALL not exceed demonstrated maturity.

------------------------------------------------------------------------

## 59. Cost Governance

DR architecture SHALL explicitly account for cost.

Major cost drivers include:

-   duplicate compute;
-   replicated databases;
-   cross-region data transfer;
-   duplicate brokers/caches;
-   backup copies;
-   Private CA/KMS;
-   observability;
-   idle standby capacity.

Recovery requirements SHALL justify the chosen cost.

------------------------------------------------------------------------

## 60. Production Verification

Before declaring the architecture Production-ready, verification SHALL
demonstrate:

-   critical services are mapped to recovery tiers;
-   HA and DR failure domains are documented;
-   critical ECS services tolerate task loss;
-   required services span AZs;
-   managed data failover behaviour is understood/tested;
-   backups meet recovery design;
-   Terraform can reconstruct foundational infrastructure;
-   immutable artifacts remain available for recovery;
-   recovery IAM/KMS/secrets/certificates are usable;
-   tenant isolation survives recovery;
-   DNS cutover procedure exists;
-   split-brain prevention is documented;
-   failback procedure exists;
-   DR runbooks identify owners;
-   a recovery exercise has produced evidence;
-   ZuriBeans continuity requirements are explicitly accepted.

------------------------------------------------------------------------

## 61. Rejected Alternatives

  ------------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- ------------------------
  Multi-AZ = DR           Rejected                Does not protect
                                                  regional failure

  Backup = DR             Rejected                Restore/reconstruction
                                                  time matters

  Active-active           Rejected                Excessive
  multi-region by default                         complexity/cost

  Cross-region etcd       Rejected                Latency/consensus
  quorum by default                               complexity

  Cross-region RabbitMQ   Rejected                Wrong recovery model
  cluster by default                              

  One DR tier for every   Rejected                Criticality differs
  service                                         

  Automatic full-region   Rejected                Risk of false/unsafe
  failover initially                              cutover

  Manual console          Rejected                Non-repeatable
  reconstruction as                               
  primary plan                                    

  Rebuild application     Rejected                Use approved immutable
  source during disaster                          artifacts

  DR environment with     Rejected                Isolation remains
  weaker tenant security                          mandatory

  Immediate automatic     Rejected                Data divergence risk
  failback                                        

  DR plan without         Rejected                Capability unproven
  exercises                                       

  Market = AWS region     Rejected                Commercial and
                                                  infrastructure placement
                                                  differ
  ------------------------------------------------------------------------

------------------------------------------------------------------------

## 62. Consequences

### Positive

-   Clear separation of HA, backup, DR and business continuity.
-   Multi-AZ resilience for ordinary infrastructure failures.
-   Avoids premature active-active complexity.
-   Recovery strategy can scale from cold to warm based on actual RTO.
-   Infrastructure-as-code becomes a recovery asset.
-   Security, KMS, secrets and certificates are included in recovery.
-   Tenant/legal-entity isolation remains intact during disaster.
-   ZuriBeans can go live without unnecessarily duplicating the whole
    platform into a second region.
-   Provides a path toward demonstrable regional resilience.

### Costs

-   DR exercises require time and infrastructure.
-   Cross-region backup/artifact strategies add cost.
-   Warm standby, if required, can materially increase spend.
-   Failover/failback requires careful data reconciliation.
-   Business teams must participate in continuity planning.
-   External dependency continuity cannot be solved solely by
    infrastructure.

These costs are accepted.

------------------------------------------------------------------------

## 63. Decision Rules

> **Baobab SHALL distinguish high availability, backup/recovery,
> disaster recovery and business continuity as separate concerns.**

> **Critical Production workloads SHOULD use Multi-AZ architecture where
> supported and justified by their SLO.**

> **Multi-AZ SHALL NOT be described as regional disaster recovery.**

> **Regional DR SHALL initially prefer active-passive recovery rather
> than active-active multi-region architecture.**

> **Cold, pilot-light or warm recovery SHALL be selected according to
> approved RPO/RTO and cost.**

> **Terraform and immutable application artifacts SHALL be core
> regional-reconstruction mechanisms.**

> **Regional recovery SHALL preserve IAM, KMS, secret, certificate and
> tenant-isolation controls.**

> **RabbitMQ and etcd SHALL NOT be stretched across regions by default;
> recovery SHALL use their approved reconstruction/restore models.**

> **Regional failover SHALL initially require controlled disaster
> declaration and authorised cutover unless automation is later proven
> safe.**

> **Recovery SHALL prevent split-brain authoritative writes.**

> **Failback SHALL be controlled and shall address data divergence and
> reconciliation.**

> **A DR plan SHALL NOT be considered proven until exercised and
> measured.**

> **ZuriBeans Production go-live SHALL require documented
> regional-disaster procedures, but a permanently warm second region is
> required only if accepted recovery objectives demand it.**

------------------------------------------------------------------------

## 64. Implementation Implications

Implementation SHALL progressively establish:

``` text
Resilience
│
├── High Availability
│   ├── multi-AZ ECS
│   ├── RDS failover
│   ├── ElastiCache failover
│   ├── RabbitMQ cluster
│   ├── APISIX redundancy
│   └── etcd quorum
│
├── Disaster Recovery
│   ├── recovery tiers
│   ├── secondary-region decision
│   ├── cold/pilot-light/warm pattern
│   ├── backup copies
│   ├── artifact availability
│   └── Terraform reconstruction
│
├── Security Continuity
│   ├── IAM
│   ├── KMS
│   ├── secrets
│   └── certificates
│
├── Traffic Recovery
│   ├── Route 53
│   ├── health validation
│   └── controlled cutover
│
└── Business Continuity
    ├── disaster declaration
    ├── command structure
    ├── runbooks
    ├── reconciliation
    ├── failback
    └── exercises
```

The exact secondary-region architecture SHALL be implemented only after
recovery objectives and regional AWS capabilities are validated.

------------------------------------------------------------------------

## 65. Current Technical Validation

Implementation SHALL revalidate current AWS capabilities before
committing the DR topology, including:

-   RDS Multi-AZ and cross-region recovery options;
-   AWS Backup cross-region/cross-account capabilities;
-   S3 replication/versioning/Object Lock;
-   ECR replication;
-   KMS multi-Region keys and regional key policies;
-   Secrets Manager replication where used;
-   Route 53 failover mechanisms;
-   ECS/Fargate regional service availability;
-   Amazon MQ regional capabilities;
-   ElastiCache regional recovery options;
-   service availability in `af-south-1` and the selected recovery
    region.

Feature availability SHALL not be assumed from another AWS region.

------------------------------------------------------------------------

## 66. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0020 --- CI/CD and Infrastructure Change Governance**

It shall define:

-   pull-request validation;
-   Terraform formatting/validation/linting;
-   security and policy scanning;
-   infrastructure plans;
-   plan review;
-   GitHub OIDC;
-   protected environments;
-   Production approvals;
-   apply governance;
-   reusable workflows;
-   action pinning;
-   dependency updates;
-   concurrency;
-   drift detection;
-   emergency changes;
-   audit evidence;
-   and the rule that untrusted pull requests may validate/plan but
    SHALL NOT mutate Production.
