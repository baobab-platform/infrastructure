# ADR-Infra-0009 --- APISIX and etcd Production Architecture

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0001 --- Environment Provisioner Boundary
    -   ADR-Infra-0005 --- Network and Trust-Zone Architecture
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0008 --- DNS, TLS, Edge and API Gateway Architecture
-   **Follow-on:** ADR-Infra-0010 --- PostgreSQL Production Architecture

------------------------------------------------------------------------

## 1. Context

APISIX is Baobab's API gateway. It sits between the AWS-managed edge and
private Baobab workloads and must support:

-   ZuriBeans B2B traffic;
-   future digital estates such as Thamani;
-   Baobab platform APIs;
-   capability-aware routing;
-   authentication integration;
-   rate and gateway policy;
-   controlled dynamic route reconciliation;
-   production-grade availability and observability.

Apache APISIX uses etcd as its configuration store in traditional
deployment mode.

The local Docker Compose environment currently runs a single APISIX
instance with a single unauthenticated etcd instance on an internal
network. That topology is explicitly development-only and SHALL NOT be
promoted directly into Production.

Production must protect both the APISIX administrative plane and the
etcd configuration store while avoiding a design in which gateway
failure becomes an avoidable platform-wide outage.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL operate APISIX in its **etcd-backed traditional
configuration model** for the initial production architecture.

Production SHALL use:

-   multiple APISIX gateway instances;
-   private APISIX runtime networking;
-   a private, authenticated, TLS-protected etcd cluster;
-   an odd-number etcd quorum, initially **three members**;
-   durable etcd storage;
-   separate APISIX traffic and administrative access paths;
-   restricted APISIX Admin API access;
-   controlled dynamic configuration reconciliation;
-   tested etcd backup and restore;
-   independent monitoring of APISIX and etcd.

The architecture SHALL preserve the option to revisit APISIX deployment
mode later, but SHALL NOT introduce a different gateway-control model
without an Accepted ADR.

------------------------------------------------------------------------

## 3. Production Topology

``` text
                       Internet
                          │
                          ▼
                 Route 53 / TLS / WAF
                          │
                          ▼
                         ALB
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
          APISIX A                 APISIX B
              │                       │
              └───────────┬───────────┘
                          │
                  private upstreams
                          │
                          ▼
                    Baobab Services


                APISIX Configuration
                          │
                          ▼
                 ┌─────────────────┐
                 │   etcd quorum   │
                 │                 │
                 │ etcd-1          │
                 │ etcd-2          │
                 │ etcd-3          │
                 └─────────────────┘
```

APISIX and etcd SHALL remain inside private network boundaries.

------------------------------------------------------------------------

## 4. APISIX Availability

Production SHALL run at least two APISIX gateway tasks/instances for
workloads requiring production availability.

They SHOULD be distributed across Availability Zones.

``` text
              ALB
               │
       ┌───────┴───────┐
       ▼               ▼
     AZ-A             AZ-B
   APISIX A         APISIX B
```

Failure of one gateway instance SHALL not require DNS changes or manual
failover.

The load balancer SHALL remove unhealthy APISIX instances from service.

------------------------------------------------------------------------

## 5. APISIX Compute

APISIX SHOULD run on the production compute platform selected by
ADR-Infra-0006 where compatibility and operational verification confirm
suitability.

APISIX tasks SHALL:

-   run privately;
-   avoid public task IPs;
-   use dedicated security groups;
-   use immutable container artifacts;
-   expose only required gateway ports;
-   emit logs and metrics;
-   receive explicit CPU/memory sizing.

APISIX SHALL not share a task definition with unrelated Baobab services.

------------------------------------------------------------------------

## 6. Traffic Plane

The APISIX traffic plane SHALL accept traffic only from approved ingress
sources and approved internal callers.

``` text
ALB Security Group
        │
        ▼
APISIX Traffic Security Group
        │
        ▼
Approved Upstream Security Group
```

The traffic listener SHALL not provide administrative privileges.

------------------------------------------------------------------------

## 7. Administrative Plane

The APISIX Admin API SHALL be private.

``` text
Public Internet
      │
      X
APISIX Admin API

Approved Reconciler / Operator
      │
      ▼
Private Management Path
      │
      ▼
APISIX Admin API
```

Administrative access SHALL be limited to explicitly authorised
identities and network paths.

Digital estates SHALL not receive APISIX administrative credentials.

------------------------------------------------------------------------

## 8. Admin Credentials

APISIX administrative credentials SHALL be stored in the approved
secrets-management system.

They SHALL NOT be:

-   committed to Git;
-   embedded in container images;
-   placed in plaintext Terraform variables;
-   distributed to tenant applications;
-   written into CI logs.

Credential rotation SHALL be supported operationally.

The dedicated secrets ADR governs lifecycle details.

------------------------------------------------------------------------

## 9. Configuration Ownership

Infrastructure owns APISIX runtime availability and baseline
configuration.

Dynamic application/gateway intent SHALL remain owned by the appropriate
Baobab control mechanisms.

``` text
nabhold/infrastructure
        │
        ├── APISIX runtime
        ├── networking
        ├── etcd
        ├── baseline security
        └── bootstrap configuration
                 │
                 ▼
               APISIX
                 ▲
                 │
      approved desired-state reconciliation
                 │
            baobab-cp
```

Terraform SHALL NOT become the routine lifecycle manager for dynamic
tenant routes.

------------------------------------------------------------------------

## 10. Reconciliation Boundary

Baobab Control Plane MAY reconcile approved gateway resources through a
scoped gateway-management interface.

The reconciler SHALL:

-   authenticate strongly;
-   operate with least privilege;
-   validate desired state;
-   be idempotent;
-   preserve tenant/capability boundaries;
-   produce auditable changes;
-   avoid direct etcd manipulation.

``` text
Desired Gateway State
        │
        ▼
Control Plane Reconciler
        │
        ▼
APISIX Admin API
        │
        ▼
       etcd
```

Control Plane code SHALL NOT write directly to etcd.

------------------------------------------------------------------------

## 11. etcd Role

etcd is a critical gateway configuration dependency.

It SHALL be treated as production data infrastructure rather than an
incidental sidecar.

etcd contains configuration required for APISIX operation and therefore
requires:

-   quorum;
-   persistence;
-   encryption in transit;
-   authentication;
-   backup;
-   restore procedures;
-   monitoring;
-   controlled upgrades.

------------------------------------------------------------------------

## 12. etcd Quorum

Production SHALL initially use **three etcd voting members**.

``` text
              etcd cluster
          ┌───────┼───────┐
          ▼       ▼       ▼
       etcd-1   etcd-2   etcd-3
          \       │       /
           \      │      /
            └── quorum ─┘
```

The cluster requires majority quorum for writes.

A three-member cluster tolerates loss of one member while retaining
quorum.

Two-member production etcd clusters are prohibited because they provide
no useful quorum-failure advantage.

------------------------------------------------------------------------

## 13. etcd Placement

etcd members SHOULD be distributed across Availability Zones where the
selected compute/storage architecture supports this safely.

The placement objective is to avoid a single-AZ failure removing the
entire configuration quorum.

The exact member placement SHALL respect etcd latency and storage
requirements.

------------------------------------------------------------------------

## 14. etcd Compute Decision

etcd SHALL NOT automatically inherit the Fargate choice simply because
APISIX runs on Fargate.

etcd requires durable local persistence and predictable member
identity/lifecycle.

Implementation SHALL select an AWS execution model that satisfies:

-   durable storage;
-   stable member lifecycle;
-   multi-AZ placement;
-   backup/restore;
-   supported etcd semantics;
-   operational simplicity.

The selected implementation MAY use dedicated compute rather than
Fargate if required.

This exception does not overturn ADR-Infra-0006's default compute
decision for replaceable application workloads.

------------------------------------------------------------------------

## 15. etcd Persistence

Each etcd member SHALL use durable storage appropriate to the selected
AWS execution model.

etcd data SHALL NOT depend solely on ephemeral container storage.

``` text
etcd member
    │
    ▼
durable volume
    │
    ▼
member restart/recovery
```

Storage performance and latency SHALL be monitored because etcd health
depends materially on storage behaviour.

------------------------------------------------------------------------

## 16. etcd Network Isolation

etcd client and peer ports SHALL be private.

Only:

-   APISIX clients;
-   etcd cluster peers;
-   authorised backup/administration mechanisms

SHALL reach etcd.

``` text
APISIX SG ─────► etcd client endpoint
etcd SG   ◄────► etcd peer endpoint
Mgmt SG   ─────► controlled administration
```

etcd SHALL never be Internet-facing.

------------------------------------------------------------------------

## 17. etcd TLS

Production etcd SHALL use TLS for:

-   client-to-etcd communication;
-   member-to-member peer communication.

Mutual TLS SHOULD be used for etcd peer and administrative/client
authentication where supported by the final implementation.

``` text
APISIX
  │ TLS/authenticated
  ▼
etcd

etcd-1
  │ mTLS
  ▼
etcd-2 / etcd-3
```

The local unauthenticated HTTP configuration SHALL not be carried into
Production.

------------------------------------------------------------------------

## 18. etcd Authentication

Production etcd SHALL require authenticated access.

Anonymous configuration writes are prohibited.

Access identities SHALL distinguish, where practical:

-   APISIX runtime access;
-   backup/restore administration;
-   cluster administration.

Direct broad administrative credentials SHALL not be embedded in APISIX
application configuration.

------------------------------------------------------------------------

## 19. etcd Direct Access

Baobab applications and digital estates SHALL NOT access etcd directly.

Prohibited:

``` text
ZuriBeans ─────► etcd
Trade ─────────► etcd
Thamani ───────► etcd
```

Required:

``` text
Digital Estate
      │
      ▼
Approved Baobab Control/API
      │
      ▼
APISIX Configuration Mechanism
      │
      ▼
etcd
```

etcd is infrastructure configuration storage, not a platform integration
API.

------------------------------------------------------------------------

## 20. Gateway Configuration Safety

Dynamic route changes SHALL be validated before they are committed.

Validation SHOULD include:

-   route uniqueness;
-   hostname/path correctness;
-   upstream existence;
-   forbidden administrative exposure;
-   authentication requirements;
-   capability ownership;
-   tenant/context constraints;
-   plugin policy.

A malformed tenant route SHALL not be allowed to hijack another digital
estate's hostname.

------------------------------------------------------------------------

## 21. Route Idempotency

Gateway reconciliation SHALL be idempotent.

Repeated application of the same desired state SHALL converge to the
same APISIX configuration.

``` text
Desired State A
      │
      ▼
Reconcile
      │
      ▼
Observed State A

repeat
      │
      ▼
Observed State A
```

Reconciliation SHALL not generate duplicate routes or plugins.

------------------------------------------------------------------------

## 22. Configuration Drift

Unexpected APISIX configuration outside the approved desired state SHALL
be considered drift.

The system SHOULD detect differences between:

``` text
Approved Desired Gateway State
              │
              ▼
            compare
              │
              ▼
Observed APISIX Configuration
```

Automatic destructive reconciliation SHALL be bounded by policy and
safety checks.

------------------------------------------------------------------------

## 23. APISIX Plugins

Only approved plugins SHALL be enabled in Production.

Plugin adoption SHALL consider:

-   security;
-   latency;
-   resource consumption;
-   configuration ownership;
-   operational support;
-   observability.

A plugin SHALL not be enabled globally merely because it ships with
APISIX.

------------------------------------------------------------------------

## 24. Authentication Plugins

APISIX authentication integration SHALL align with `baobab-iam`.

Gateway authentication MAY validate tokens or invoke approved identity
mechanisms.

APISIX SHALL NOT become the authoritative user or role store.

``` text
Client
  │
  ▼
APISIX authentication
  │
  ▼
Baobab IAM trust
  │
  ▼
Application authorization
```

------------------------------------------------------------------------

## 25. Rate and Protection Policies

APISIX MAY enforce:

-   route rate limits;
-   client quotas;
-   request-size limits;
-   timeout policy;
-   retry policy;
-   circuit protection where appropriate.

Policies SHALL be explicit and workload-aware.

Retries SHALL be particularly conservative for non-idempotent
operations.

------------------------------------------------------------------------

## 26. Upstream Discovery

APISIX SHALL route to stable service discovery/load-balancing endpoints
rather than individual ephemeral task IPs where practical.

``` text
APISIX
  │
  ▼
Stable Internal Service Endpoint
  │
  ▼
ECS Tasks
```

The gateway SHALL tolerate routine ECS task replacement.

------------------------------------------------------------------------

## 27. Health

APISIX health SHALL be monitored independently from upstream health.

Operational status includes:

-   APISIX process/task health;
-   gateway listener availability;
-   etcd connectivity;
-   route/configuration availability;
-   upstream reachability;
-   latency/error rate.

A running APISIX process with broken etcd connectivity SHALL not
automatically be considered fully healthy.

------------------------------------------------------------------------

## 28. etcd Failure Behaviour

APISIX may continue serving existing configuration during some etcd
disruptions, but the platform SHALL NOT rely on indefinite operation
without etcd.

Operational behaviour SHALL distinguish:

``` text
etcd healthy
   │
   ├── traffic + config changes available
   │
etcd degraded/unavailable
   │
   ├── preserve safe existing traffic where APISIX supports it
   └── block/alert configuration changes
```

Gateway reconciliation SHALL fail safely when etcd/configuration control
is unavailable.

------------------------------------------------------------------------

## 29. Quorum Loss

If etcd loses quorum:

1.  automated configuration mutation SHALL stop;
2.  operators SHALL establish member health;
3.  unsafe member replacement SHALL be avoided;
4.  recovery SHALL follow the etcd runbook;
5.  gateway traffic health SHALL be monitored separately.

Quorum SHALL not be "repaired" by casually starting unrelated empty
members.

------------------------------------------------------------------------

## 30. Backup

etcd snapshots SHALL be taken on an approved schedule.

Snapshots SHALL be:

-   encrypted;
-   stored outside the etcd member's local failure domain;
-   access-controlled;
-   retained according to policy;
-   monitored for successful completion.

``` text
etcd quorum
    │
    ▼
Snapshot
    │
    ▼
Encrypted Backup Storage
    │
    ▼
Retention
```

Detailed platform-wide backup policy is governed by ADR-Infra-0018.

------------------------------------------------------------------------

## 31. Restore Testing

An untested etcd snapshot SHALL not be considered a proven recovery
capability.

Restore tests SHALL verify:

-   snapshot integrity;
-   cluster reconstruction;
-   member identity/configuration;
-   APISIX reconnection;
-   route availability;
-   gateway correctness after recovery.

Production restore testing SHALL occur in an isolated recovery
environment where practical.

------------------------------------------------------------------------

## 32. Disaster Recovery

etcd multi-AZ quorum protects against selected infrastructure failures
but does not constitute regional disaster recovery.

Regional recovery requirements are governed by ADR-Infra-0019.

The etcd backup design SHALL nevertheless support reconstruction in a
recovery environment.

------------------------------------------------------------------------

## 33. Upgrades

APISIX and etcd upgrades SHALL be deliberate and independently planned.

Before upgrade:

-   review compatibility;
-   review release notes;
-   validate in Development;
-   validate in Staging;
-   verify backup;
-   define rollback.

etcd quorum SHALL be preserved during rolling member maintenance.

Major APISIX or etcd upgrades SHALL not be combined casually with
unrelated network or application changes.

------------------------------------------------------------------------

## 34. Version Pinning

Production APISIX and etcd images/packages SHALL use approved immutable
versions.

Mutable `latest` tags are prohibited.

Dependency automation MAY propose upgrades, but Production adoption
requires validation.

------------------------------------------------------------------------

## 35. Observability

APISIX telemetry SHOULD include:

-   request rate;
-   latency;
-   status-code distribution;
-   upstream latency;
-   gateway errors;
-   rejected requests;
-   active connections;
-   route/plugin failures.

etcd telemetry SHOULD include:

-   leader status;
-   member health;
-   quorum/member availability;
-   proposal failures;
-   database size;
-   storage latency;
-   fsync latency;
-   network peer health.

Alerts SHALL focus on actionable conditions.

------------------------------------------------------------------------

## 36. Logging

APISIX access/error logs SHALL be centrally collected.

Logs SHOULD include appropriate correlation information while excluding:

-   passwords;
-   bearer tokens;
-   API secrets;
-   sensitive request bodies unless explicitly approved.

etcd administrative/security logs SHALL be retained according to
infrastructure audit policy.

------------------------------------------------------------------------

## 37. Capacity

APISIX capacity SHALL be tested against expected request volume and
latency.

Scaling SHOULD be horizontal where practical.

etcd SHALL be sized for configuration workload rather than customer
request volume because normal request traffic does not traverse etcd.

``` text
Customer Requests
      │
      ▼
    APISIX
      │
      X
   etcd request path

Configuration Changes
      │
      ▼
    APISIX
      │
      ▼
     etcd
```

etcd SHALL NOT be placed in the synchronous customer request path by
custom Baobab logic.

------------------------------------------------------------------------

## 38. Tenant Isolation

A shared APISIX deployment MAY route multiple digital estates.

Tenant isolation SHALL rely on:

-   validated route ownership;
-   authentication;
-   application authorization;
-   tenant context;
-   capability bindings;
-   data isolation.

Tenant SHALL NOT imply a dedicated APISIX or etcd cluster.

Dedicated gateway infrastructure MAY be introduced only where an
accepted IsolationProfile or operational requirement justifies it.

------------------------------------------------------------------------

## 39. ZuriBeans Go-Live

ZuriBeans SHALL validate the first production APISIX path:

``` text
ZuriBeans Customer
       │
       ▼
      ALB
       │
       ▼
 APISIX Cluster
       │
       ├──► ZuriBeans
       ├──► IAM
       ├──► Trade
       └──► approved capabilities
```

Gateway configuration for ZuriBeans SHALL not grant access to unrelated
Thamani or future-tenant routes.

The ZuriBeans go-live test SHALL include gateway-instance failure and
configuration-control failure scenarios.

------------------------------------------------------------------------

## 40. Operational Runbooks

Production SHALL have runbooks for at least:

-   APISIX task failure;
-   APISIX deployment rollback;
-   Admin API credential rotation;
-   invalid route recovery;
-   etcd member failure;
-   etcd quorum loss;
-   etcd snapshot creation;
-   etcd restore;
-   certificate/TLS failure between APISIX and etcd;
-   gateway configuration drift.

Runbooks SHALL identify when human intervention is required.

------------------------------------------------------------------------

## 41. Security Invariants

The architecture SHALL maintain:

1.  APISIX traffic plane private behind approved ingress;
2.  APISIX Admin API private;
3.  etcd private;
4.  authenticated etcd access;
5.  encrypted etcd client/peer communication;
6.  no direct tenant access to etcd;
7.  no direct Control Plane writes to etcd;
8.  least-privilege gateway reconciliation;
9.  immutable runtime artifacts;
10. auditable configuration changes.

------------------------------------------------------------------------

## 42. Verification

Production readiness SHALL verify:

-   multiple APISIX instances serve through ALB;
-   one APISIX instance can fail without total gateway outage;
-   Admin API is not publicly reachable;
-   etcd is not publicly reachable;
-   etcd quorum survives one-member loss;
-   unauthenticated etcd access fails;
-   TLS-protected etcd communication works;
-   APISIX reconnects appropriately after etcd disruption;
-   snapshots can be restored;
-   invalid routes cannot hijack another estate;
-   configuration changes are auditable;
-   gateway metrics and logs are available.

A healthy `/status` endpoint alone is insufficient.

------------------------------------------------------------------------

## 43. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Single APISIX instance  Rejected                Avoidable gateway SPOF
  in Production                                   

  Single etcd instance    Rejected                Configuration-store
                                                  SPOF

  Two-member etcd cluster Rejected                Poor quorum-failure
                                                  characteristics

  Unauthenticated etcd    Rejected                Production security
                                                  risk

  Public etcd             Rejected                Critical configuration
                                                  exposure

  Public APISIX Admin API Rejected                Administrative-plane
                                                  exposure

  Control Plane writes    Rejected                Tight coupling and
  directly to etcd                                unsafe ownership

  Terraform manages every Rejected                Wrong lifecycle
  dynamic route                                   boundary

  Tenant-specific gateway Rejected                Tenant does not imply
  by default                                      physical gateway

  Ephemeral-only etcd     Rejected                Configuration
  storage                                         durability risk

  etcd in customer        Rejected                Unnecessary critical
  request path                                    dependency

  Promote local Compose   Rejected                Development topology
  topology to Production                          lacks production
                                                  controls

  Automatic major         Rejected                Gateway/configuration
  upgrades                                        compatibility risk
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 44. Consequences

### Positive

-   Removes APISIX single-instance failure risk.
-   Protects gateway administration.
-   Provides resilient etcd configuration storage.
-   Preserves dynamic Control Plane reconciliation.
-   Prevents direct Control Plane/tenant coupling to etcd.
-   Provides explicit backup and restore requirements.
-   Supports shared gateway infrastructure across digital estates.
-   Gives ZuriBeans a production-grade gateway path.

### Costs

-   Three-member etcd requires additional compute and storage.
-   etcd becomes an explicitly operated stateful system.
-   TLS and authentication increase configuration complexity.
-   Backup and restore testing require operational effort.
-   APISIX/etcd compatibility must be managed during upgrades.
-   A non-Fargate execution model may be necessary for etcd.

These costs are accepted.

------------------------------------------------------------------------

## 45. Decision Rules

The following rules are authoritative:

> **Baobab SHALL use APISIX with an etcd-backed traditional
> configuration model for the initial Production architecture.**

> **Production SHALL run multiple APISIX gateway instances.**

> **Production etcd SHALL initially use a three-member quorum.**

> **etcd SHALL be private, authenticated, TLS-protected and durably
> persisted.**

> **APISIX traffic and administrative access SHALL be separated.**

> **The APISIX Admin API SHALL NOT be publicly accessible.**

> **Baobab applications and digital estates SHALL NOT access etcd
> directly.**

> **Baobab Control Plane SHALL reconcile gateway intent through an
> approved APISIX management interface and SHALL NOT write directly to
> etcd.**

> **Terraform SHALL own gateway infrastructure and bootstrap
> configuration, not the routine lifecycle of dynamic tenant routes.**

> **etcd SHALL NOT be placed in the synchronous customer request path by
> Baobab application logic.**

> **etcd backups SHALL be tested through restoration.**

> **Tenant SHALL NOT imply dedicated APISIX or etcd infrastructure.**

------------------------------------------------------------------------

## 46. Implementation Implications

Implementation SHALL introduce production infrastructure capable of
expressing:

``` text
APISIX
├── multiple gateway instances
├── private task networking
├── traffic-plane security group
├── private Admin API path
├── immutable version
├── secrets integration
├── logs
├── metrics
└── health checks

etcd
├── three voting members
├── durable member storage
├── private client networking
├── private peer networking
├── TLS
├── authentication
├── encrypted snapshots
├── monitoring
└── restore tooling
```

Implementation SHALL NOT assume that the current local single-node etcd
configuration is an acceptable Production template.

The exact etcd AWS compute/storage implementation SHALL be selected only
after validating etcd persistence and member-lifecycle requirements
against available AWS execution models.

------------------------------------------------------------------------

## 47. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0010 --- PostgreSQL Production Architecture**

It shall define:

-   managed PostgreSQL deployment;
-   PostgreSQL 17 baseline;
-   RDS/Aurora decision;
-   multi-AZ availability;
-   database and schema isolation;
-   encryption;
-   TLS;
-   credentials and IAM integration;
-   connection pooling;
-   backups;
-   point-in-time recovery;
-   maintenance and upgrades;
-   monitoring;
-   engine-specific database ownership;
-   tenant isolation;
-   and the database requirements necessary for ZuriBeans and the wider
    Baobab platform.
