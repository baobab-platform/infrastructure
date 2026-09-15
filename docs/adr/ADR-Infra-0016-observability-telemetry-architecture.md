# ADR-Infra-0016 --- Observability and Telemetry Architecture

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
-   **Follow-on:** ADR-Infra-0017 --- SLOs, Health, Capacity and
    Operational Monitoring

------------------------------------------------------------------------

## 1. Context

Baobab is a polyrepo, polyglot, event-driven platform composed of
independently deployable digital estates, platform services and headless
engines.

A single user or business operation may traverse:

``` text
Digital Estate
    │
    ▼
AWS Edge / APISIX
    │
    ▼
Baobab Service
    │
    ├── PostgreSQL / Redis
    ├── RabbitMQ
    └── downstream engine/service
```

Production operation therefore requires correlated telemetry across:

-   ZuriBeans and future digital estates;
-   APISIX;
-   `baobab-cp`;
-   `baobab-iam`;
-   `baobab-trade`;
-   `baobab-erp`;
-   `baobab-cms`;
-   `baobab-pulse`;
-   PostgreSQL;
-   ElastiCache;
-   RabbitMQ;
-   ECS/Fargate;
-   AWS edge/network infrastructure;
-   deployment and infrastructure automation.

The existing local OpenTelemetry Collector configuration exports to a
debug exporter only. This is a development foundation, not a Production
observability architecture.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL adopt **OpenTelemetry (OTel)** as the vendor-neutral
telemetry standard for application and cross-service instrumentation.

The Production observability architecture SHALL collect and correlate:

-   **metrics**;
-   **logs**;
-   **distributed traces**;
-   operational events where appropriate.

AWS-native services SHALL provide the initial managed Production
telemetry backend, with OpenTelemetry preserving portability at the
instrumentation and collection layers.

The initial AWS baseline SHALL use, where appropriate:

-   Amazon CloudWatch metrics;
-   CloudWatch Logs;
-   ECS Container Insights with enhanced observability;
-   AWS X-Ray-compatible distributed tracing through the supported
    OpenTelemetry/AWS integration;
-   CloudWatch alarms and dashboards;
-   AWS service-native metrics for managed infrastructure.

The backend MAY evolve later without requiring every application to
replace its instrumentation.

------------------------------------------------------------------------

## 3. Architecture

``` text
Applications / Engines / Gateways
             │
             │ OTLP / structured logs / native metrics
             ▼
      OpenTelemetry Layer
             │
      ┌──────┼──────┐
      ▼      ▼      ▼
   Traces  Metrics  Logs
      │      │      │
      └──────┼──────┘
             ▼
       AWS Observability
             │
      ┌──────┼───────────┐
      ▼      ▼           ▼
 CloudWatch Logs     CloudWatch Metrics
             │           │
             └─────┬─────┘
                   ▼
              Trace Backend
                   │
                   ▼
        Dashboards / Alerts / Investigation
```

------------------------------------------------------------------------

## 4. OpenTelemetry Standard

Application instrumentation SHOULD use official OpenTelemetry SDKs,
APIs, instrumentation libraries and semantic conventions appropriate to
each language/runtime.

Baobab SHALL avoid creating custom telemetry conventions where an
established OpenTelemetry semantic convention already exists.

Custom Baobab attributes SHALL be namespaced and governed.

------------------------------------------------------------------------

## 5. Service Identity

Every independently observable service SHALL provide stable telemetry
identity.

At minimum:

``` text
service.name
service.namespace
service.version
deployment.environment.name
```

`service.instance.id` SHOULD identify an individual runtime instance
where reliably available.

For horizontally scaled workloads, `service.name` SHALL remain stable
across instances.

------------------------------------------------------------------------

## 6. Baobab Service Namespace

Baobab SHOULD use a consistent OpenTelemetry service namespace.

Conceptually:

``` text
service.namespace = baobab
service.name      = baobab-trade
service.version   = <immutable release version>
```

Digital estates MAY use their own logical namespace where doing so
improves operational clarity, but naming SHALL remain deterministic and
governed.

------------------------------------------------------------------------

## 7. Resource Attributes

Telemetry SHOULD describe the resource producing it using standard
OpenTelemetry resource attributes where available.

Relevant dimensions MAY include:

-   service;
-   deployment environment;
-   cloud provider;
-   cloud region;
-   container/task identity;
-   service version.

Baobab SHALL not copy every infrastructure tag into every telemetry
item.

------------------------------------------------------------------------

## 8. Custom Baobab Context

Where operationally necessary, Baobab MAY define custom attributes such
as:

``` text
baobab.tenant.id
baobab.legal_entity.id
baobab.digital_estate.id
baobab.market
baobab.engine.name
baobab.engine_instance.id
baobab.capability
```

These names are conceptual until incorporated into an approved telemetry
contract.

Custom context SHALL be added only when:

-   operationally useful;
-   available reliably;
-   safe to expose;
-   cardinality is understood.

------------------------------------------------------------------------

## 9. Tenant Telemetry Is Not Authorization

Tenant attributes are observability metadata.

They SHALL NOT be used as proof of authorization.

``` text
Telemetry tenant attribute
          ≠
Application authorization decision
```

The owning application remains responsible for validating
tenant/legal-entity context before telemetry is emitted.

------------------------------------------------------------------------

## 10. Tenant Privacy

Tenant identifiers SHOULD use stable opaque identifiers rather than
sensitive names where practical.

Telemetry SHALL NOT contain unnecessary:

-   customer names;
-   personal data;
-   addresses;
-   identity documents;
-   payment details;
-   secret business payloads.

Operational usefulness SHALL be balanced against confidentiality and
cardinality.

------------------------------------------------------------------------

## 11. Cardinality Governance

High-cardinality telemetry can create severe cost and performance
problems.

Metrics SHALL NOT routinely use dimensions such as:

-   order ID;
-   request ID;
-   event ID;
-   user ID;
-   email address;
-   arbitrary URL;
-   full SQL statement;
-   unbounded tenant-provided strings.

High-cardinality identifiers belong primarily in traces or structured
logs when needed.

------------------------------------------------------------------------

## 12. Metrics

Metrics SHALL answer aggregate operational questions such as:

-   request rate;
-   error rate;
-   latency;
-   saturation;
-   queue backlog;
-   cache effectiveness;
-   database capacity;
-   task health;
-   deployment health.

Metrics SHOULD be low-cardinality and suitable for dashboards and
alerting.

------------------------------------------------------------------------

## 13. Logs

Production applications SHALL emit structured logs.

Preferred conceptual record:

``` json
{
  "timestamp": "...",
  "severity": "ERROR",
  "service": "baobab-trade",
  "environment": "production",
  "trace_id": "...",
  "span_id": "...",
  "correlation_id": "...",
  "event": "order.integration.failed"
}
```

The exact schema SHALL follow approved logging conventions and language
capabilities.

------------------------------------------------------------------------

## 14. Log Content

Logs SHOULD describe events, decisions and failures rather than dump
arbitrary object state.

Production logs SHALL NOT contain:

-   passwords;
-   tokens;
-   API keys;
-   private keys;
-   full authorization headers;
-   raw payment credentials;
-   unrestricted request/response bodies;
-   secret environment variables.

Sensitive values SHALL be redacted before export.

------------------------------------------------------------------------

## 15. Log Levels

Applications SHOULD use consistent severity semantics:

``` text
DEBUG  development/troubleshooting detail
INFO   normal meaningful lifecycle/business operation
WARN   abnormal but recoverable condition
ERROR  failed operation requiring attention
FATAL  process/service cannot continue
```

Production DEBUG logging SHALL not remain globally enabled by default.

------------------------------------------------------------------------

## 16. Distributed Tracing

Distributed tracing SHALL follow a request or operation across service
boundaries.

``` text
Browser / Client
      │
      ▼
APISIX
      │
      ▼
Trade API
      │
      ├── PostgreSQL
      │
      └── RabbitMQ Publish
              │
              ▼
          ERP Consumer
```

Trace context SHOULD propagate across supported synchronous and
asynchronous boundaries.

------------------------------------------------------------------------

## 17. W3C Trace Context

Baobab SHOULD use W3C Trace Context as the standard propagation format
where supported by OpenTelemetry instrumentation and participating
components.

A service SHALL preserve incoming valid trace context and create child
spans rather than invent unrelated trace trees.

Untrusted trace metadata SHALL not become authorization data.

------------------------------------------------------------------------

## 18. Correlation IDs

A business/request correlation identifier MAY coexist with OpenTelemetry
trace identifiers.

``` text
trace_id        = technical distributed trace
correlation_id  = stable operational/business correlation
event_id        = canonical event identity
```

These concepts SHALL not be conflated.

------------------------------------------------------------------------

## 19. RabbitMQ Tracing

RabbitMQ publishers and consumers SHOULD propagate trace context through
message metadata according to applicable OpenTelemetry messaging
conventions.

``` text
Producer Span
     │
     ▼
RabbitMQ Message
     │ trace context
     ▼
Consumer Span
```

Redelivery SHALL not destroy canonical event identity.

------------------------------------------------------------------------

## 20. Canonical Event Telemetry

Canonical events SHOULD expose safe operational metadata such as:

-   event type;
-   event version;
-   producer;
-   event ID;
-   correlation ID;
-   tenant/legal-entity context where appropriate.

Event payloads SHALL NOT be copied wholesale into telemetry.

------------------------------------------------------------------------

## 21. APISIX Telemetry

APISIX telemetry SHOULD include:

-   request rate;
-   response status;
-   request latency;
-   upstream latency;
-   route/upstream health;
-   rejected requests;
-   authentication/gateway-policy failures;
-   connection behaviour.

APISIX SHALL propagate correlation/trace context to upstream services
where supported.

Gateway logs SHALL redact sensitive headers.

------------------------------------------------------------------------

## 22. ECS/Fargate Telemetry

ECS/Fargate observability SHALL include:

-   service desired/running task count;
-   task starts/stops;
-   CPU;
-   memory;
-   deployment events;
-   task failure reasons;
-   container logs;
-   restart/replacement patterns.

ECS Container Insights with enhanced observability SHOULD be enabled for
Production where cost and operational requirements support it.

------------------------------------------------------------------------

## 23. Application Metrics on ECS

Applications running on ECS/Fargate SHALL use OpenTelemetry
instrumentation for custom application metrics where practical.

The collection architecture SHALL distinguish:

``` text
Application metrics ──► OpenTelemetry
Task/container metrics ──► ECS/Container Insights
AWS managed-service metrics ──► native AWS telemetry
```

One signal source SHALL not be forced to impersonate another.

------------------------------------------------------------------------

## 24. Collector Topology

The OpenTelemetry Collector SHALL remain a telemetry processing/export
component, not a business service.

A Production collector topology SHALL avoid a single collector becoming
a platform-wide single point of failure.

Possible deployment patterns include:

``` text
Application
   │
   ▼
Local/Regional Collector Layer
   │
   ▼
AWS Telemetry Backend
```

The exact ECS deployment topology SHALL be validated against scale,
reliability and supported AWS integrations during implementation.

------------------------------------------------------------------------

## 25. Collector Failure

Application correctness SHALL NOT depend on the OpenTelemetry Collector.

``` text
Telemetry Backend Failure
          │
          ▼
Application continues
          │
          ▼
Telemetry may buffer/drop according to bounded policy
```

Observability is critical operational infrastructure, but SHALL not be
placed synchronously in authorization or transaction correctness paths.

------------------------------------------------------------------------

## 26. Collector Security

Collectors SHALL:

-   run privately;
-   accept telemetry only from approved sources;
-   use workload identity;
-   export through authenticated/encrypted mechanisms;
-   redact/drop prohibited attributes where feasible;
-   avoid exposing unrestricted debug endpoints publicly.

------------------------------------------------------------------------

## 27. Debug Exporter

The current OpenTelemetry debug exporter is appropriate for local
development only.

Production SHALL NOT rely on debug export as its telemetry backend.

------------------------------------------------------------------------

## 28. Sampling

Trace sampling SHALL be explicit.

Production SHALL balance:

-   diagnostic value;
-   traffic volume;
-   incident needs;
-   storage;
-   cost.

Errors and high-value transactions MAY require higher retention/sampling
than routine successful traffic.

Sampling SHALL not silently eliminate the telemetry needed to diagnose
critical failure modes.

------------------------------------------------------------------------

## 29. Tail Sampling

Tail-based sampling MAY be introduced where the Collector topology and
scale justify it, particularly to retain:

-   errors;
-   high-latency traces;
-   selected critical workflows.

It SHALL not be introduced before understanding collector resource and
buffering requirements.

------------------------------------------------------------------------

## 30. Metrics Sampling

Application metrics SHALL generally be aggregated rather than sampled as
traces are.

Metric design SHALL avoid uncontrolled label/dimension cardinality.

------------------------------------------------------------------------

## 31. Managed AWS Service Telemetry

AWS-managed services SHALL use their native telemetry in addition to
application-level OpenTelemetry.

Examples:

``` text
RDS         → CloudWatch/RDS telemetry
ElastiCache → CloudWatch service metrics
Amazon MQ   → broker/CloudWatch metrics
ALB         → request/target metrics and access logs
WAF         → security metrics/logs
ECS         → service/task metrics
```

OpenTelemetry SHALL not replace useful managed-service health data.

------------------------------------------------------------------------

## 32. PostgreSQL Telemetry

PostgreSQL monitoring SHALL include, as applicable:

-   connections;
-   CPU;
-   memory pressure;
-   storage;
-   I/O;
-   latency;
-   locks/deadlocks;
-   transaction behaviour;
-   expensive queries;
-   failover;
-   backup health.

Application traces SHOULD capture database operation timing without
recording sensitive SQL values.

------------------------------------------------------------------------

## 33. Redis/Valkey Telemetry

ElastiCache telemetry SHOULD include:

-   memory;
-   CPU;
-   connections;
-   hit/miss ratio;
-   evictions;
-   expirations;
-   replication health;
-   latency;
-   failover.

Unexpected eviction or memory pressure SHALL be operationally visible.

------------------------------------------------------------------------

## 34. RabbitMQ Telemetry

RabbitMQ/Amazon MQ telemetry SHOULD include:

-   broker health;
-   connections/channels;
-   publish rate;
-   confirmation failures;
-   queue depth;
-   consumer count;
-   unacknowledged messages;
-   redelivery;
-   DLQ depth;
-   memory/storage pressure.

Queue metrics SHALL be attributable to an operational owner.

------------------------------------------------------------------------

## 35. etcd Telemetry

Production etcd monitoring SHALL include:

-   leader status;
-   member health;
-   quorum health;
-   proposal rates/failures;
-   database size;
-   storage latency;
-   peer connectivity;
-   snapshot/backup health.

Loss of etcd quorum SHALL generate urgent operational visibility.

------------------------------------------------------------------------

## 36. IAM and Security Telemetry

Infrastructure security telemetry SHALL include relevant:

-   AWS role assumptions;
-   denied access;
-   IAM changes;
-   secret access;
-   KMS activity;
-   WAF/security events;
-   privileged administrative operations.

Security audit telemetry SHALL remain distinguishable from application
observability.

------------------------------------------------------------------------

## 37. Deployment Telemetry

Every Production release SHOULD be observable.

Telemetry SHOULD make it possible to correlate:

``` text
service.version
image digest
deployment/release identifier
deployment time
```

with changes in:

-   error rate;
-   latency;
-   resource usage;
-   queue backlog;
-   availability.

------------------------------------------------------------------------

## 38. Release Markers

Deployment pipelines SHOULD emit or record release markers visible in
operational dashboards or investigation tooling.

An operator SHOULD be able to answer:

> "Did this failure begin immediately after a deployment?"

without manually reconstructing Git history.

------------------------------------------------------------------------

## 39. Environment Separation

Development, Staging and Production telemetry SHALL remain
distinguishable.

Production alerts SHALL not be polluted by Development signals.

Retention and verbosity MAY differ by environment.

Production telemetry access SHALL be more tightly controlled.

------------------------------------------------------------------------

## 40. IsolationProfile Awareness

Observability SHALL work for both shared and dedicated
IsolationProfiles.

``` text
Shared Infrastructure
   ├── service
   ├── tenant context where safe
   └── engine instance

Dedicated Infrastructure
   ├── service
   ├── dedicated resource identity
   └── tenant context where safe
```

Telemetry architecture SHALL not require a separate monitoring stack per
tenant by default.

------------------------------------------------------------------------

## 41. Tenant Dashboards

Tenant-specific operational views MAY be created where justified.

Such views SHALL enforce access control and SHALL not expose other
tenants' telemetry.

Tenant dashboards SHALL not require physically separate observability
infrastructure unless the IsolationProfile demands it.

------------------------------------------------------------------------

## 42. Metrics and Tenant Cardinality

Tenant ID MAY be a metric dimension only when tenant cardinality is
bounded and the operational value justifies cost.

For future large-scale SaaS, per-tenant metrics MAY instead require:

-   logs/traces;
-   derived aggregates;
-   selective high-value metrics;
-   dedicated analytics.

"Add tenant ID to every metric" is explicitly rejected.

------------------------------------------------------------------------

## 43. Data Classification

Telemetry SHALL be classified and governed as operational data.

Logs and traces can contain sensitive information even when the primary
database is properly protected.

Retention, access and export SHALL reflect the sensitivity of captured
fields.

------------------------------------------------------------------------

## 44. Telemetry Access

Access SHALL follow least privilege.

Typical roles MAY include:

-   platform operator;
-   service owner;
-   security analyst;
-   auditor;
-   tenant-support role where approved.

Access to observability SHALL not automatically grant access to raw
Production business data.

------------------------------------------------------------------------

## 45. Retention

Retention SHALL be explicit per signal/environment.

``` text
Metrics → operational trend horizon
Logs    → incident/audit horizon
Traces  → diagnostic horizon
Audit   → compliance/security horizon
```

A single universal retention period SHALL not be imposed.

Exact periods SHALL be defined from operational, legal, security and
cost requirements.

------------------------------------------------------------------------

## 46. Cost Governance

Observability cost SHALL be actively governed.

Cost drivers include:

-   log volume;
-   trace sampling;
-   custom metric dimensions;
-   high-cardinality data;
-   retention;
-   dashboard/query patterns.

Cost reduction SHALL prioritise better telemetry design rather than
disabling visibility indiscriminately.

------------------------------------------------------------------------

## 47. Sensitive Data Controls

Instrumentation SHALL apply data minimisation at the source.

Collectors MAY additionally:

-   redact attributes;
-   drop prohibited fields;
-   transform values;
-   route signals differently.

Collector redaction SHALL be defence-in-depth, not an excuse for
applications to emit secrets.

------------------------------------------------------------------------

## 48. PII and Business Payloads

Production instrumentation SHALL NOT record full business payloads by
default.

Examples of prohibited default capture include:

-   complete order payloads;
-   customer personal records;
-   passwords/tokens;
-   payment credentials;
-   identity documents.

Where payload-level diagnostics are exceptionally required, they SHALL
use controlled, temporary and audited mechanisms.

------------------------------------------------------------------------

## 49. Health Checks vs Telemetry

Health checks and observability are related but distinct.

``` text
Health Check
   "Should traffic/work continue?"

Telemetry
   "What is happening and why?"
```

A service returning HTTP 200 does not prove that its latency, queue
backlog or dependencies are healthy.

Detailed health/SLO architecture follows ADR-Infra-0017.

------------------------------------------------------------------------

## 50. Alerting Boundary

This ADR establishes telemetry sources and observability structure.

Alert thresholds, SLOs, burn rates, capacity triggers and operational
health policies are governed by ADR-Infra-0017.

Not every metric SHALL create an alert.

------------------------------------------------------------------------

## 51. Dashboards

Dashboards SHOULD be organized around operational questions rather than
technology vanity metrics.

Platform dashboards SHOULD answer:

-   Is customer traffic succeeding?
-   Which service is failing?
-   Is latency increasing?
-   Are queues growing?
-   Are databases saturated?
-   Did a deployment cause regression?
-   Is one tenant/workload creating contention?
-   Are critical dependencies healthy?

------------------------------------------------------------------------

## 52. ZuriBeans Go-Live

ZuriBeans SHALL be the first end-to-end observability validation
workload.

The critical path SHOULD be traceable:

``` text
B2B Client
    │
    ▼
ZuriBeans
    │
    ▼
APISIX
    │
    ├──► IAM
    ├──► Trade
    │      ├──► PostgreSQL
    │      └──► RabbitMQ
    │                │
    │                ▼
    │               ERP
    └──► other approved capability
```

Operators SHALL be able to identify the failing component without
requiring direct access to every application's database.

------------------------------------------------------------------------

## 53. ZuriBeans/Thamani Isolation

Telemetry from ZuriBeans and Thamani MAY share the same observability
backend where access and context controls permit.

Shared telemetry backend SHALL NOT cause:

-   cross-tenant data leakage;
-   dashboard leakage;
-   alert ambiguity;
-   accidental correlation of independent legal entities.

------------------------------------------------------------------------

## 54. Polyglot Instrumentation

Go, Node.js/TypeScript, Java and Python workloads SHALL use the
applicable supported OpenTelemetry libraries/agents.

Instrumentation quality SHALL be consistent at the semantic level even
when implementation differs by language.

No language SHALL invent incompatible trace/correlation conventions
merely because its framework differs.

------------------------------------------------------------------------

## 55. Auto-Instrumentation

Auto-instrumentation MAY accelerate coverage but SHALL not be accepted
blindly.

Implementation SHALL verify:

-   span quality;
-   sensitive-data capture;
-   overhead;
-   duplicate instrumentation;
-   semantic-convention compatibility;
-   library support.

Manual instrumentation SHALL be added for important domain operations
not represented adequately by automatic instrumentation.

------------------------------------------------------------------------

## 56. Performance Overhead

Telemetry SHALL have bounded overhead.

Instrumentation SHALL be load-tested for:

-   CPU;
-   memory;
-   network;
-   latency;
-   collector capacity;
-   backend volume.

Observability SHALL not materially destabilize the workload it is
intended to diagnose.

------------------------------------------------------------------------

## 57. Failure Semantics

  -----------------------------------------------------------------------
  Failure                             Expected Behaviour
  ----------------------------------- -----------------------------------
  Collector unavailable               Application continues; bounded
                                      buffering/drop

  CloudWatch/backend unavailable      Application remains correct

  Trace export fails                  Request still completes where
                                      application dependencies are
                                      healthy

  Log export pressure                 Bounded handling; no unbounded
                                      memory growth

  Invalid telemetry attribute         Telemetry issue isolated from
                                      business operation

  Tenant metadata missing             Do not invent tenant; preserve safe
                                      service telemetry

  Secret detected in telemetry        Treat as security exposure;
                                      redact/rotate as required
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 58. Infrastructure as Code

Terraform SHALL manage observability infrastructure where appropriate,
including:

``` text
terraform/modules/telemetry/
├── log groups
├── retention
├── IAM
├── ECS Container Insights configuration
├── collector runtime resources
├── CloudWatch dashboards
├── alarm foundations
├── trace integration
└── operational outputs
```

Application instrumentation remains owned by the application repository.

------------------------------------------------------------------------

## 59. Repository Responsibilities

  -----------------------------------------------------------------------
  Repository                          Responsibility
  ----------------------------------- -----------------------------------
  `nabhold/infrastructure`            collectors, AWS telemetry
                                      infrastructure, retention
                                      foundations, platform dashboards

  `nabhold/shared`                    shared telemetry/correlation
                                      contracts where canonical

  application/engine repo             instrumentation, domain
                                      spans/metrics/logging

  `baobab-cp`                         platform resolution/provisioning
                                      telemetry

  `baobab-iam`                        IAM-specific operational/security
                                      telemetry

  digital estate                      estate/user-experience telemetry
  -----------------------------------------------------------------------

Responsibilities SHALL not be duplicated unnecessarily.

------------------------------------------------------------------------

## 60. Production Verification

Before go-live, verification SHALL demonstrate:

-   Production no longer relies on debug-only telemetry export;
-   every critical service has stable `service.name`;
-   environment and release version are identifiable;
-   HTTP trace context propagates through APISIX and services;
-   RabbitMQ trace/correlation propagation works;
-   logs correlate with trace IDs where applicable;
-   secrets/tokens are redacted;
-   critical ECS metrics are available;
-   RDS, ElastiCache, Amazon MQ and APISIX metrics are visible;
-   etcd health is visible;
-   deployment markers can be correlated with regressions;
-   collector failure does not break application correctness;
-   ZuriBeans end-to-end flow is diagnosable;
-   tenant/legal-entity telemetry does not leak across access
    boundaries;
-   high-cardinality dimensions are controlled;
-   retention is explicitly configured.

------------------------------------------------------------------------

## 61. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Debug exporter as       Rejected                Not operational
  Production backend                              telemetry storage

  Vendor-specific         Rejected                Creates avoidable
  instrumentation in                              lock-in
  every app                                       

  Logs only               Rejected                Insufficient
                                                  distributed visibility

  Metrics only            Rejected                Insufficient diagnostic
                                                  detail

  Traces only             Rejected                Insufficient
                                                  aggregate/operational
                                                  view

  Separate monitoring     Rejected                Tenant does not imply
  stack per tenant by                             physical telemetry
  default                                         stack

  Tenant ID on every      Rejected                Cardinality/cost risk
  metric                                          

  Full request/response   Rejected                Security/privacy risk
  body logging                                    

  Secrets in telemetry    Rejected                Credential exposure

  Collector in            Rejected                Observability failure
  transaction/auth                                must not break
  critical path                                   correctness

  Unbounded trace         Rejected                Cost/resource risk
  collection                                      

  Custom conventions      Rejected                Fragmentation
  where OTel standards                            
  exist                                           

  Production DEBUG        Rejected                Volume/security/cost
  logging by default                              risk

  Service health =        Rejected                Insufficient
  process is running                              operational signal
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 62. Consequences

### Positive

-   Common telemetry model across Baobab's polyglot repositories.
-   Cross-service diagnosis from digital estate through platform
    engines.
-   Vendor-neutral application instrumentation.
-   AWS-managed initial backend.
-   Strong deployment and release correlation.
-   Supports shared and dedicated IsolationProfiles.
-   Better ZuriBeans go-live diagnostics.
-   Controlled tenant telemetry without making tenant a physical
    observability boundary.
-   Clear security and cardinality controls.

### Costs

-   Instrumentation must be implemented consistently across
    repositories.
-   CloudWatch/log/trace ingestion has ongoing cost.
-   Sampling and retention require tuning.
-   Collector capacity must be operated.
-   Tenant-aware telemetry increases governance complexity.
-   Managed-service and application telemetry must be correlated.
-   Polyglot instrumentation versions require lifecycle management.

These costs are accepted.

------------------------------------------------------------------------

## 63. Decision Rules

> **OpenTelemetry SHALL be Baobab's standard application and
> cross-service telemetry framework.**

> **Production observability SHALL combine metrics, structured logs and
> distributed traces.**

> **AWS-native managed observability services SHALL provide the initial
> Production backend while OpenTelemetry preserves instrumentation
> portability.**

> **Every independently observable service SHALL have stable service
> identity and environment/release context.**

> **Trace context SHOULD propagate across HTTP and RabbitMQ boundaries
> where supported.**

> **Tenant/legal-entity telemetry attributes SHALL be operational
> metadata, not authorization evidence.**

> **Tenant identifiers SHALL NOT be attached indiscriminately to every
> metric.**

> **Production telemetry SHALL NOT contain secrets, credentials or
> unrestricted business payloads.**

> **The OpenTelemetry Collector SHALL NOT be a synchronous dependency
> for business correctness or authorization.**

> **AWS-managed service telemetry SHALL complement rather than be
> replaced by application OpenTelemetry.**

> **Shared observability infrastructure SHALL be the default;
> tenant-specific physical observability stacks require an accepted
> IsolationProfile need.**

> **ZuriBeans SHALL validate end-to-end observability before Production
> go-live.**

------------------------------------------------------------------------

## 64. Current Technical Validation

This ADR was checked against current OpenTelemetry and AWS documentation
on 2026-09-15.

Current documentation confirms that:

-   OpenTelemetry semantic conventions provide common naming across
    traces, metrics, logs, resources and related telemetry.
-   `service.name`, `service.namespace`, `service.version` and
    `service.instance.id` are defined service resource attributes.
-   OpenTelemetry resource conventions are designed to identify the
    entity producing telemetry and its infrastructure context.
-   AWS supports OpenTelemetry application metrics for ECS workloads on
    Fargate.
-   AWS distinguishes application custom metrics from ECS task-level
    metrics and directs task-level visibility to ECS Container Insights.

Exact AWS collector distributions, ECS integration options,
CloudWatch/X-Ray capabilities, regional availability and pricing SHALL
be revalidated during implementation.

------------------------------------------------------------------------

## 65. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0017 --- SLOs, Health, Capacity and Operational Monitoring**

It shall define:

-   service-level indicators;
-   service-level objectives;
-   availability and latency targets;
-   error budgets;
-   burn-rate alerts;
-   readiness/liveness/dependency health;
-   capacity thresholds;
-   saturation;
-   queue backlog;
-   database/cache/broker capacity;
-   synthetic monitoring;
-   alert severity;
-   escalation;
-   dashboard ownership;
-   and Production go-live health gates.
