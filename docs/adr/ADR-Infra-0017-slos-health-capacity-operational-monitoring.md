# ADR-Infra-0017 --- SLOs, Health, Capacity and Operational Monitoring

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0005 --- Network and Trust-Zone Architecture
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0008 --- DNS, TLS, Edge and API Gateway Architecture
    -   ADR-Infra-0009 --- APISIX and etcd Production Architecture
    -   ADR-Infra-0010 --- PostgreSQL Production Architecture
    -   ADR-Infra-0011 --- Redis Production Architecture
    -   ADR-Infra-0012 --- RabbitMQ Production Architecture
    -   ADR-Infra-0015 --- Tenant and Workload Infrastructure Isolation
    -   ADR-Infra-0016 --- Observability and Telemetry Architecture
-   **Follow-on:** ADR-Infra-0018 --- Backup, Restore and Data Retention

------------------------------------------------------------------------

## 1. Context

ADR-Infra-0016 establishes how Baobab collects metrics, logs and traces.
Telemetry alone does not define whether the platform is healthy enough
to serve customers.

Production requires explicit answers to:

-   What does "available" mean?
-   Which customer journeys matter?
-   How much failure is acceptable?
-   When should an operator be paged?
-   When should a deployment be stopped or rolled back?
-   How much spare capacity is required?
-   How are queue backlogs interpreted?
-   When is a service ready for traffic?
-   When should a container be restarted?
-   How is dependency degradation distinguished from process death?

Baobab SHALL therefore operate against measurable service objectives
rather than "the process is running" or "the dashboard looks green."

------------------------------------------------------------------------

## 2. Decision

Production Baobab services SHALL define **Service Level Indicators
(SLIs)** and **Service Level Objectives (SLOs)** for customer- or
platform-critical behaviour.

Operational monitoring SHALL use:

-   customer-impacting SLIs;
-   SLOs and error budgets;
-   multi-window burn-rate alerting where appropriate;
-   readiness, liveness and startup health semantics;
-   dependency-aware health without creating cascading restart loops;
-   capacity and saturation monitoring;
-   queue/backlog monitoring;
-   synthetic checks for critical external journeys;
-   explicit alert severity and ownership;
-   deployment health gates.

Infrastructure metrics SHALL support service objectives, not replace
them.

------------------------------------------------------------------------

## 3. SLI → SLO → Error Budget

``` text
Observed Behaviour
       │
       ▼
      SLI
       │
       ▼
 Target over Window
       │
       ▼
      SLO
       │
       ▼
Allowed Unreliability
       │
       ▼
  Error Budget
```

Example:

``` text
SLI: successful eligible requests / total eligible requests
SLO: 99.9% over rolling 30 days
Error budget: 0.1% unsuccessful
```

Exact objectives SHALL be service-specific and evidence-based.

------------------------------------------------------------------------

## 4. SLOs Are Not Universal

Baobab SHALL NOT impose one arbitrary availability percentage on every
component.

SLOs SHALL reflect:

-   customer impact;
-   workload criticality;
-   dependency chain;
-   recovery capability;
-   contractual commitments;
-   operational maturity;
-   cost.

A public B2B ordering API and an asynchronous reporting worker do not
necessarily require the same objective.

------------------------------------------------------------------------

## 5. Service Criticality

Production workloads SHALL be classified by operational criticality.

A practical baseline is:

  Class            Meaning
  ---------------- ------------------------------------------------------
  **Critical**     Directly blocks core customer/platform operations
  **High**         Major capability degradation with limited workaround
  **Standard**     Important but tolerates bounded interruption
  **Background**   Delay acceptable within defined processing window

Criticality SHALL influence SLOs, redundancy, paging and capacity---not
tenant prestige.

------------------------------------------------------------------------

## 6. Customer-Journey SLOs

Where possible, Baobab SHALL measure meaningful journeys rather than
only individual processes.

For ZuriBeans, candidate journeys include:

``` text
B2B Customer Authentication
B2B Catalogue/Pricing Retrieval
B2B Order Submission
B2B Order Status Retrieval
```

A healthy ECS task count does not prove that these journeys work.

------------------------------------------------------------------------

## 7. Availability SLI

HTTP/API availability SHOULD be measured from eligible requests.

Conceptually:

``` text
successful eligible requests
────────────────────────────
total eligible requests
```

The definition SHALL explicitly determine treatment of:

-   client errors;
-   authentication failures;
-   rate limiting;
-   dependency failures;
-   gateway failures;
-   timeouts.

Expected invalid client requests SHALL not automatically count as
service failures.

------------------------------------------------------------------------

## 8. Latency SLI

Critical synchronous services SHOULD define latency objectives using
percentiles rather than averages.

Examples:

``` text
p50
p95
p99
```

Average latency SHALL NOT be the sole latency health measure because it
can hide slow-tail customer experience.

------------------------------------------------------------------------

## 9. Asynchronous SLIs

Asynchronous services SHALL use appropriate indicators such as:

-   processing success;
-   queue age;
-   time-to-process;
-   backlog;
-   retry rate;
-   DLQ rate;
-   end-to-end event completion time.

For RabbitMQ workloads, queue depth alone is insufficient.

------------------------------------------------------------------------

## 10. Freshness and Processing Windows

Background/data workloads MAY define freshness SLOs.

Example:

``` text
95% of accepted events processed within X minutes
99% within Y minutes
```

Exact values SHALL be derived from business requirements.

------------------------------------------------------------------------

## 11. Error Budgets

Each formal SLO SHOULD have an associated error budget.

``` text
SLO Target
   │
   ▼
Allowed Failure
   │
   ├── budget healthy → normal change velocity
   └── budget exhausted → reliability priority
```

Persistent error-budget exhaustion SHALL trigger reliability review.

------------------------------------------------------------------------

## 12. Error Budget Governance

Error budgets SHALL influence operational decisions.

When a critical service repeatedly exhausts its budget, teams SHOULD
consider:

-   pausing risky changes;
-   reducing deployment frequency;
-   prioritising reliability defects;
-   increasing capacity;
-   improving dependency resilience;
-   strengthening tests.

Error budgets SHALL not be used to justify intentionally consuming all
allowable failure.

------------------------------------------------------------------------

## 13. Burn-Rate Alerting

SLO-based alerts SHOULD use burn rate where practical.

``` text
Current Error Rate
        │
        ▼
How fast is the error budget being consumed?
        │
        ▼
     Burn Rate
```

Fast burn requires rapid response. Slow burn can use lower urgency.

Multi-window alerting SHOULD reduce both delayed detection and
transient-noise paging.

------------------------------------------------------------------------

## 14. Alert Philosophy

An alert SHALL answer:

> **What action should an operator take?**

Metrics without actionable thresholds belong on dashboards, not
necessarily in paging systems.

Baobab SHALL avoid alerting on every metric merely because the metric
exists.

------------------------------------------------------------------------

## 15. Alert Severity

A baseline severity model SHALL distinguish:

  -----------------------------------------------------------------------
  Severity                            Meaning
  ----------------------------------- -----------------------------------
  **SEV-1 / Critical**                Active major customer/platform
                                      impact; immediate response

  **SEV-2 / High**                    Significant degradation or imminent
                                      critical failure

  **SEV-3 / Warning**                 Requires timely investigation but
                                      no immediate major impact

  **Informational**                   Operational event; normally no page
  -----------------------------------------------------------------------

Exact incident-process naming MAY evolve, but severity semantics SHALL
remain clear.

------------------------------------------------------------------------

## 16. Alert Ownership

Every paging alert SHALL have:

-   owning service/team;
-   severity;
-   trigger;
-   dashboard/query;
-   runbook;
-   escalation path;
-   expected operator action.

An alert with no owner is not Production-ready.

------------------------------------------------------------------------

## 17. Readiness

A readiness check answers:

> **Can this instance safely receive new traffic/work now?**

If readiness fails, the workload SHOULD be removed from traffic/work
assignment without necessarily restarting the process.

Readiness MAY consider essential local dependencies required to serve
the operation.

------------------------------------------------------------------------

## 18. Liveness

A liveness check answers:

> **Is this process irrecoverably stuck such that restarting it is
> appropriate?**

Liveness SHALL be conservative.

A temporary downstream database, RabbitMQ, Redis or third-party outage
SHALL NOT automatically make every application instance fail liveness.

Otherwise the platform may create restart storms during dependency
incidents.

------------------------------------------------------------------------

## 19. Startup Health

Slow-starting services SHOULD use startup/grace mechanisms so that
liveness checks do not kill them before initialization completes.

This is particularly relevant to:

-   Java/iDempiere workloads;
-   Keycloak;
-   services performing controlled startup initialization.

Startup delay SHALL be measured, not guessed.

------------------------------------------------------------------------

## 20. Health Endpoint Separation

Where practical, services SHOULD expose distinct semantics such as:

``` text
/health/live
/health/ready
```

Exact endpoint names remain application-owned.

A single endpoint that reports every dependency failure as process death
is discouraged.

------------------------------------------------------------------------

## 21. Dependency Health

Dependency health SHALL be observable separately from process liveness.

``` text
Application
   │
   ├── process alive
   ├── ready for traffic?
   ├── PostgreSQL health
   ├── RabbitMQ health
   └── Redis health
```

Operators need to distinguish "application crashed" from "application is
healthy but dependency unavailable."

------------------------------------------------------------------------

## 22. Health Check Security

Health endpoints SHALL expose only information necessary for automated
health and diagnostics.

They SHALL NOT expose:

-   secrets;
-   connection strings;
-   credentials;
-   internal stack traces;
-   sensitive tenant data.

Detailed diagnostics SHOULD require controlled operational access.

------------------------------------------------------------------------

## 23. APISIX and Edge Health

Edge monitoring SHALL distinguish:

``` text
DNS
  │
  ▼
TLS/WAF/ALB
  │
  ▼
APISIX
  │
  ▼
Upstream Service
```

A failure at one layer SHALL not be misreported as generic application
failure where telemetry can identify the layer.

Synthetic monitoring SHOULD validate the complete public path.

------------------------------------------------------------------------

## 24. Synthetic Monitoring

Critical Production journeys SHOULD have external or independently
executed synthetic checks.

A synthetic check MAY verify:

``` text
DNS → TLS → Edge → APISIX → Service → Expected Response
```

Synthetic checks SHALL use dedicated test identities/data where
authentication is required.

They SHALL not create uncontrolled business transactions.

------------------------------------------------------------------------

## 25. ZuriBeans Synthetic Journeys

Before ZuriBeans go-live, synthetic monitoring SHOULD cover at least:

-   public digital-estate reachability;
-   TLS validity;
-   gateway routing;
-   authentication entry point;
-   one safe read-only B2B capability;
-   one controlled critical API path where feasible.

Order-creation synthetics SHALL use explicitly isolated test data if
implemented.

------------------------------------------------------------------------

## 26. Capacity Model

Every critical service SHALL understand its primary capacity
constraints.

Typical constraints include:

``` text
ECS          CPU / memory / task count
RDS          connections / CPU / I/O / storage
ElastiCache  memory / connections / evictions
RabbitMQ     queue age / backlog / consumers / storage
APISIX       request throughput / latency / connections
etcd         storage / quorum / proposal latency
```

Capacity SHALL be measured under representative load.

------------------------------------------------------------------------

## 27. Headroom

Production SHALL maintain deliberate capacity headroom for critical
workloads.

Headroom protects against:

-   traffic bursts;
-   task/node failure;
-   deployment overlap;
-   dependency slowdown;
-   recovery/replay;
-   autoscaling delay.

Operating continuously at saturation is prohibited.

------------------------------------------------------------------------

## 28. Autoscaling

Autoscaling SHALL use signals that correlate with workload demand.

CPU MAY be appropriate but SHALL not be assumed sufficient.

Other useful signals MAY include:

-   memory;
-   request rate;
-   concurrency;
-   queue backlog;
-   queue age;
-   custom application demand metrics.

Autoscaling SHALL define minimum, maximum and cooldown/stabilization
behaviour.

------------------------------------------------------------------------

## 29. Minimum Capacity

Critical services SHALL maintain enough minimum capacity to tolerate
expected task replacement and normal AZ-level scheduling behaviour
consistent with their SLO.

Scaling to zero SHALL only be used for workloads whose service objective
permits cold start and temporary absence.

------------------------------------------------------------------------

## 30. Maximum Capacity

Every autoscaled service SHALL have a bounded maximum.

The maximum SHALL consider downstream capacity.

``` text
More ECS Tasks
     │
     ▼
More DB Connections
     │
     ▼
Possible RDS Saturation
```

Autoscaling one layer SHALL not be allowed to overwhelm another.

------------------------------------------------------------------------

## 31. Database Capacity

RDS monitoring SHALL include:

-   connection utilization;
-   CPU;
-   memory;
-   I/O;
-   storage;
-   lock/deadlock behaviour;
-   query latency;
-   replica/failover health where applicable.

Application connection-pool budgets SHALL be reconciled with maximum
task counts.

------------------------------------------------------------------------

## 32. Database Storage

Storage growth SHALL be forecast.

Alerts SHALL occur before exhaustion becomes imminent.

Automatic storage scaling, where used, SHALL not replace:

-   growth monitoring;
-   maximum-threshold planning;
-   cost awareness;
-   cleanup/retention policy.

------------------------------------------------------------------------

## 33. Redis/Valkey Capacity

Cache health SHALL consider:

-   memory utilization;
-   evictions;
-   hit/miss ratio;
-   connections;
-   latency;
-   replication;
-   failover.

Unexpected sustained evictions on a cache expected to preserve hot
working data SHALL trigger investigation.

------------------------------------------------------------------------

## 34. RabbitMQ Backlog

Queue monitoring SHALL include:

-   ready messages;
-   unacknowledged messages;
-   oldest-message age where available/derived;
-   publish rate;
-   consume/ack rate;
-   redelivery;
-   DLQ growth;
-   consumer count.

A backlog is unhealthy when it threatens the workload's processing
SLO---not merely because the queue is non-empty.

------------------------------------------------------------------------

## 35. Consumer Capacity

For event consumers:

``` text
Publish Rate > Sustainable Consume Rate
             │
             ▼
          Backlog
             │
             ▼
     Processing SLO Risk
```

Scaling SHOULD consider both backlog size and age.

Infinite consumer scaling is prohibited; database/downstream limits
remain authoritative constraints.

------------------------------------------------------------------------

## 36. APISIX Capacity

APISIX monitoring SHALL include:

-   request throughput;
-   latency;
-   upstream latency;
-   error rates;
-   connection pressure;
-   rejected/rate-limited traffic;
-   unhealthy upstreams.

Capacity tests SHALL include realistic TLS/gateway/plugin overhead.

------------------------------------------------------------------------

## 37. etcd Capacity and Quorum

etcd health SHALL monitor:

-   leader presence;
-   quorum;
-   member health;
-   proposal latency/failure;
-   storage/database size;
-   disk latency;
-   peer health.

Loss of quorum is a critical configuration-control incident even if
existing APISIX traffic temporarily continues.

------------------------------------------------------------------------

## 38. Saturation

Saturation means a constrained resource is approaching the point where
additional work causes rapidly worsening service.

Examples:

``` text
CPU throttling
memory pressure
DB connection exhaustion
queue processing delay
disk/storage pressure
thread/worker exhaustion
```

Saturation indicators SHALL be monitored before hard failure.

------------------------------------------------------------------------

## 39. Capacity Forecasting

Critical capacity trends SHOULD be reviewed over time.

Forecasting SHOULD identify:

-   organic growth;
-   seasonal patterns;
-   customer onboarding impact;
-   data growth;
-   queue growth;
-   storage growth.

Capacity planning SHALL not depend solely on emergency autoscaling.

------------------------------------------------------------------------

## 40. Tenant/Workload Contention

Shared infrastructure SHALL monitor for noisy-neighbour behaviour.

Relevant signals MAY include:

-   disproportionate request volume;
-   database connection consumption;
-   queue production;
-   cache consumption;
-   compute utilization.

Tenant-level dimensions SHALL be used selectively to avoid cardinality
problems described in ADR-Infra-0016.

Repeated harmful contention MAY trigger an IsolationProfile review under
ADR-Infra-0015.

------------------------------------------------------------------------

## 41. Deployment Health Gates

Production deployment SHALL not be considered successful merely because
ECS accepted the new task definition.

Post-deployment verification SHOULD evaluate:

``` text
new tasks healthy
request success stable
latency acceptable
error rate acceptable
dependencies healthy
queue behaviour stable
synthetics pass
```

Failure SHALL trigger stop/rollback according to ADR-Infra-0022.

------------------------------------------------------------------------

## 42. Canary/Progressive Validation

Where supported and justified, high-risk services MAY use progressive
deployment/canary validation.

A canary SHALL be judged using measurable health signals.

"Wait five minutes and see" is not an adequate deployment strategy
unless accompanied by defined checks.

------------------------------------------------------------------------

## 43. Release Correlation

Operational monitoring SHALL expose the active:

-   service version;
-   image digest;
-   release/deployment identifier.

A regression SHALL be correlatable to a release without guessing.

------------------------------------------------------------------------

## 44. SLO and Dependency Composition

A service cannot sustainably promise an objective stronger than its
critical dependency chain without architectural mitigation.

``` text
Customer Journey
   │
   ├── APISIX
   ├── Service
   ├── Database
   └── IAM
```

SLO design SHALL account for dependency availability and failure
handling.

------------------------------------------------------------------------

## 45. Critical Dependency Inventory

Each Production service SHOULD document critical dependencies and
degradation behaviour.

Example:

  -----------------------------------------------------------------------
  Dependency                          Failure Behaviour
  ----------------------------------- -----------------------------------
  PostgreSQL                          core write path unavailable

  Redis                               degrade/reconstruct where
                                      architecture permits

  RabbitMQ                            transactional operation may persist
                                      outbox and delay publication

  Telemetry backend                   application continues

  Third-party API                     retry/degrade according to domain
                                      policy
  -----------------------------------------------------------------------

This prevents all dependencies from being treated equally.

------------------------------------------------------------------------

## 46. Graceful Degradation

Where domain correctness permits, services SHOULD degrade rather than
fail entirely.

Examples:

-   cache unavailable → authoritative source;
-   telemetry unavailable → continue business processing;
-   asynchronous consumer unavailable → queue safely accumulates within
    SLO;
-   optional intelligence capability unavailable → core transaction
    remains available if architecture permits.

Correctness SHALL not be sacrificed merely to remain "available."

------------------------------------------------------------------------

## 47. Fail-Open vs Fail-Closed

Security- and correctness-sensitive dependencies SHALL explicitly define
fail-open/fail-closed behaviour.

Authentication and authorization failures SHALL normally fail closed.

Optional telemetry SHALL fail open relative to the business request.

The decision SHALL be documented per capability rather than assumed
globally.

------------------------------------------------------------------------

## 48. Maintenance Windows

Planned maintenance SHALL be operationally visible and included
correctly in SLO interpretation according to the defined objective.

The platform SHALL not silently exclude outages merely because they were
planned unless the SLO/contract explicitly permits that treatment.

------------------------------------------------------------------------

## 49. Dashboard Hierarchy

Baobab SHOULD maintain dashboards at several levels:

``` text
Executive/Service Health
        │
        ▼
Customer Journey
        │
        ▼
Service
        │
        ▼
Dependency / Infrastructure
```

Operators SHOULD begin from impact and drill toward cause.

------------------------------------------------------------------------

## 50. Platform Health Dashboard

A Production platform dashboard SHOULD show:

-   critical journey availability;
-   SLO/error-budget status;
-   latency;
-   active incidents;
-   APISIX/edge health;
-   critical service health;
-   queue backlog;
-   database/cache/broker saturation;
-   recent deployments.

It SHALL avoid becoming a wall of unprioritized metrics.

------------------------------------------------------------------------

## 51. Runbooks

Every critical alert SHALL link to a runbook.

Runbooks SHOULD include:

-   symptom;
-   likely causes;
-   immediate checks;
-   safe mitigation;
-   escalation;
-   rollback/failover procedure where applicable;
-   verification;
-   follow-up.

A runbook SHALL not instruct operators to destroy/recreate stateful
infrastructure casually.

------------------------------------------------------------------------

## 52. Alert Noise

Repeated unactionable alerts SHALL be treated as defects.

The platform SHALL review:

-   false positives;
-   duplicate alerts;
-   flapping;
-   alerts with no action;
-   thresholds that trigger too late.

Muting alerts indefinitely is not a substitute for fixing alert design.

------------------------------------------------------------------------

## 53. On-Call Readiness

Before a service is declared Production-ready, the organization SHALL
know:

-   who receives critical alerts;
-   how they are contacted;
-   who can deploy/rollback;
-   who can access diagnostics;
-   who can invoke break-glass;
-   who owns follow-up.

Technical monitoring without an operational response model is
incomplete.

------------------------------------------------------------------------

## 54. Incident Correlation

Operators SHOULD be able to correlate:

``` text
Alert
  │
  ▼
SLO Impact
  │
  ▼
Trace / Logs / Metrics
  │
  ▼
Recent Deployment
  │
  ▼
Dependency Health
```

ADR-Infra-0016 provides the telemetry foundation for this workflow.

------------------------------------------------------------------------

## 55. ZuriBeans Go-Live Gate

ZuriBeans SHALL NOT be declared Production-ready until critical-path
health monitoring is implemented and exercised.

At minimum, go-live validation SHALL demonstrate:

-   public reachability;
-   valid TLS;
-   APISIX health;
-   IAM authentication path;
-   critical B2B API health;
-   Trade persistence path;
-   event publication path;
-   required downstream processing visibility;
-   meaningful alerts;
-   deployment health verification;
-   capacity/load evidence;
-   runbooks and ownership.

------------------------------------------------------------------------

## 56. Load Testing

Critical ZuriBeans/Baobab paths SHALL undergo representative load
testing before Production go-live.

Testing SHOULD determine:

-   sustainable request throughput;
-   latency distribution;
-   ECS resource consumption;
-   DB connections;
-   database latency;
-   RabbitMQ behaviour;
-   cache behaviour;
-   scaling response;
-   failure point.

Load tests SHALL use safe non-Production or isolated test
environments/data.

------------------------------------------------------------------------

## 57. Stress and Failure Testing

Where practical, Production-readiness testing SHOULD include controlled
failure scenarios such as:

-   task termination;
-   dependency unavailability;
-   broker-node disruption;
-   cache failover;
-   database failover;
-   APISIX instance loss;
-   telemetry collector loss.

The goal is to validate expected behaviour, not create uncontrolled
chaos.

------------------------------------------------------------------------

## 58. Capacity Before Onboarding

A material new tenant/workload SHALL trigger capacity assessment where
its expected load could affect shared infrastructure.

Tenant onboarding SHALL not assume that autoscaling alone guarantees
sufficient shared capacity.

------------------------------------------------------------------------

## 59. SLO Ownership

SLOs SHALL be owned by the service/domain responsible for the customer
capability, with infrastructure providing measurement foundations.

`nabhold/infrastructure` SHALL NOT invent business SLOs for Trade, ERP,
IAM or digital estates without the owning domain.

Infrastructure SHALL own objectives for infrastructure services it
directly operates.

------------------------------------------------------------------------

## 60. Production Verification

Before platform go-live, verification SHALL demonstrate:

-   critical services have defined SLIs/SLOs;
-   error budgets are calculable;
-   critical alerts are actionable and owned;
-   readiness/liveness semantics are distinct;
-   temporary dependency loss does not create restart storms;
-   critical journeys have synthetic monitoring where appropriate;
-   latency uses percentile measures;
-   queue age/backlog monitoring exists;
-   database/cache/broker saturation is monitored;
-   autoscaling has bounded minimum/maximum;
-   downstream capacity is considered;
-   deployment health gates detect regressions;
-   release versions/digests are visible;
-   runbooks exist for critical alerts;
-   ZuriBeans critical path has been load tested;
-   operator escalation is defined.

------------------------------------------------------------------------

## 61. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  "Process running" =     Rejected                Does not measure
  healthy                                         service behaviour

  One SLO for every       Rejected                Criticality differs
  service                                         

  Average latency only    Rejected                Hides tail latency

  Alert on every metric   Rejected                Creates noise

  CPU-only autoscaling    Rejected                Demand signals differ
  universally                                     

  Unlimited autoscaling   Rejected                Can overwhelm
                                                  dependencies/cost

  Queue depth alone =     Rejected                Age/rates/SLO matter
  queue health                                    

  Dependency failure =    Rejected                Creates restart storms
  liveness failure                                

  No synthetic monitoring Rejected                Internal metrics can
                                                  miss external failure

  No error-budget         Rejected                SLO becomes decorative
  governance                                      

  Tenant ID on every      Rejected                Cardinality/cost risk
  capacity metric                                 

  Deploy success = ECS    Rejected                Does not prove customer
  accepted task                                   health

  Alerts without          Rejected                Operationally
  owner/runbook                                   incomplete

  Autoscaling instead of  Rejected                Reactive and unsafe
  capacity planning                               
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 62. Consequences

### Positive

-   Customer impact becomes measurable.
-   Health semantics reduce cascading restarts.
-   SLOs connect telemetry to operational decisions.
-   Error budgets create reliability governance.
-   Capacity limits become explicit.
-   Queue backlog and asynchronous processing become measurable.
-   Deployment regressions can be detected rapidly.
-   ZuriBeans receives a concrete go-live operational gate.
-   Shared infrastructure noisy-neighbour risks become observable.

### Costs

-   SLOs require ongoing ownership and refinement.
-   Synthetic and load testing add engineering effort.
-   Capacity monitoring requires representative baselines.
-   Burn-rate alerting requires reliable SLI data.
-   Runbooks and on-call processes require maintenance.
-   Some services may need application changes for correct health
    endpoints.

These costs are accepted.

------------------------------------------------------------------------

## 63. Decision Rules

> **Critical Production services SHALL define measurable SLIs and
> SLOs.**

> **SLO targets SHALL be workload-specific rather than one arbitrary
> platform-wide percentage.**

> **Formal SLOs SHOULD have error budgets, and critical SLO alerting
> SHOULD use burn-rate principles where practical.**

> **Readiness SHALL answer whether an instance can safely receive work;
> liveness SHALL answer whether restart is appropriate.**

> **Temporary dependency failure SHALL NOT automatically make
> application liveness fail.**

> **Critical customer journeys SHOULD be monitored synthetically through
> the real external path.**

> **Latency objectives SHOULD use percentiles rather than averages
> alone.**

> **Asynchronous workloads SHALL measure processing delay/queue age and
> success, not queue depth alone.**

> **Critical workloads SHALL maintain deliberate capacity headroom and
> bounded autoscaling.**

> **Autoscaling SHALL respect downstream capacity limits.**

> **Every paging alert SHALL be actionable, owned and linked to
> operational guidance.**

> **A Production deployment SHALL pass post-deployment service-health
> checks, not merely infrastructure deployment checks.**

> **ZuriBeans SHALL pass critical-path monitoring, load, alerting and
> runbook gates before Production go-live.**

------------------------------------------------------------------------

## 64. Implementation Implications

Implementation SHALL progressively establish:

``` text
Operational Reliability
│
├── SLOs
│   ├── availability
│   ├── latency
│   ├── processing/freshness
│   └── error budgets
│
├── Health
│   ├── readiness
│   ├── liveness
│   ├── startup
│   └── dependency status
│
├── Capacity
│   ├── ECS
│   ├── RDS
│   ├── Redis/Valkey
│   ├── RabbitMQ
│   ├── APISIX
│   └── etcd
│
├── Monitoring
│   ├── synthetics
│   ├── dashboards
│   ├── burn-rate alerts
│   └── deployment gates
│
└── Operations
    ├── severity
    ├── ownership
    ├── escalation
    ├── runbooks
    └── load/failure tests
```

Exact SLO targets SHALL be established with the owning service/domain
using measured baseline performance and business requirements.

------------------------------------------------------------------------

## 65. Current Technical Validation

This ADR follows established SRE and AWS operational principles current
as of 2026-09-15:

-   availability objectives should be based on measurable service-level
    indicators;
-   error budgets connect reliability targets to operational
    decision-making;
-   multi-window, multi-burn-rate alerting is a recognized method for
    actionable SLO alerting;
-   Amazon ECS health checks and load-balancer health participate in
    task/service health decisions;
-   ECS Service Auto Scaling supports target-tracking and other scaling
    policies;
-   CloudWatch provides metric alarms, composite alarms and
    anomaly-detection capabilities;
-   AWS managed-service metrics complement application-level SLIs rather
    than replace them.

Exact AWS scaling capabilities, CloudWatch alarm features and
service-specific metrics SHALL be revalidated during implementation.

------------------------------------------------------------------------

## 66. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0018 --- Backup, Restore and Data Retention**

It shall define:

-   authoritative data inventory;
-   backup classes;
-   RPO/RTO inputs;
-   PostgreSQL backups/PITR;
-   RabbitMQ recovery;
-   etcd snapshots;
-   Redis/Valkey recovery;
-   object storage;
-   Keycloak/iDempiere/Medusa/Payload data;
-   Terraform state protection;
-   encryption;
-   retention;
-   immutability;
-   restore testing;
-   tenant/legal-entity considerations;
-   backup access;
-   deletion;
-   and evidence required before Production go-live.
