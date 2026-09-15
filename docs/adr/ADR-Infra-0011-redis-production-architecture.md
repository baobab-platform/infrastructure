# ADR-Infra-0011 --- Redis Production Architecture

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0005 --- Network and Trust-Zone Architecture
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0010 --- PostgreSQL Production Architecture
-   **Follow-on:** ADR-Infra-0012 --- RabbitMQ Production Architecture

------------------------------------------------------------------------

## 1. Context

Baobab requires a low-latency in-memory data service for approved
workloads such as:

-   disposable projections;
-   application caches;
-   bounded session or token-related transient state where the owning
    application permits it;
-   rate-limit counters;
-   short-lived coordination data;
-   derived lookup data;
-   other explicitly non-authoritative runtime state.

The local development platform currently uses Redis 7 with AOF enabled
and `noeviction`. That configuration is useful for local development but
SHALL NOT be copied directly into Production without considering
managed-service capabilities, failure semantics, memory policy and
workload purpose.

Baobab's authoritative platform state remains in systems designed for
durable ownership, principally PostgreSQL and domain-specific durable
stores.

Redis SHALL not silently become an undocumented system of record.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use **Amazon ElastiCache** as the default managed in-memory
production service.

For new infrastructure, the preferred engine SHALL be **Valkey** where
compatibility with the consuming Baobab workload is verified.

Redis OSS-compatible ElastiCache deployments MAY be retained or selected
where an application, vendor engine, module, licensing constraint or
verified compatibility requirement makes Valkey inappropriate.

The platform SHALL treat the service primarily as **disposable or
reconstructable state**, unless a specific workload ADR explicitly
establishes stronger persistence requirements.

------------------------------------------------------------------------

## 3. Why Managed ElastiCache

``` text
Baobab Workloads
      │
      ▼
Private Cache Endpoint
      │
      ▼
Amazon ElastiCache
      │
      ├── managed nodes
      ├── replication
      ├── failover
      ├── monitoring
      ├── encryption
      └── maintenance
```

Baobab SHALL not self-host Redis/Valkey on ECS/Fargate merely to
standardise on container compute.

------------------------------------------------------------------------

## 4. Engine Strategy

The engine-selection flow SHALL be:

``` text
New Cache Requirement
        │
        ▼
Valkey-compatible?
   │            │
  Yes           No
   │            │
   ▼            ▼
Valkey       Verify Redis OSS
preferred    requirement
                 │
                 ▼
           Approved exception
```

Engine choice SHALL be recorded in infrastructure configuration.

Applications SHALL not depend unnecessarily on implementation-specific
features that prevent future compatible engine evolution.

------------------------------------------------------------------------

## 5. Role in Baobab

Redis/Valkey SHALL be considered a supporting runtime service.

Preferred:

``` text
Authoritative State
    PostgreSQL
        │
        ▼
Derived Projection
        │
        ▼
Redis / Valkey
```

If Redis/Valkey is lost, Baobab SHOULD be able to reconstruct affected
cache/projection state from authoritative sources wherever the workload
is classified as disposable.

------------------------------------------------------------------------

## 6. Authoritative-State Boundary

The following SHALL NOT be stored only in Redis/Valkey without an
explicitly accepted durability design:

-   canonical tenant records;
-   legal-entity master data;
-   orders;
-   financial ledger records;
-   payment truth;
-   inventory truth;
-   IAM identity truth;
-   contractual records;
-   irreversible workflow state;
-   canonical Control Plane mappings.

Redis/Valkey availability SHALL not redefine domain ownership.

------------------------------------------------------------------------

## 7. Production Topology

Critical Production caches SHALL use a replicated Multi-AZ topology with
automatic failover where supported and appropriate.

``` text
                  Application
                      │
                      ▼
               Primary Endpoint
                      │
              ┌───────┴───────┐
              ▼               ▼
           Primary          Replica
             AZ-A             AZ-B
```

A single-node Production deployment MAY be used only for explicitly
non-critical workloads whose loss and downtime are acceptable.

------------------------------------------------------------------------

## 8. Cluster Mode

Cluster mode SHALL be selected according to measured scale requirements.

Default initial preference:

``` text
Replication Group
     │
     ├── primary
     └── replica(s)
```

Cluster-mode sharding SHOULD be introduced when:

-   dataset size exceeds practical single-shard limits;
-   throughput requires horizontal partitioning;
-   measured scaling requirements justify additional operational
    complexity.

Cluster mode SHALL NOT be enabled merely because it exists.

------------------------------------------------------------------------

## 9. Network Placement

ElastiCache SHALL run in private Data Zone subnets.

``` text
Application Security Group
          │
          ▼
ElastiCache Security Group
```

Production cache nodes SHALL NOT be publicly reachable.

Ingress SHALL be limited to approved workload security groups and
required service ports.

------------------------------------------------------------------------

## 10. Encryption in Transit

Production connections SHALL use encryption in transit where supported
by the selected engine/topology.

``` text
Application
     │
     │ TLS
     ▼
ElastiCache
```

Applications SHALL verify and support the required TLS mode before
Production rollout.

Plaintext cross-zone cache traffic SHALL not be accepted merely because
the VPC is private.

------------------------------------------------------------------------

## 11. Encryption at Rest

Production ElastiCache data SHALL use encryption at rest where
supported.

AWS KMS-backed encryption SHOULD be used where the selected service mode
permits and where Baobab requires customer-managed key control.

Snapshots/backups, where enabled, SHALL follow the same confidentiality
requirements.

------------------------------------------------------------------------

## 12. Authentication

Production SHALL require authenticated cache access using the strongest
supported mechanism compatible with the selected engine and client.

Where supported, Baobab SHOULD use:

-   ElastiCache users/user groups and ACLs;
-   IAM authentication where operationally appropriate;
-   workload-specific access.

A single globally shared cache password across all Baobab services is
prohibited.

------------------------------------------------------------------------

## 13. Workload Identity

Cache access SHALL be scoped by workload.

``` text
Trade
  │
  └── approved cache identity

Control Plane
  │
  └── different approved identity
```

An application SHALL not receive access to unrelated cache namespaces
merely because it runs in the same VPC.

Network access and cache authentication SHALL both be enforced.

------------------------------------------------------------------------

## 14. Tenant Boundary

Tenant SHALL NOT imply an ElastiCache deployment.

Default:

``` text
Shared Managed Cache
       │
       ├── service boundary
       ├── tenant-aware key namespace
       ├── ACL/application isolation
       └── TTL/eviction policy
```

Dedicated cache infrastructure MAY be selected where an approved
IsolationProfile, regulatory requirement, scale boundary or workload
risk requires it.

------------------------------------------------------------------------

## 15. Legal-Entity Isolation

ZuriBeans and Thamani SHALL remain independent legal-entity contexts.

If a shared cache is used, key design and application authorization
SHALL prevent one estate from reading or overwriting another estate's
state.

Example conceptual namespace:

``` text
{service}:{tenant}:{purpose}:{identifier}
```

The exact key format belongs to the owning application contract, not
Terraform.

------------------------------------------------------------------------

## 16. Database Numbers Are Not Tenant Isolation

Redis logical database numbers SHALL NOT be treated as a strong tenant
or security boundary.

Baobab SHALL prefer:

-   separate service deployments where justified;
-   ACL/user separation;
-   key namespaces;
-   application-level tenant validation;
-   approved physical isolation profiles.

Logical DB selection alone is insufficient isolation.

------------------------------------------------------------------------

## 17. Key Naming

Applications SHALL define deterministic key conventions.

Keys SHOULD include enough context to avoid collisions, such as:

``` text
service
tenant/legal-entity context
purpose
resource identifier
version where needed
```

Example:

``` text
trade:tenant-123:price:sku-456
```

Sensitive business information SHOULD NOT be unnecessarily exposed in
human-readable key names.

------------------------------------------------------------------------

## 18. TTL Policy

Cache entries SHOULD have explicit TTLs unless a documented reason
requires otherwise.

``` text
Write Cache Entry
      │
      ▼
Explicit TTL
      │
      ▼
Expiry
      │
      ▼
Rebuild on Demand
```

Indefinite cache keys SHALL be exceptional and owned.

TTL selection SHALL consider:

-   freshness requirements;
-   rebuild cost;
-   upstream load;
-   business correctness;
-   memory consumption.

------------------------------------------------------------------------

## 19. Eviction Policy

Eviction policy SHALL be selected according to workload semantics.

A universal `noeviction` policy SHALL NOT be imposed across Production.

Decision flow:

``` text
Memory Pressure
     │
     ▼
Can data be safely evicted?
   │               │
  Yes              No
   │               │
   ▼               ▼
Select suitable   Treat as stronger
eviction policy   state requirement
                  and redesign/size
```

A workload that cannot tolerate eviction SHALL not casually be labelled
a cache.

------------------------------------------------------------------------

## 20. Memory Sizing

Production capacity SHALL account for:

-   steady-state dataset;
-   peak dataset;
-   replication overhead;
-   fragmentation;
-   connection overhead;
-   failover;
-   growth margin.

Memory utilisation SHALL be monitored before reaching conditions that
trigger widespread eviction or write failures.

------------------------------------------------------------------------

## 21. Hot-Key Risk

Applications SHOULD avoid designs where one key receives
disproportionate traffic.

Hot keys can create localised performance bottlenecks even when
aggregate cache capacity appears healthy.

High-volume workloads SHALL test key distribution during staging/load
testing.

------------------------------------------------------------------------

## 22. Large Values

Applications SHOULD avoid using Redis/Valkey as a store for
unnecessarily large objects.

Large values increase:

-   network transfer;
-   memory pressure;
-   replication cost;
-   latency;
-   failover/recovery burden.

Large durable objects belong in an appropriate durable store.

------------------------------------------------------------------------

## 23. Connection Management

Applications SHALL use bounded connection pools.

``` text
Task Count
   ×
Cache Connections
   ≤
Safe Connection Budget
```

Autoscaling ECS services SHALL not create uncontrolled connection
storms.

Clients SHOULD support reconnect behaviour appropriate to failover.

------------------------------------------------------------------------

## 24. Timeouts

Cache operations SHALL use bounded:

-   connection timeouts;
-   command timeouts;
-   retry limits.

An unavailable cache SHALL not cause indefinite application
thread/request blocking.

------------------------------------------------------------------------

## 25. Retry Behaviour

Retries SHALL use bounded backoff.

``` text
Cache Failure
    │
    ▼
Retry Safe?
 │       │
Yes      No
 │       │
 ▼       ▼
bounded  fail/degrade
backoff  safely
```

Retry storms during failover SHALL be prevented.

------------------------------------------------------------------------

## 26. Failure Semantics

Every consuming service SHALL define what happens when the cache is
unavailable.

Preferred for disposable caches:

``` text
Cache Available
      │
      ▼
Fast Path

Cache Unavailable
      │
      ▼
Authoritative Source
      │
      ▼
Degraded but Correct
```

Correctness SHALL take precedence over cache availability.

------------------------------------------------------------------------

## 27. Cache Stampede Protection

Applications with expensive cache rebuilds SHOULD implement stampede
protection where needed.

Mechanisms MAY include:

-   jittered TTLs;
-   bounded locks;
-   stale-while-revalidate patterns;
-   request coalescing;
-   background refresh.

Distributed locks SHALL not be introduced casually for
correctness-critical workflows.

------------------------------------------------------------------------

## 28. Distributed Locking

Redis/Valkey-based locks MAY be used only where the owning service has
explicitly defined:

-   lock ownership;
-   lease duration;
-   fencing or stale-owner handling;
-   failure semantics;
-   correctness requirements.

For workflows where duplicate execution could corrupt authoritative
state, a stronger coordination mechanism SHOULD be preferred where
appropriate.

------------------------------------------------------------------------

## 29. Sessions

Session data MAY use Redis/Valkey only where the application's session
architecture tolerates cache failover and expiration.

Long-lived business identity SHALL remain in `baobab-iam` or the owning
authoritative system.

Cache session loss SHALL not destroy authoritative user identity.

------------------------------------------------------------------------

## 30. Rate Limiting

Redis/Valkey MAY support rate-limit counters where required by APISIX or
applications.

Rate-limit state SHALL be classified as transient unless a business
requirement states otherwise.

Failure behaviour SHALL be explicitly chosen as fail-open or fail-closed
according to security and availability risk.

------------------------------------------------------------------------

## 31. Persistence

For disposable cache/projection workloads, ElastiCache persistence SHALL
NOT be relied upon as the sole recovery mechanism.

Where a workload requires stronger recovery:

-   snapshots;
-   replication;
-   append-only persistence semantics where available;
-   external authoritative reconstruction

MAY be considered.

Such a workload SHALL document why Redis/Valkey is appropriate rather
than moving authoritative state to PostgreSQL or another durable system.

------------------------------------------------------------------------

## 32. Backups

Snapshots/backups MAY be enabled for workloads where cache
reconstruction cost or stronger state requirements justify them.

Backup policy SHALL not imply that all cache data is authoritative.

``` text
Disposable Cache
      │
      └── usually rebuild

Important Reconstructable State
      │
      └── optional snapshot + rebuild
```

Platform-wide retention and restore policy is governed by
ADR-Infra-0018.

------------------------------------------------------------------------

## 33. Restore Testing

Where snapshots are part of the accepted recovery design, restoration
SHALL be tested.

A configured snapshot schedule without demonstrated restore capability
is insufficient.

------------------------------------------------------------------------

## 34. Multi-AZ Failover

Applications SHALL be tested against ElastiCache primary failover.

Tests SHOULD verify:

-   reconnect behaviour;
-   DNS/endpoint handling;
-   bounded errors;
-   no indefinite retry loops;
-   recovery latency;
-   application correctness after reconnection.

High availability exists only if clients behave correctly during
failover.

------------------------------------------------------------------------

## 35. Maintenance

Maintenance windows SHALL be configured intentionally.

Engine and node upgrades SHALL be validated in Development and Staging
before Production where Baobab controls upgrade timing.

Automatic version changes SHALL not be assumed safe for all client
libraries.

------------------------------------------------------------------------

## 36. Version Compatibility

The platform SHALL track compatibility among:

-   selected Valkey/Redis engine version;
-   client libraries;
-   APISIX plugins where relevant;
-   application frameworks;
-   vendor engines.

A nominal Redis-compatible API SHALL not substitute for integration
testing.

------------------------------------------------------------------------

## 37. Observability

Monitoring SHOULD include:

-   memory utilisation;
-   freeable memory;
-   CPU;
-   engine CPU;
-   connections;
-   cache hits/misses;
-   evictions;
-   expired keys;
-   replication health;
-   replication lag;
-   network throughput;
-   command latency;
-   failovers;
-   rejected connections.

Metrics SHALL be interpreted per workload purpose.

A low cache-hit ratio may indicate design problems rather than
infrastructure shortage.

------------------------------------------------------------------------

## 38. Alerts

Actionable alerts SHOULD cover:

-   memory exhaustion risk;
-   unexpected evictions;
-   replication degradation;
-   failover;
-   connection saturation;
-   authentication failures;
-   sustained latency;
-   node/service health;
-   snapshot failure where backups are required.

Alerts SHALL identify an operational owner.

------------------------------------------------------------------------

## 39. Slow Operations

Applications SHOULD avoid expensive blocking commands and unbounded key
scans in Production.

Operational tooling SHALL prefer cursor-based scanning and workload-safe
inspection methods.

Production debugging SHALL not introduce a cache outage.

------------------------------------------------------------------------

## 40. Keyspace Inspection

Administrative inspection SHALL use controlled identities and private
access.

Operators SHALL not expose cache endpoints publicly for troubleshooting.

Bulk deletion or flush operations SHALL require exceptional authority.

Commands equivalent to flushing an entire Production cache SHALL be
protected by procedure and least privilege.

------------------------------------------------------------------------

## 41. Data Classification

Sensitive data SHOULD be minimised in cache.

Before caching sensitive information, the owning service SHALL consider:

-   necessity;
-   TTL;
-   encryption;
-   access scope;
-   logging;
-   memory exposure;
-   deletion semantics;
-   legal/data residency requirements.

A cache is not exempt from data-protection obligations.

------------------------------------------------------------------------

## 42. ZuriBeans Go-Live

ZuriBeans SHALL access Redis/Valkey only through the Baobab services
that own relevant cache/projection state.

Conceptually:

``` text
ZuriBeans
    │
    ▼
APISIX
    │
    ├──► Trade ──► Trade cache/projections
    ├──► CP    ──► CP cache/projections
    └──► other approved service
```

ZuriBeans SHALL NOT receive broad direct credentials to shared platform
cache infrastructure.

Its cached state SHALL remain isolated from Thamani and future estates.

------------------------------------------------------------------------

## 43. Control Plane Usage

Baobab Control Plane MAY use Redis/Valkey for disposable projections,
acceleration or bounded coordination where explicitly implemented.

PostgreSQL remains authoritative for Control Plane desired state,
canonical mappings and other durable records.

``` text
Control Plane PostgreSQL
      │ authoritative
      ▼
Control Plane
      │
      ▼
Redis Projection
```

Loss of the projection SHALL not imply loss of canonical Control Plane
state.

------------------------------------------------------------------------

## 44. Cache Invalidation

Owning services SHALL define invalidation semantics.

Possible mechanisms include:

-   TTL expiration;
-   event-driven invalidation;
-   explicit delete/update;
-   versioned keys.

Infrastructure SHALL not attempt to solve domain cache invalidation
generically.

------------------------------------------------------------------------

## 45. Event-Driven Projection

Where RabbitMQ events populate cache projections:

``` text
Authoritative Change
       │
       ▼
Canonical Event
       │
       ▼
Projection Consumer
       │
       ▼
Redis / Valkey
```

Consumers SHALL be idempotent and capable of rebuilding projection state
where required.

Redis SHALL not become the event system of record.

------------------------------------------------------------------------

## 46. Infrastructure as Code

Terraform SHALL manage ElastiCache infrastructure, including where
applicable:

``` text
terraform/modules/redis/
├── subnet group
├── security group
├── replication group
├── engine/version
├── node/serverless configuration
├── Multi-AZ/failover
├── encryption
├── users/user groups
├── maintenance
├── parameter groups
├── snapshot policy
├── monitoring
└── operational outputs
```

Application key schemas, TTLs and domain invalidation rules SHALL remain
owned by application repositories.

------------------------------------------------------------------------

## 47. Serverless Option

ElastiCache Serverless MAY be considered for workloads where its scaling
and operational model provides clear value.

It SHALL NOT be selected solely to avoid capacity analysis.

Before adoption, implementation SHALL verify:

-   engine compatibility;
-   networking;
-   authentication;
-   latency;
-   cost profile;
-   supported commands/features;
-   backup/recovery requirements;
-   predictable workload behaviour.

Provisioned replication groups remain a valid baseline.

------------------------------------------------------------------------

## 48. Disaster Recovery Boundary

Multi-AZ replication protects against selected in-region failures.

It SHALL NOT be described as regional disaster recovery.

For disposable caches, regional recovery MAY consist of rebuilding state
from authoritative systems.

For stronger state classifications, ADR-Infra-0019 SHALL define regional
recovery requirements.

------------------------------------------------------------------------

## 49. Production Verification

Before go-live, verification SHALL demonstrate:

-   cache endpoints are private;
-   unauthorised workloads cannot connect;
-   authentication is enforced;
-   TLS works;
-   Multi-AZ/failover behaves as expected for critical workloads;
-   client reconnection works;
-   cache loss does not corrupt authoritative business state;
-   tenant/legal-entity isolation tests pass;
-   memory/eviction policy is deliberate;
-   TTL behaviour is verified;
-   connection limits are bounded;
-   metrics and alerts are available;
-   snapshots restore successfully where snapshots are part of recovery.

------------------------------------------------------------------------

## 50. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Self-host Redis on      Rejected                Unnecessary stateful
  Fargate by default                              operations

  Redis as authoritative  Rejected                Wrong durability/domain
  platform database                               role

  Public cache endpoints  Rejected                Violates trust-zone
                                                  architecture

  Shared password across  Rejected                Weak isolation
  all workloads                                   

  Redis logical DB number Rejected                Not a sufficient
  as tenant isolation                             security boundary

  ElastiCache instance    Rejected                Tenant does not imply
  per tenant by default                           physical cache

  `noeviction` for every  Rejected                Cache semantics differ
  workload                                        

  No TTLs by default      Rejected                Memory/staleness risk

  Unlimited connection    Rejected                Resource exhaustion
  pools                                           

  Infinite retries during Rejected                Retry storm risk
  failure                                         

  Snapshots as substitute Rejected                Cache role remains
  for authoritative state                         distinct

  Flush-all as normal     Rejected                Excessive blast radius
  operational tool                                

  Cluster mode by default Rejected                Complexity without
                                                  demonstrated need
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 51. Consequences

### Positive

-   Managed in-memory infrastructure.
-   Strong private-network posture.
-   Clear distinction between cache/projection state and authoritative
    state.
-   Multi-AZ/failover available for critical workloads.
-   Workload-specific authentication and ACLs.
-   Supports tenant-aware shared infrastructure without cache-per-tenant
    sprawl.
-   Allows Valkey-first evolution while retaining compatibility
    exceptions.
-   Provides explicit failure and reconstruction semantics.
-   Fits ZuriBeans without making it the infrastructure owner.

### Costs

-   ElastiCache introduces AWS service dependency.
-   Multi-AZ and replicas increase cost.
-   Valkey compatibility must be tested per workload.
-   Cache invalidation remains an application responsibility.
-   Memory and eviction policies require workload-specific design.
-   Failover behaviour depends on correct client configuration.
-   Stronger persistence requirements may indicate a need for another
    data store.

These costs are accepted.

------------------------------------------------------------------------

## 52. Decision Rules

The following rules are authoritative:

> **Amazon ElastiCache SHALL be Baobab's default managed Production
> in-memory service.**

> **Valkey SHALL be preferred for new deployments where workload
> compatibility is verified; Redis OSS-compatible deployment MAY be used
> where justified.**

> **Redis/Valkey SHALL NOT become an undocumented authoritative system
> of record.**

> **Critical Production cache workloads SHALL use an appropriate
> replicated Multi-AZ/failover topology.**

> **Production cache endpoints SHALL be private, authenticated and
> encrypted in transit.**

> **Tenant SHALL NOT imply an ElastiCache deployment.**

> **Redis logical database numbers SHALL NOT be treated as a tenant
> security boundary.**

> **Cache entries SHOULD use explicit TTLs unless a documented workload
> requirement states otherwise.**

> **Eviction policy SHALL be selected according to workload semantics
> rather than standardised blindly.**

> **Connection pools and retries SHALL be bounded.**

> **Loss of disposable cache/projection state SHALL not corrupt
> authoritative Baobab state.**

> **ZuriBeans and Thamani SHALL remain logically isolated even when
> cache infrastructure is shared.**

------------------------------------------------------------------------

## 53. Current AWS Validation

At implementation time, the team SHALL revalidate current AWS
ElastiCache capabilities in `af-south-1`, including:

-   Valkey engine availability;
-   supported engine versions;
-   Multi-AZ and automatic failover;
-   encryption at rest and in transit;
-   ACL/user groups;
-   IAM authentication where applicable;
-   Serverless availability where considered;
-   snapshot/restore behaviour.

AWS service capabilities and engine support evolve; Terraform
configuration SHALL target capabilities verified at implementation time
rather than assumptions copied from local Redis Compose.

------------------------------------------------------------------------

## 54. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0012 --- RabbitMQ Production Architecture**

It shall define:

-   managed versus self-operated RabbitMQ;
-   Amazon MQ suitability;
-   quorum/replication architecture;
-   private networking;
-   TLS;
-   workload identities and credentials;
-   virtual hosts;
-   exchanges and queue ownership;
-   quorum queues;
-   dead-lettering;
-   publisher confirms;
-   consumer acknowledgements;
-   retry topology;
-   message durability;
-   monitoring;
-   backup/recovery boundaries;
-   and Baobab canonical event delivery requirements.
