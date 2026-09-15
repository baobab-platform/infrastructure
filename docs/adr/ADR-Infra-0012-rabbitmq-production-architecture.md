# ADR-Infra-0012 --- RabbitMQ Production Architecture

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
    -   ADR-Infra-0011 --- Redis Production Architecture
-   **Follow-on:** ADR-Infra-0013 --- Infrastructure IAM and Workload
    Identity

------------------------------------------------------------------------

## 1. Context

RabbitMQ is Baobab's principal asynchronous messaging broker for
canonical events and service integration.

The platform requires messaging between independently deployable
services such as:

-   `baobab-cp`;
-   `baobab-trade`;
-   `baobab-erp`;
-   `baobab-iam`;
-   `baobab-cms`;
-   `baobab-pulse`;
-   digital-estate integration workers;
-   future Baobab engines and services.

The local development environment currently runs RabbitMQ with the
management plugin and quorum queues as the default queue type. That is
an appropriate development baseline but does not by itself provide a
production architecture.

Production messaging must provide:

-   high availability;
-   durable replicated queues where business correctness requires them;
-   private networking;
-   TLS;
-   workload-specific identities;
-   bounded retry and dead-letter handling;
-   publisher confirms;
-   explicit consumer acknowledgements;
-   idempotent consumers;
-   observable message flow;
-   controlled topology ownership;
-   failure recovery.

RabbitMQ is a delivery mechanism. It SHALL NOT become the authoritative
business database or replace Baobab's canonical contract governance.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use **Amazon MQ for RabbitMQ** as the default Production
RabbitMQ service.

Critical Production environments SHALL use an **Amazon MQ RabbitMQ
cluster deployment**, not a single-instance broker.

The default durable queue type for long-lived, business-significant
queues SHALL be **RabbitMQ quorum queues**.

Production messaging SHALL use:

-   TLS (`amqps`);
-   private broker networking;
-   workload-specific broker users/credentials;
-   publisher confirms for reliable publishing;
-   manual consumer acknowledgements;
-   durable exchanges/queues where required;
-   persistent messages for business-significant events;
-   explicit dead-letter and retry topology;
-   idempotent consumers;
-   bounded queue/backlog policies;
-   central metrics, logs and alarms.

Self-managed RabbitMQ SHALL not be the default Production architecture.

------------------------------------------------------------------------

## 3. Why Amazon MQ

``` text
Baobab Services
      │
      ▼
   AMQPS/TLS
      │
      ▼
Amazon MQ for RabbitMQ
      │
      ├── managed broker nodes
      ├── cluster deployment
      ├── stable endpoints
      ├── AWS monitoring
      └── managed maintenance
```

The platform does not currently have a requirement that justifies
operating RabbitMQ nodes, Erlang runtime, broker storage and cluster
lifecycle directly.

------------------------------------------------------------------------

## 4. Production Topology

The initial critical Production topology SHALL use the managed RabbitMQ
cluster deployment.

Conceptually:

``` text
                    Private Application Zone
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
      Publisher A        Publisher B         Consumer
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
                          AMQPS
                             │
                             ▼
                   Amazon MQ Endpoint
                             │
                 ┌───────────┼───────────┐
                 ▼           ▼           ▼
              Broker 1    Broker 2    Broker 3
                AZ-A         AZ-B         AZ-C
```

The exact AWS AZ placement remains controlled by Amazon MQ's supported
regional topology.

------------------------------------------------------------------------

## 5. Single-Instance Brokers

Single-instance RabbitMQ brokers SHALL NOT be used for critical
Production messaging.

They MAY be used in:

-   development;
-   disposable test environments;
-   explicitly non-critical workloads.

A single broker behind a stable endpoint does not provide the same
broker-node availability as a cluster deployment.

------------------------------------------------------------------------

## 6. Queue Type

Quorum queues SHALL be the default for long-lived queues where
replicated durability and high availability are required.

``` text
Exchange
   │
   ▼
Quorum Queue
   │
   ├── leader
   ├── replica
   └── replica
```

RabbitMQ quorum queues use consensus-based replication and are
appropriate for business-significant workloads where data safety is more
important than the absolute lowest possible latency.

------------------------------------------------------------------------

## 7. When Quorum Queues Are Not Appropriate

Quorum queues SHALL NOT be imposed on every messaging pattern.

They are generally inappropriate for:

-   temporary/exclusive queues;
-   very high queue churn;
-   workloads where data safety is intentionally unimportant;
-   patterns requiring semantics unsupported by quorum queues;
-   very large retained event histories better suited to a stream/log
    architecture.

Alternative queue types or messaging technologies require explicit
workload justification.

------------------------------------------------------------------------

## 8. Canonical Event Boundary

RabbitMQ transports canonical events but does not define them.

``` text
Owning Service
      │
      ▼
Canonical Contract
 nabhold/shared
      │
      ▼
RabbitMQ Exchange
      │
      ▼
Consumer
```

Canonical event schemas, versioning and semantic ownership SHALL remain
governed by `nabhold/shared` and the owning domain repositories.

`nabhold/infrastructure` SHALL NOT invent business event contracts.

------------------------------------------------------------------------

## 9. Event Publication

Business-significant event publication SHALL use the owning service's
durable transaction/outbox pattern where required to avoid the
database-message dual-write problem.

Conceptually:

``` text
Business Transaction
       │
       ├── domain change
       └── outbox record
              │
              ▼
        Outbox Publisher
              │
              ▼
          RabbitMQ
```

Infrastructure provides the broker; it does not replace
application-level transactional publication guarantees.

------------------------------------------------------------------------

## 10. Publisher Confirms

Publishers of durable/business-significant events SHALL use RabbitMQ
publisher confirms.

``` text
Publisher
    │ publish
    ▼
RabbitMQ
    │ replicated/accepted
    ▼
Publisher Confirm
```

A successful socket write SHALL NOT be interpreted as proof that
RabbitMQ safely accepted a message.

Applications SHALL handle negative confirms and uncertain publish
outcomes.

------------------------------------------------------------------------

## 11. Unroutable Messages

Business-significant publishers SHOULD use mechanisms that detect
unroutable messages where appropriate.

A successful broker connection SHALL not hide the fact that a message
matched no queue.

Topology and publisher policy SHOULD fail visibly when a required
routing path is missing.

------------------------------------------------------------------------

## 12. Consumer Acknowledgements

Consumers of business-significant events SHALL use manual
acknowledgements.

``` text
RabbitMQ
    │
    ▼
Consumer
    │
    ├── process successfully ──► ACK
    │
    └── fail processing ───────► NACK/retry/DLQ policy
```

Consumers SHALL acknowledge only after the work represented by the
message has reached the application's required durable completion point.

Automatic acknowledgement is prohibited for events where message loss
could affect business correctness.

------------------------------------------------------------------------

## 13. Delivery Semantics

Baobab SHALL design for **at-least-once delivery** for
business-significant asynchronous integration.

Therefore:

> Consumers SHALL be idempotent.

A message may be delivered more than once because of:

-   consumer failure;
-   connection failure;
-   acknowledgement uncertainty;
-   retry;
-   broker failover;
-   dead-letter/republication mechanisms.

Exactly-once business semantics SHALL NOT be assumed from RabbitMQ
alone.

------------------------------------------------------------------------

## 14. Idempotency

Consumers SHALL define a safe duplicate-processing strategy.

Possible mechanisms include:

-   event/message identifier tracking;
-   unique database constraints;
-   idempotency keys;
-   state-transition guards;
-   inbox tables;
-   deterministic upserts.

``` text
Message
   │
   ▼
Already Processed?
  │           │
 Yes          No
  │           │
  ▼           ▼
ACK       Process
              │
              ▼
          Record Result
              │
              ▼
             ACK
```

The implementation belongs to the consuming service.

------------------------------------------------------------------------

## 15. Message Identity

Canonical events SHALL carry a stable unique event/message identifier.

They SHOULD also carry sufficient metadata for traceability, such as:

-   event type;
-   event version;
-   occurred-at timestamp;
-   producer;
-   correlation ID;
-   causation ID where appropriate;
-   tenant/legal-entity context where semantically required.

Infrastructure SHALL not infer tenant identity from queue location
alone.

------------------------------------------------------------------------

## 16. Exchanges

Domain/event publishers SHOULD publish to durable exchanges rather than
directly coupling themselves to consumer queue names.

``` text
Producer
   │
   ▼
Exchange
   │
   ├──► Consumer Queue A
   ├──► Consumer Queue B
   └──► Consumer Queue C
```

This preserves publisher/consumer decoupling.

Exchange type SHALL follow routing semantics, not convenience.

------------------------------------------------------------------------

## 17. Queue Ownership

A queue SHALL have an identifiable consuming owner.

Preferred naming concept:

``` text
{domain}.{consumer}.{purpose}
```

Queue names SHALL not become accidental public API contracts unless
explicitly governed as such.

Consumers own their queue processing semantics; publishers own the
events they emit.

------------------------------------------------------------------------

## 18. Virtual Hosts

RabbitMQ virtual hosts MAY be used as an administrative and namespace
boundary.

They SHALL NOT be treated as the sole tenant-security mechanism.

Virtual-host design SHOULD primarily reflect:

-   environment;
-   platform/domain isolation;
-   operational blast radius;
-   explicitly approved workload separation.

A virtual host per tenant SHALL NOT be the default.

------------------------------------------------------------------------

## 19. Tenant and Legal-Entity Isolation

Tenant SHALL NOT imply RabbitMQ broker or virtual host.

Shared broker infrastructure MAY carry events for ZuriBeans, Thamani and
future estates where approved isolation controls are maintained.

Isolation SHALL combine:

-   workload credentials;
-   virtual-host permissions where used;
-   exchange/queue permissions;
-   canonical tenant/legal-entity context;
-   application authorization;
-   topology ownership.

ZuriBeans and Thamani SHALL remain operationally independent
legal-entity contexts.

------------------------------------------------------------------------

## 20. Broker Identities

Each independently operated publisher/consumer workload SHALL use a
dedicated broker identity or appropriately scoped identity.

Example:

``` text
baobab-cp publisher
      │
      └── write approved exchanges

baobab-trade worker
      │
      ├── read Trade queues
      └── write approved exchanges
```

One shared RabbitMQ superuser credential across all Baobab services is
prohibited.

------------------------------------------------------------------------

## 21. Administrative Identity

RabbitMQ administrative credentials SHALL be separate from application
credentials.

Application identities SHALL not receive:

-   broker-wide administrator rights;
-   unrestricted topology deletion;
-   access to unrelated queues;
-   unrestricted management API privileges.

Administrative access SHALL be private, controlled and auditable.

------------------------------------------------------------------------

## 22. Credential Storage

Broker credentials SHALL reside in the approved secrets-management
system.

They SHALL NOT be:

-   committed to Git;
-   embedded in container images;
-   stored in plaintext task definitions;
-   copied into digital-estate source repositories;
-   printed in CI logs.

Credential rotation SHALL be operationally supported.

------------------------------------------------------------------------

## 23. TLS

Production clients SHALL use TLS-protected AMQP connections.

``` text
Application
     │
     │ AMQPS
     ▼
Amazon MQ RabbitMQ
```

Clients SHALL verify broker certificates.

Plain AMQP shall not be the normal Production application path.

------------------------------------------------------------------------

## 24. Network Placement

Amazon MQ brokers SHALL be privately reachable within the approved VPC
architecture.

Broker security groups SHALL allow only approved application sources.

The broker and management interface SHALL NOT be exposed publicly merely
for convenience.

------------------------------------------------------------------------

## 25. Connection Management

Applications SHOULD reuse RabbitMQ connections and multiplex work
through channels according to client-library best practices.

Avoid:

``` text
1 message = 1 TCP connection
```

Prefer:

``` text
Application Process
      │
      ▼
Persistent Connection
      │
      ├── Channel A
      ├── Channel B
      └── Channel C
```

Connection/channel limits SHALL be included in capacity planning.

------------------------------------------------------------------------

## 26. Reconnection

Clients SHALL implement bounded automatic reconnection with backoff.

Reconnection logic SHALL:

-   tolerate broker-node failover;
-   avoid tight retry loops;
-   re-establish channels/consumers safely;
-   restore topology only where the application owns that topology;
-   preserve idempotency.

------------------------------------------------------------------------

## 27. Prefetch

Consumers SHALL use bounded prefetch appropriate to:

-   message processing time;
-   memory;
-   concurrency;
-   ordering requirements;
-   acknowledgement latency.

Unlimited prefetch is prohibited.

A large prefetch can create uneven work distribution and large
unacknowledged-message sets.

------------------------------------------------------------------------

## 28. Durable Messaging

For business-significant events:

-   exchanges SHALL be durable where appropriate;
-   queues SHALL be durable;
-   messages SHALL be published persistently where required;
-   publisher confirms SHALL be enabled;
-   consumers SHALL acknowledge manually.

Durability is an end-to-end property.

A durable queue alone does not guarantee safe delivery.

------------------------------------------------------------------------

## 29. Retry Strategy

Retries SHALL be explicit and bounded.

Preferred conceptual flow:

``` text
Main Queue
    │
    ▼
Consumer
  │     │
  │ success
  │     └────► ACK
  │
  └ failure
       │
       ▼
Retry Policy
       │
   ┌───┴────┐
   ▼        ▼
Retry     Exhausted
Queue       │
   │        ▼
   └────► Dead Letter Queue
```

Immediate unlimited requeue loops are prohibited.

------------------------------------------------------------------------

## 30. Delayed Retry

Retry delay SHOULD prevent repeatedly failing messages from immediately
consuming all worker capacity.

Delay MAY be implemented through RabbitMQ-supported queue/dead-letter
patterns or other approved mechanisms.

Retry topology SHALL be simple enough to operate and observe.

------------------------------------------------------------------------

## 31. Dead-Letter Exchanges

Business-significant queues SHOULD define dead-letter handling.

``` text
Source Queue
     │
     ▼
Dead-Letter Exchange
     │
     ▼
Dead-Letter Queue
```

DLQ routing SHALL identify the original workload and failure context.

Dead-letter queues SHALL be monitored.

A DLQ is not a permanent archive.

------------------------------------------------------------------------

## 32. At-Least-Once Dead-Lettering

Where loss during dead-letter transfer is unacceptable, quorum queues
MAY use RabbitMQ's at-least-once dead-letter strategy.

Implementation SHALL account for its required configuration and
additional resource use.

Where enabled, topology SHALL be validated against the RabbitMQ version
supported by Amazon MQ.

The platform SHALL not assume that dead-lettering is automatically
at-least-once under every configuration.

------------------------------------------------------------------------

## 33. Poison Messages

Consumers SHALL distinguish transient failures from poison messages.

A message that repeatedly fails because of invalid content or
incompatible semantics SHALL eventually leave the normal retry path.

``` text
Delivery
   │
   ▼
Failure Count
   │
   ├── below threshold ──► retry
   │
   └── threshold reached ► DLQ
```

Infinite poison-message cycling is prohibited.

------------------------------------------------------------------------

## 34. Queue Limits

Production queues SHOULD define bounded backlog controls appropriate to
their purpose.

Controls MAY include:

-   maximum length;
-   maximum bytes;
-   TTL;
-   overflow policy.

Limits SHALL be chosen carefully because rejecting or discarding
messages can affect business correctness.

For business-critical queues, backpressure and publisher failure are
often preferable to silent message loss.

------------------------------------------------------------------------

## 35. Backpressure

The platform SHALL treat sustained queue growth as an operational
signal.

``` text
Publish Rate > Consume Rate
          │
          ▼
      Queue Growth
          │
          ▼
Alert / Scale / Investigate
```

Increasing queue size indefinitely is not a capacity strategy.

------------------------------------------------------------------------

## 36. Message Size

Canonical events SHOULD be compact.

Large binary payloads SHOULD be stored in an appropriate object/data
store, with the event carrying a reference where appropriate.

RabbitMQ SHALL not become a bulk file-transfer system.

Maximum accepted message size SHALL be governed and monitored.

------------------------------------------------------------------------

## 37. Ordering

Applications SHALL NOT assume global event ordering.

Where ordering matters, the owning service SHALL explicitly define:

-   ordering scope;
-   routing key;
-   consumer concurrency;
-   retry implications.

Retries and redelivery can affect observed processing order.

Business correctness SHALL not rely on an undocumented global queue
order.

------------------------------------------------------------------------

## 38. Request/Reply

RabbitMQ request/reply MAY be used only where asynchronous messaging
genuinely fits the interaction.

Synchronous service calls SHALL not be replaced mechanically with broker
RPC.

Temporary reply queues and latency-sensitive RPC patterns may be poor
candidates for quorum queues.

------------------------------------------------------------------------

## 39. Event Retention

RabbitMQ queues are operational delivery buffers, not Baobab's permanent
event archive.

If long-term event replay/audit becomes a platform requirement, a
dedicated event-log/archive architecture SHALL be evaluated.

Retaining millions of messages indefinitely in quorum queues is not the
default strategy.

------------------------------------------------------------------------

## 40. Schema Evolution

Event schemas SHALL evolve compatibly.

Consumers SHOULD tolerate additive changes where contracts permit them.

Breaking event changes SHALL use controlled versioning.

Broker topology SHALL not be used to hide incompatible schema evolution.

------------------------------------------------------------------------

## 41. Topology Management

Baseline broker infrastructure SHALL be managed by
`nabhold/infrastructure`.

Application/domain topology SHALL be declared through an approved,
version-controlled mechanism owned jointly by the appropriate
platform/application boundary.

Terraform SHALL NOT necessarily manage every dynamically evolving queue.

The platform SHALL avoid competing topology authorities.

------------------------------------------------------------------------

## 42. Infrastructure Boundary

``` text
nabhold/infrastructure
        │
        ├── Amazon MQ broker
        ├── networking
        ├── security groups
        ├── secrets integration
        ├── monitoring
        └── foundational broker policy

Application / Shared Contracts
        │
        ├── canonical event schemas
        ├── exchanges/queues required by domain
        ├── routing semantics
        ├── retry semantics
        └── consumer behaviour
```

Infrastructure SHALL not define business semantics.

------------------------------------------------------------------------

## 43. Control Plane

Baobab Control Plane MAY publish and consume canonical platform events.

Its PostgreSQL outbox remains the durable source for events that must be
published transactionally from Control Plane state changes.

RabbitMQ SHALL not replace the Control Plane database.

------------------------------------------------------------------------

## 44. ZuriBeans Go-Live

ZuriBeans SHALL not integrate directly with every broker queue.

The intended path remains through owning Baobab services.

Conceptually:

``` text
ZuriBeans
    │
    ▼
Baobab APIs
    │
    ▼
Owning Service
    │
    ├── DB transaction
    └── outbox
          │
          ▼
       RabbitMQ
          │
          ▼
Downstream Baobab Service
```

ZuriBeans-specific events SHALL preserve its tenant/legal-entity context
and SHALL not leak into Thamani processing paths without an explicitly
authorised integration.

------------------------------------------------------------------------

## 45. Cross-Entity Events

If ZuriBeans and Thamani later transact with each other, that
relationship SHALL be modelled as an explicit business integration.

Common ownership by Nabhold SHALL NOT justify bypassing
tenant/legal-entity event boundaries.

``` text
ZuriBeans
    │
    │ explicit authorised business event
    ▼
Integration Contract
    │
    ▼
Thamani
```

------------------------------------------------------------------------

## 46. Monitoring

Production monitoring SHOULD include:

-   broker/node health;
-   connections;
-   channels;
-   queue depth;
-   message ingress/egress;
-   publish/confirm rates;
-   consumer acknowledgements;
-   unacknowledged messages;
-   redeliveries;
-   consumer utilisation;
-   DLQ depth;
-   memory pressure;
-   disk/storage pressure;
-   network;
-   node alarms;
-   failover/maintenance events.

Queue-depth monitoring SHALL be workload-aware.

------------------------------------------------------------------------

## 47. Alerts

Actionable alerts SHOULD cover:

-   broker unavailable/degraded;
-   sustained queue growth;
-   no active consumers on critical queues;
-   DLQ growth;
-   excessive redelivery;
-   connection exhaustion;
-   high unacknowledged-message count;
-   memory/storage pressure;
-   authentication failures;
-   abnormal publisher-confirm failures.

Each critical queue SHALL have an operational owner.

------------------------------------------------------------------------

## 48. Observability and Correlation

Messages SHOULD propagate:

-   trace/correlation ID;
-   event ID;
-   causation ID where appropriate.

Distributed tracing SHOULD connect:

``` text
HTTP Request
    │
    ▼
Producer
    │
    ▼
RabbitMQ
    │
    ▼
Consumer
    │
    ▼
Downstream Work
```

Trace metadata SHALL not replace canonical business identifiers.

------------------------------------------------------------------------

## 49. Broker Management Interface

RabbitMQ management access SHALL be private and restricted.

It SHALL be used for:

-   operational inspection;
-   diagnostics;
-   controlled administration.

It SHALL NOT become an application integration API.

Administrative actions with large blast radius SHALL require elevated
authority.

------------------------------------------------------------------------

## 50. Broker Configuration Changes

Production changes SHALL follow:

``` text
Change
  │
  ▼
Review
  │
  ▼
Development
  │
  ▼
Staging
  │
  ▼
Compatibility / Failure Tests
  │
  ▼
Production Approval
  │
  ▼
Apply + Verify
```

Major RabbitMQ upgrades SHALL include client compatibility and
quorum-queue validation.

------------------------------------------------------------------------

## 51. Backup Boundary

RabbitMQ is not the authoritative source of Baobab business records.

Recovery therefore prioritises:

1.  broker availability;
2.  durable queue safety;
3.  application outbox/inbox recovery;
4.  replay/republication from authoritative systems where designed.

Amazon MQ's managed durability SHALL not eliminate the need for
application-level recovery semantics.

Detailed backup/restore requirements are governed by ADR-Infra-0018.

------------------------------------------------------------------------

## 52. Disaster Recovery Boundary

A multi-AZ Amazon MQ cluster protects against selected in-region
failures.

It SHALL NOT be represented as regional disaster recovery.

Regional broker recovery, topology reconstruction and event recovery
SHALL be defined under ADR-Infra-0019.

------------------------------------------------------------------------

## 53. Failure Scenarios

Production verification SHALL cover:

  -----------------------------------------------------------------------
  Failure                             Expected Response
  ----------------------------------- -----------------------------------
  Broker node failure                 Cluster continues where
                                      quorum/service permits

  Consumer crash before ACK           Message redelivered

  Publisher loses connection before   Outcome treated as uncertain; safe
  confirm                             retry/idempotency

  Poison message                      Bounded retry then DLQ

  Consumer unavailable                Queue grows and alerts

  DLQ unavailable                     Failure visible; no silent loss
                                      assumption

  Credential revoked                  Connection denied and alertable

  Network interruption                Bounded reconnect/backoff

  Duplicate delivery                  Consumer remains correct
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 54. Capacity Planning

Capacity SHALL consider:

-   publish rate;
-   consume rate;
-   message size;
-   queue count;
-   quorum replication cost;
-   connection/channel count;
-   backlog tolerance;
-   DLQ volume;
-   burst behaviour;
-   recovery throughput.

Broker sizing SHALL be load-tested using representative Baobab event
patterns.

------------------------------------------------------------------------

## 55. Infrastructure as Code

Terraform SHALL manage Amazon MQ infrastructure, including where
applicable:

``` text
terraform/modules/rabbitmq/
├── broker
├── cluster deployment
├── engine/version
├── private subnet placement
├── security groups
├── encryption
├── secrets integration
├── broker configuration
├── maintenance
├── logging
├── monitoring
└── operational outputs
```

Application event schemas SHALL remain outside the Terraform module.

------------------------------------------------------------------------

## 56. Production Verification

Before go-live, verification SHALL demonstrate:

-   broker endpoints are private;
-   AMQPS/TLS works and certificates are verified;
-   unauthorised workloads cannot connect;
-   application identities are least privilege;
-   critical queues use approved durable/quorum configuration;
-   publisher confirms work;
-   consumers use manual acknowledgements;
-   duplicate delivery is safe;
-   poison messages reach DLQ after bounded retries;
-   broker/node failure is tolerated;
-   client reconnect works;
-   queue-depth and DLQ alerts fire;
-   ZuriBeans and Thamani event boundaries remain isolated;
-   event contracts correspond to `nabhold/shared`;
-   authoritative database/outbox recovery remains possible.

------------------------------------------------------------------------

## 57. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Self-managed RabbitMQ   Rejected                Unnecessary
  by default                                      broker-cluster
                                                  operational burden

  Single-instance broker  Rejected                Avoidable availability
  for critical Production                         risk

  Classic queues as       Rejected                Quorum queues are
  default critical queue                          preferred for
                                                  replicated durable
                                                  workloads

  One broker per tenant   Rejected                Tenant does not imply
  by default                                      physical broker

  Virtual host as sole    Rejected                Insufficient isolation
  tenant security                                 model

  Shared broker superuser Rejected                Excessive privilege
  across services                                 

  Plain AMQP in           Rejected                Transport-security
  Production                                      weakness

  Automatic consumer ACK  Rejected                Message-loss risk
  for critical events                             

  Publishing without      Rejected                Unsafe publish
  confirms for critical                           assumptions
  events                                          

  Infinite immediate      Rejected                Poison/retry storm
  retries                                         

  RabbitMQ as permanent   Rejected                Wrong workload model
  event archive                                   

  RabbitMQ as             Rejected                Wrong domain ownership
  authoritative business                          
  DB                                              

  Direct tenant access to Rejected                Breaks
  arbitrary queues                                service/capability
                                                  boundaries

  Exactly-once assumption Rejected                Distributed delivery
                                                  requires idempotent
                                                  application semantics
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 58. Consequences

### Positive

-   Managed RabbitMQ operations.
-   Multi-AZ clustered Production topology.
-   Strong quorum-queue data safety for critical messaging.
-   Explicit at-least-once delivery model.
-   Publisher and consumer reliability requirements are clear.
-   Workload-specific identities preserve least privilege.
-   Canonical contract ownership remains in `shared`.
-   Tenant/legal-entity boundaries remain independent of broker
    topology.
-   Clear retry and DLQ semantics.
-   Practical event-driven foundation for ZuriBeans and future estates.

### Costs

-   Amazon MQ introduces AWS service dependency.
-   Cluster deployments cost more than single brokers.
-   Quorum queues incur replication/storage overhead.
-   Idempotent consumer engineering is mandatory.
-   Retry/DLQ topology requires operational ownership.
-   Broker limits and supported RabbitMQ versions must be tracked.
-   Long-term replay would require a separate architecture.

These costs are accepted.

------------------------------------------------------------------------

## 59. Decision Rules

The following rules are authoritative:

> **Amazon MQ for RabbitMQ SHALL be Baobab's default Production RabbitMQ
> platform.**

> **Critical Production messaging SHALL use an Amazon MQ RabbitMQ
> cluster deployment.**

> **Quorum queues SHALL be the default for long-lived, replicated,
> business-significant queues.**

> **Production application connections SHALL use AMQPS/TLS and verify
> broker certificates.**

> **Business-significant publishers SHALL use publisher confirms.**

> **Business-significant consumers SHALL use manual acknowledgements.**

> **Baobab SHALL design business-significant messaging for at-least-once
> delivery and idempotent consumption.**

> **Retries SHALL be bounded and poison messages SHALL have a
> dead-letter path.**

> **RabbitMQ SHALL NOT be Baobab's authoritative business database or
> permanent event archive.**

> **Canonical event contracts SHALL remain governed by `nabhold/shared`
> and owning domains.**

> **Tenant SHALL NOT imply RabbitMQ broker or virtual host.**

> **ZuriBeans and Thamani SHALL remain independent legal-entity contexts
> even when broker infrastructure is shared.**

> **Infrastructure SHALL own broker runtime; application/domain
> repositories SHALL own event semantics and consumer behaviour.**

------------------------------------------------------------------------

## 60. Current Technical Validation

This ADR was checked against current AWS and RabbitMQ documentation on
2026-09-15.

Current documentation confirms that:

-   Amazon MQ supports RabbitMQ cluster deployments with three broker
    nodes distributed across multiple Availability Zones.
-   Amazon MQ RabbitMQ application connections use TLS-enabled listener
    endpoints, including secure AMQP.
-   AWS recommends quorum queues for production cluster deployments on
    supported modern RabbitMQ versions.
-   RabbitMQ recommends publisher confirms for quorum-queue data safety.
-   RabbitMQ recommends manual consumer acknowledgements for reliable
    processing.
-   Quorum queues support dead-lettering and can provide at-least-once
    dead-letter transfer under the required configuration.
-   Quorum queues are intended for long-lived, replicated queues where
    data safety matters and are not appropriate for every temporary or
    extremely large-backlog use case.

Amazon MQ regional availability, supported RabbitMQ versions, broker
instance classes, queue feature support and quotas SHALL be revalidated
immediately before implementation.

------------------------------------------------------------------------

## 61. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0013 --- Infrastructure IAM and Workload Identity**

It shall define:

-   AWS IAM boundaries;
-   GitHub Actions OIDC;
-   ECS task execution roles;
-   ECS application task roles;
-   infrastructure deployment roles;
-   human administrative access;
-   break-glass access;
-   cross-account trust;
-   least privilege;
-   role naming;
-   permission boundaries;
-   service-to-service AWS identity;
-   environment separation;
-   and the relationship between AWS infrastructure IAM and Baobab
    application IAM/Keycloak.
