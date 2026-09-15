# ADR-Infra-0024 --- Cost Governance, Tagging and Resource Lifecycle

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0003 --- Terraform Architecture and Module Strategy
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0007 --- Container Registry and Immutable Artifact
        Strategy
    -   ADR-Infra-0010 --- PostgreSQL Production Architecture
    -   ADR-Infra-0011 --- Redis Production Architecture
    -   ADR-Infra-0012 --- RabbitMQ Production Architecture
    -   ADR-Infra-0015 --- Tenant and Workload Infrastructure Isolation
    -   ADR-Infra-0016 --- Observability and Telemetry Architecture
    -   ADR-Infra-0017 --- SLOs, Health, Capacity and Operational
        Monitoring
    -   ADR-Infra-0018 --- Backup, Restore and Data Retention
    -   ADR-Infra-0019 --- Availability, Disaster Recovery and Business
        Continuity
    -   ADR-Infra-0020 --- CI/CD and Infrastructure Change Governance
    -   ADR-Infra-0023 --- Infrastructure Security, Compliance and Audit
-   **Completes:** Initial ADR-Infra-0001 through ADR-Infra-0024
    infrastructure architecture baseline

------------------------------------------------------------------------

## 1. Context

Baobab is intended to support multiple legal entities, digital estates,
engines, markets and eventually external SaaS customers.

Cloud cost will therefore grow across:

-   compute;
-   databases;
-   cache;
-   messaging;
-   networking;
-   observability;
-   backups;
-   security services;
-   container registries;
-   object storage;
-   data transfer;
-   disaster-recovery capacity.

Cost cannot be governed correctly if every tenant automatically receives
dedicated infrastructure.

Conversely, cost reduction SHALL NOT weaken:

-   tenant isolation;
-   security;
-   reliability;
-   recoverability;
-   data residency;
-   accepted SLOs.

Baobab requires cost attribution and resource lifecycle governance as
architectural concerns rather than retrospective billing exercises.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL implement **FinOps-oriented cost governance** based on:

1.  mandatory resource metadata;
2.  environment/service/workload attribution;
3.  shared-cost allocation;
4.  budgets and anomaly detection;
5.  right-sizing;
6.  lifecycle automation;
7.  orphan-resource detection;
8.  retention governance;
9.  deliberate commitment purchasing;
10. periodic cost review.

Cost optimization SHALL remain subordinate to accepted security,
reliability, compliance and isolation requirements.

------------------------------------------------------------------------

## 3. Core Principle

``` text
Business Requirement
        │
        ▼
Architecture / Isolation / SLO
        │
        ▼
Required Resources
        │
        ▼
Measured Consumption
        │
        ▼
Cost Attribution
        │
        ▼
Optimization
```

The architecture SHALL NOT begin with "cheapest resource" and work
backwards into weakened requirements.

------------------------------------------------------------------------

## 4. Cost Governance Objectives

Baobab SHOULD be able to answer:

-   What does each environment cost?
-   What does each platform service cost?
-   Which costs are shared?
-   Which resources belong to a dedicated tenant/workload?
-   Which costs are growing unexpectedly?
-   Which resources are idle or orphaned?
-   Which services are over-provisioned?
-   What does ZuriBeans materially add to shared platform cost?
-   When is stronger physical isolation economically justified?

------------------------------------------------------------------------

## 5. Mandatory Tagging

Taggable AWS resources SHALL receive a standard Baobab tag set where
supported.

Baseline tags:

  Tag                            Purpose
  ------------------------------ ------------------------------------
  `baobab:environment`           development/staging/production
  `baobab:service`               owning platform service/workload
  `baobab:owner`                 accountable team/function
  `baobab:managed-by`            terraform/approved controller
  `baobab:cost-center`           financial attribution
  `baobab:data-classification`   approved classification
  `baobab:isolation-profile`     applicable isolation class
  `baobab:repository`            source repository where meaningful

Exact values SHALL be centrally governed.

------------------------------------------------------------------------

## 6. Tag Namespace

Baobab-specific tags SHOULD use the `baobab:` namespace.

This reduces collisions with:

-   AWS-managed tags;
-   third-party tooling;
-   generic organizational tags.

Tag keys SHALL be stable and machine-readable.

------------------------------------------------------------------------

## 7. Environment Tag

Every taggable environment-owned resource SHALL identify its
environment.

Examples:

``` text
baobab:environment=development
baobab:environment=staging
baobab:environment=production
```

Free-form variants such as `prod`, `prd`, `live` SHALL not be mixed
arbitrarily.

------------------------------------------------------------------------

## 8. Service Tag

`baobab:service` SHALL identify the primary owning workload or platform
capability.

Examples MAY include:

``` text
baobab-cp
baobab-trade
baobab-iam
baobab-erp
baobab-cms
baobab-pulse
zuribeans
shared-platform
```

Shared infrastructure SHALL be labelled honestly as shared rather than
falsely attributed to one tenant.

------------------------------------------------------------------------

## 9. Tenant Tagging

A tenant/legal-entity tag SHALL be used only where the physical resource
is genuinely dedicated to that tenant or where approved cost allocation
requires it and disclosure is safe.

Shared resources SHALL NOT be tagged:

``` text
tenant=zuribeans
```

merely because ZuriBeans was the first workload using them.

This prevents misleading ownership and lifecycle decisions.

------------------------------------------------------------------------

## 10. Legal-Entity Identifiers

Where tenant/legal-entity identifiers are used in tags, they SHOULD be
stable opaque identifiers rather than sensitive customer names where
practical.

Tags SHALL NOT contain:

-   personal information;
-   secrets;
-   credentials;
-   confidential transaction details.

AWS tags are operational metadata, not a secret store.

------------------------------------------------------------------------

## 11. IsolationProfile Tag

Where applicable:

``` text
baobab:isolation-profile=<approved-profile>
```

SHALL identify the physical isolation policy represented by the
resource.

The tag is descriptive evidence.

It SHALL NOT itself determine authorization or tenant resolution.

------------------------------------------------------------------------

## 12. Managed-By Tag

Resources created through Terraform SHOULD identify:

``` text
baobab:managed-by=terraform
```

Resources owned by another approved controller MAY use its governed
identifier.

Manual resources lacking an approved owner SHALL be treated as potential
drift.

------------------------------------------------------------------------

## 13. Repository Tag

Where useful, a resource MAY identify the repository responsible for its
workload/configuration.

Example:

``` text
baobab:repository=nabhold/baobab-trade
```

The infrastructure repository remains owner of physical provisioning
even when the application repository owns the workload artifact.

------------------------------------------------------------------------

## 14. Tag Enforcement

Mandatory tags SHOULD be enforced through:

-   Terraform module defaults;
-   variable validation;
-   CI policy-as-code;
-   AWS Organizations tag policies where appropriate;
-   AWS Config/security/cost checks where useful.

Manual tagging after deployment SHALL not be the primary mechanism.

------------------------------------------------------------------------

## 15. Untaggable Resources

Not every AWS resource supports all tagging semantics.

Where tagging is unavailable, attribution SHALL derive from:

-   parent resource;
-   Terraform state/module;
-   account/environment;
-   naming;
-   AWS billing dimensions.

Lack of tag support SHALL not make a resource unowned.

------------------------------------------------------------------------

## 16. Naming and Tags

Resource names and tags serve different purposes.

``` text
Name
  = operational identification

Tags
  = metadata, ownership, governance, cost
```

Cost attribution SHALL not depend solely on parsing resource names.

------------------------------------------------------------------------

## 17. Cost Allocation Tags

Approved cost-allocation tags SHALL be activated in AWS billing tooling
where appropriate.

Tag creation alone does not make a tag available for all billing
analysis.

The billing configuration SHALL explicitly enable the required
cost-allocation dimensions.

------------------------------------------------------------------------

## 18. Cost Categories

Baobab SHOULD define cost categories such as:

-   shared platform;
-   Control Plane;
-   IAM;
-   Trade;
-   ERP;
-   CMS;
-   Pulse;
-   digital estate;
-   security;
-   observability;
-   backup/DR;
-   networking.

These categories MAY combine multiple AWS services.

------------------------------------------------------------------------

## 19. Shared Costs

Shared infrastructure costs SHALL be distinguished from dedicated
workload costs.

Examples:

``` text
Shared
├── APISIX
├── etcd
├── shared networking
├── shared observability
└── shared security tooling

Workload-attributable
├── dedicated ECS service
├── workload DB
├── workload storage
└── workload-specific traffic
```

------------------------------------------------------------------------

## 20. Shared-Cost Allocation

Shared costs MAY be allocated for management reporting using a
transparent model.

Possible drivers include:

-   request volume;
-   compute consumption;
-   storage;
-   transaction volume;
-   tenant count;
-   equal allocation;
-   blended weighting.

Allocation SHALL be an accounting/FinOps model unless physical isolation
is independently required.

------------------------------------------------------------------------

## 21. Cost Allocation Does Not Create Tenancy

Authoritative rule:

``` text
Cost Allocation
      ≠
Tenant Authorization
      ≠
IsolationProfile
      ≠
Dedicated Infrastructure
```

A desire for tenant-level billing SHALL not automatically create a
database, VPC or broker per tenant.

------------------------------------------------------------------------

## 22. ZuriBeans Cost Attribution

ZuriBeans SHALL initially be measured as:

1.  direct ZuriBeans-specific resources;
2.  incremental use of shared Baobab resources;
3.  allocated share of common platform overhead.

The first Production tenant SHALL NOT be assigned the full long-term
shared-platform cost merely because no other tenant is live yet.

------------------------------------------------------------------------

## 23. Thamani Independence

Thamani SHALL have independent cost attribution when onboarded.

ZuriBeans and Thamani may share infrastructure, but their:

-   direct costs;
-   consumption;
-   business economics;
-   legal-entity reporting

SHALL remain distinguishable.

------------------------------------------------------------------------

## 24. External SaaS Tenants

Future external customers SHALL use the same model:

``` text
Direct Cost
   +
Allocated Shared Cost
   +
Isolation Premium where applicable
```

A stronger IsolationProfile MAY carry materially higher cost and SHOULD
be visible in commercial pricing.

------------------------------------------------------------------------

## 25. Budgets

AWS Budgets or an approved equivalent SHALL be configured for meaningful
scopes.

At minimum, Production SHOULD have:

-   monthly cost budget;
-   forecast threshold;
-   actual-spend thresholds.

Development/Staging SHOULD also have bounded budgets appropriate to
their role.

------------------------------------------------------------------------

## 26. Budget Alerts

Budget thresholds SHOULD escalate progressively.

Conceptually:

``` text
50% / expected pace
      │
      ▼
Informational

80%
      │
      ▼
Review

100% / forecast breach
      │
      ▼
Escalate
```

Exact thresholds SHALL reflect business needs.

Budget alerts SHALL NOT automatically terminate critical Production
services.

------------------------------------------------------------------------

## 27. Cost Anomaly Detection

AWS Cost Anomaly Detection or an approved equivalent SHOULD monitor
unexpected spend.

Anomalies SHOULD be segmented by useful dimensions such as:

-   account;
-   service;
-   cost category;
-   environment.

An anomaly SHALL trigger investigation, not automatic destructive
remediation.

------------------------------------------------------------------------

## 28. Cost Alert Ownership

Every budget/anomaly alert SHALL have an owner.

Alerts without a recipient or expected action are operationally useless.

Cost alerts SHOULD identify:

-   scope;
-   expected baseline;
-   observed/forecast cost;
-   likely driver;
-   investigation path.

------------------------------------------------------------------------

## 29. Cost Dashboards

Cost reporting SHOULD provide views for:

``` text
Organization
  │
  ├── Environment
  │
  ├── Service
  │
  ├── Cost Category
  │
  └── Dedicated Tenant Resources
```

FinOps reporting SHALL not expose confidential tenant information
unnecessarily.

------------------------------------------------------------------------

## 30. Right-Sizing

Resources SHALL be sized from measured demand rather than habit.

Review SHOULD include:

-   ECS CPU/memory utilization;
-   RDS capacity;
-   cache memory/connections;
-   RabbitMQ broker utilization;
-   storage growth;
-   NAT/data-transfer cost;
-   observability ingestion.

------------------------------------------------------------------------

## 31. Right-Sizing Safety

Right-sizing SHALL preserve:

-   SLO headroom;
-   deployment overlap;
-   failover capacity;
-   traffic bursts;
-   recovery capacity.

Running every resource near 100% utilization is not efficient
architecture.

------------------------------------------------------------------------

## 32. ECS Cost Governance

ECS/Fargate workloads SHALL have explicit CPU/memory sizing.

Sizing SHOULD be reviewed after representative load testing and
Production observation.

Fargate Spot MAY be used only for interruption-tolerant workloads as
defined by ADR-Infra-0006.

------------------------------------------------------------------------

## 33. Scale-to-Zero

Development/background workloads MAY scale to zero where technically and
operationally appropriate.

Critical Production services SHALL NOT scale to zero unless their SLO
explicitly permits cold-start unavailability.

------------------------------------------------------------------------

## 34. Non-Production Scheduling

Development and Staging resources SHOULD be stopped, scaled down or
scheduled outside working/test windows where:

-   the service supports it;
-   state safety is preserved;
-   team workflows are not materially harmed.

This MAY include selected:

-   ECS services;
-   development databases;
-   test environments;
-   temporary resources.

------------------------------------------------------------------------

## 35. Production Scheduling

Production resources SHALL NOT be stopped merely to meet a cost target
if doing so violates:

-   availability;
-   recovery;
-   security;
-   business continuity.

Cost governance is not an outage mechanism.

------------------------------------------------------------------------

## 36. RDS Cost Governance

RDS review SHALL consider:

-   instance class;
-   storage;
-   IOPS;
-   connection pressure;
-   Multi-AZ requirement;
-   backup retention;
-   read replicas;
-   utilization trend.

Multi-AZ SHALL not be removed merely because it costs more when required
by accepted availability objectives.

------------------------------------------------------------------------

## 37. Database Consolidation

Multiple logical databases MAY share physical RDS infrastructure where
accepted engine/isolation architecture permits.

Consolidation SHALL consider:

-   blast radius;
-   version compatibility;
-   performance;
-   maintenance;
-   legal isolation;
-   recovery.

Cost alone SHALL not justify unsafe consolidation.

------------------------------------------------------------------------

## 38. Cache Cost Governance

ElastiCache/Valkey review SHALL consider:

-   node/serverless capacity model;
-   memory use;
-   hit rate;
-   evictions;
-   connection count;
-   replication;
-   data-transfer.

A cache providing negligible value SHOULD be redesigned or removed
rather than retained automatically.

------------------------------------------------------------------------

## 39. RabbitMQ Cost Governance

RabbitMQ/Amazon MQ sizing SHALL consider:

-   broker size;
-   cluster topology;
-   queue backlog;
-   throughput;
-   storage;
-   connection/channel count.

Critical cluster redundancy SHALL not be removed merely to save cost.

------------------------------------------------------------------------

## 40. APISIX and etcd Cost Governance

APISIX capacity SHALL reflect actual gateway throughput and resilience
requirements.

etcd SHALL preserve quorum and durability requirements.

Cost optimization SHALL not reduce a three-member required quorum to an
unsafe two-node topology.

------------------------------------------------------------------------

## 41. Network Cost Governance

Network cost SHALL be reviewed explicitly.

Potential drivers include:

-   NAT Gateway hourly/data charges;
-   cross-AZ traffic;
-   cross-region traffic;
-   internet egress;
-   load balancers;
-   VPC endpoints.

Architecture SHOULD reduce unnecessary data movement without weakening
network boundaries.

------------------------------------------------------------------------

## 42. NAT Strategy

NAT architecture SHALL balance:

-   availability;
-   security;
-   cost;
-   cross-AZ traffic.

A single NAT Gateway may reduce cost but introduce availability/cross-AZ
tradeoffs.

The Production design SHALL follow accepted availability requirements
rather than universal cheapest topology.

------------------------------------------------------------------------

## 43. VPC Endpoints

VPC endpoints SHOULD be considered where they:

-   improve private connectivity;
-   reduce NAT dependence;
-   improve security;
-   provide economic benefit.

Endpoints SHALL not be added indiscriminately; they also carry cost.

------------------------------------------------------------------------

## 44. Observability Cost

Telemetry cost SHALL be governed through:

-   log retention;
-   sampling;
-   metric cardinality;
-   debug controls;
-   trace volume;
-   dashboard usefulness.

Cost SHALL be reduced by improving telemetry design, not by making
Production opaque.

------------------------------------------------------------------------

## 45. Log Retention

CloudWatch log groups SHALL have explicit retention.

"Never expire" SHALL not be the default for ordinary application logs.

Security/audit logs MAY require longer retention according to
ADR-Infra-0023.

------------------------------------------------------------------------

## 46. Metrics Cardinality

Unbounded custom metric dimensions SHALL be prohibited.

Tenant/order/user/event identifiers SHALL not automatically become
metric dimensions.

Cardinality is both an operational and cost concern.

------------------------------------------------------------------------

## 47. Trace Sampling

Trace sampling SHALL balance:

-   diagnostic value;
-   SLO visibility;
-   incident investigation;
-   traffic volume;
-   cost.

High-value/error traces MAY use stronger retention/sampling.

------------------------------------------------------------------------

## 48. Backup Cost Governance

Backup cost SHALL reflect:

-   RPO/RTO;
-   retention;
-   snapshot size;
-   cross-region/cross-account copies;
-   legal requirements.

Unused orphan snapshots SHALL not accumulate indefinitely.

------------------------------------------------------------------------

## 49. Backup Lifecycle

Backup retention SHALL be automated where possible.

``` text
Create
  │
  ▼
Retain
  │
  ▼
Transition / Archive if justified
  │
  ▼
Expire according to policy
```

Manual deletion SHALL not be the normal retention mechanism.

------------------------------------------------------------------------

## 50. Object Storage Lifecycle

S3/object storage SHOULD use lifecycle policies where appropriate for:

-   temporary files;
-   logs;
-   backups;
-   generated reports;
-   archival objects.

Lifecycle policy SHALL respect legal retention and recovery
requirements.

------------------------------------------------------------------------

## 51. ECR Lifecycle

Container registries SHALL use lifecycle governance.

Production-referenced digests SHALL remain available for required
rollback/recovery windows.

Old unreferenced artifacts MAY expire according to policy.

Lifecycle rules SHALL not delete the only known-good rollback artifact.

------------------------------------------------------------------------

## 52. Terraform State Lifecycle

Terraform state versions SHALL remain protected under ADR-Infra-0004.

State retention SHALL balance:

-   recovery;
-   audit;
-   sensitive metadata;
-   storage.

State SHALL not be aggressively expired without a recovery analysis.

------------------------------------------------------------------------

## 53. Temporary Resources

Temporary infrastructure SHALL include an explicit lifecycle.

Examples:

-   preview environments;
-   migration instances;
-   restore-test databases;
-   DR exercise resources;
-   load-test infrastructure.

Temporary SHALL mean automatically or operationally removable after its
purpose ends.

------------------------------------------------------------------------

## 54. Expiry Metadata

Temporary resources SHOULD carry metadata such as:

``` text
baobab:lifecycle=temporary
baobab:expires-at=<approved timestamp/date>
```

where supported and useful.

Expiry metadata SHALL feed cleanup reporting/automation.

------------------------------------------------------------------------

## 55. Orphan Detection

Baobab SHALL detect resources that appear unowned or unused.

Candidates include:

-   unattached storage;
-   old snapshots;
-   unused load balancers;
-   stale elastic IPs;
-   abandoned databases;
-   old task definitions/images;
-   unused secrets;
-   obsolete DNS records;
-   temporary test resources.

Detection SHALL precede deletion.

------------------------------------------------------------------------

## 56. Orphan Deletion Safety

An apparently idle resource SHALL NOT be deleted automatically if it may
be:

-   backup/recovery dependency;
-   DR asset;
-   compliance retention;
-   dormant but contractual;
-   Terraform-managed;
-   externally referenced.

Cleanup SHALL verify ownership and lifecycle first.

------------------------------------------------------------------------

## 57. Resource Decommissioning

Decommissioning SHALL follow:

``` text
Identify Resource
      │
      ▼
Confirm Owner / Dependencies
      │
      ▼
Check Retention / Backup
      │
      ▼
Remove Traffic / Bindings
      │
      ▼
Revoke Secrets / Access
      │
      ▼
Destroy
      │
      ▼
Verify Billing Stops
```

------------------------------------------------------------------------

## 58. Tenant Deprovisioning

Tenant deprovisioning SHALL distinguish logical and physical resources.

``` text
Tenant Removed
      │
      ├── shared resource → retain
      └── dedicated resource → evaluate destruction
```

A tenant departure SHALL not destroy shared platform infrastructure.

------------------------------------------------------------------------

## 59. Dedicated Tenant Resources

Dedicated resources SHALL carry enough metadata to identify:

-   tenant/legal entity;
-   IsolationProfile;
-   owner;
-   retention requirement;
-   cost center;
-   lifecycle.

This supports safe billing and deprovisioning.

------------------------------------------------------------------------

## 60. Resource Ownership

Every Production resource SHALL have an accountable owner, either
directly or through a clearly owned parent/module/service.

"No one knows what this is" is a lifecycle-governance defect.

------------------------------------------------------------------------

## 61. Cost of Isolation

IsolationProfile decisions SHALL include economic impact.

Conceptually:

  Isolation                Relative Cost
  ---------------------- ---------------
  Shared                          Lowest
  Data-Isolated            Low--Moderate
  Instance-Isolated             Moderate
  Environment-Isolated              High
  Region-Isolated                Highest

Cost SHALL inform---not dictate---the decision.

------------------------------------------------------------------------

## 62. Isolation Downgrade

A stronger IsolationProfile SHALL NOT be downgraded solely for cost
savings without the controlled review required by ADR-Infra-0015.

Security, contract, residency and data-migration implications SHALL be
assessed first.

------------------------------------------------------------------------

## 63. Commitment Discounts

Savings Plans, Reserved Instances/commitments or other AWS commitment
mechanisms SHOULD be considered only after workload baselines become
sufficiently predictable.

Commitment SHALL consider:

-   utilization history;
-   growth forecast;
-   architecture changes;
-   service eligibility;
-   commitment duration;
-   DR capacity.

Premature commitments may lock Baobab into obsolete architecture.

------------------------------------------------------------------------

## 64. Spot Capacity

Spot/interruption-discounted capacity SHALL only be used for workloads
that tolerate interruption.

Examples MAY include:

-   batch processing;
-   non-critical workers;
-   rebuildable analytics;
-   selected development workloads.

Critical synchronous customer paths SHALL not depend solely on Spot.

------------------------------------------------------------------------

## 65. Cost Forecasting

Major architecture changes SHOULD include estimated cost impact before
Production approval.

Examples:

-   new region;
-   dedicated tenant environment;
-   new RDS cluster;
-   warm DR;
-   increased log retention;
-   high-volume data pipeline.

Forecasts need not be perfectly accurate, but material cost should not
be a surprise.

------------------------------------------------------------------------

## 66. Cost Regression

Infrastructure PRs SHOULD expose material cost regressions where
practical.

A cost increase MAY be entirely valid.

The goal is visibility:

``` text
Change
  │
  ▼
Estimated Cost Impact
  │
  ▼
Review
```

Cost tooling MAY be integrated into CI when mature enough.

------------------------------------------------------------------------

## 67. Cost Optimization Review

Baobab SHOULD conduct periodic FinOps reviews.

Review SHOULD examine:

-   top services;
-   month-over-month changes;
-   anomalies;
-   idle resources;
-   right-sizing;
-   commitments;
-   storage growth;
-   observability cost;
-   backup cost;
-   network transfer;
-   tenant/shared allocation.

------------------------------------------------------------------------

## 68. Cost vs Reliability

An optimization SHALL be rejected if it materially violates an accepted
SLO/RTO/RPO without a superseding decision.

Examples:

``` text
Remove Multi-AZ to save cost      → reject if SLO requires it
Reduce etcd quorum to two         → reject
Delete backups early              → reject
Disable monitoring                → reject
Use Spot for sole critical path   → reject
```

------------------------------------------------------------------------

## 69. Cost vs Security

Cost reduction SHALL NOT justify:

-   public data services;
-   weaker encryption;
-   shared credentials;
-   disabling critical audit;
-   removing tenant isolation;
-   retaining secrets insecurely.

Security remains a non-negotiable constraint.

------------------------------------------------------------------------

## 70. Cost vs Compliance

Legal/contractual retention, residency and security requirements take
precedence over ordinary optimization.

If a requirement creates significant cost, the business SHALL see that
cost explicitly rather than infrastructure silently violating the
requirement.

------------------------------------------------------------------------

## 71. Cost vs Architecture Purity

Conversely, engineering SHALL not overbuild merely for architectural
elegance.

Dedicated infrastructure, multi-region systems, excessive observability
and high-capacity resources require evidence.

Baobab SHALL pursue the simplest architecture that safely meets accepted
requirements.

------------------------------------------------------------------------

## 72. FinOps Ownership

Cost governance is shared among:

  Role                    Responsibility
  ----------------------- -----------------------------------------
  Infrastructure          resource efficiency, tagging, lifecycle
  Service owners          workload sizing/usage
  Finance/business        budgets, cost centers, economics
  Security                prevents unsafe optimization
  Architecture            isolation/reliability tradeoffs
  Tenant/product owners   demand and service requirements

No single team can optimize cost accurately in isolation.

------------------------------------------------------------------------

## 73. Cost Governance Automation

Terraform and CI SHOULD automate:

-   standard tags;
-   environment metadata;
-   lifecycle settings;
-   log retention;
-   backup retention;
-   ECR lifecycle;
-   budget resources where appropriate;
-   anomaly-monitor configuration;
-   policy validation.

Manual spreadsheets MAY supplement analysis but SHALL not be the only
governance system.

------------------------------------------------------------------------

## 74. Policy as Code

Machine-checkable cost/lifecycle policies MAY enforce:

``` text
REQUIRE environment tag
REQUIRE owner tag
REQUIRE managed-by tag
REQUIRE explicit log retention
REQUIRE lifecycle on temporary resources
DENY unapproved Production instance classes where governed
WARN on missing expiry for temporary resources
```

Cost policy SHALL not override architectural ADRs.

------------------------------------------------------------------------

## 75. ZuriBeans Go-Live Cost Gate

Before ZuriBeans Production go-live, verify:

-   Production resources have required tags;
-   ZuriBeans-specific resources are distinguishable;
-   shared resources are not falsely tagged as ZuriBeans-owned;
-   Production budget exists;
-   cost anomaly monitoring is configured;
-   ECS/RDS/cache/broker sizing has evidence;
-   log retention is explicit;
-   backup retention is explicit;
-   ECR lifecycle protects rollback artifacts;
-   temporary staging/test resources have cleanup paths;
-   known shared-platform baseline cost is documented;
-   no cost optimization weakens the accepted go-live
    security/reliability posture.

------------------------------------------------------------------------

## 76. Production Verification

Before declaring this ADR implemented, verify:

-   standard tag schema exists;
-   Terraform applies tags consistently;
-   cost-allocation tags are enabled where needed;
-   shared vs dedicated costs are distinguishable;
-   budgets and forecast alerts exist;
-   anomaly detection exists;
-   alert ownership exists;
-   resource right-sizing is reviewed;
-   non-Production scheduling is considered;
-   logs have retention;
-   backups have lifecycle;
-   ECR has lifecycle;
-   temporary resources have cleanup;
-   orphan detection exists;
-   decommission runbook exists;
-   tenant deprovisioning preserves shared resources;
-   commitment purchases require evidence;
-   cost changes are reviewed for major architecture decisions;
-   ZuriBeans cost gate passes.

------------------------------------------------------------------------

## 77. Rejected Alternatives

  --------------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- --------------------------
  No tags; infer          Rejected                Fragile attribution
  ownership from names                            

  Tag every shared        Rejected                False ownership
  resource to first                               
  tenant                                          

  Tenant = dedicated      Rejected                Wasteful/architecturally
  infrastructure for                              wrong
  billing                                         

  Cheapest topology       Rejected                Reliability violation
  regardless of SLO                               

  Remove security         Rejected                Unacceptable risk
  controls to save cost                           

  Keep all logs forever   Rejected                Unbounded cost/data
                                                  retention

  Delete logs to          Rejected                Operational blindness
  eliminate observability                         
  cost                                            

  Automatic resource      Rejected                Unsafe
  deletion from anomaly                           
  alert                                           

  Automatic deletion of   Rejected                Recovery/dependency risk
  apparent orphans                                

  Commit long-term before Rejected                Lock-in/waste
  workload stabilizes                             

  Spot for sole critical  Rejected                Availability risk
  path                                            

  Keep temporary          Rejected                Resource leakage
  environments forever                            

  One cost center for     Rejected                Poor accountability
  entire platform forever                         

  Cost optimization       Rejected                Security/contract risk
  drives IsolationProfile                         
  downgrade                                       
  --------------------------------------------------------------------------

------------------------------------------------------------------------

## 78. Consequences

### Positive

-   Cloud spending becomes attributable and explainable.
-   Shared-platform economics remain visible without creating false
    tenant boundaries.
-   ZuriBeans and Thamani can be financially distinguished while sharing
    infrastructure safely.
-   Idle and temporary resources receive explicit lifecycle governance.
-   Budgets/anomaly detection reduce surprise spend.
-   Right-sizing becomes evidence-based.
-   Future SaaS pricing can account for shared cost and isolation
    premiums.
-   Security/reliability requirements remain protected from unsafe
    optimization.

### Costs

-   Tagging and billing taxonomy require maintenance.
-   FinOps reviews consume operational time.
-   Cost tooling/alerts may require tuning.
-   Detailed shared-cost allocation can become complex.
-   Lifecycle automation requires safeguards.
-   Some resilient/security controls remain intentionally expensive.

These costs are accepted.

------------------------------------------------------------------------

## 79. Decision Rules

> **Taggable Production resources SHALL carry governed environment,
> service, owner, management and cost-attribution metadata where
> supported.**

> **Shared resources SHALL be labelled as shared and SHALL NOT be
> falsely assigned to the first tenant using them.**

> **Tenant/legal-entity tagging SHALL describe genuine dedicated
> attribution; it SHALL NOT define authorization.**

> **Budgets, forecasts and anomaly detection SHOULD provide early
> visibility into material spend changes.**

> **Cost alerts SHALL have an owner and SHALL NOT automatically
> terminate critical Production resources.**

> **Resource sizing SHALL use measured demand while preserving required
> reliability headroom.**

> **Non-Production resources SHOULD be scheduled/scaled down where
> safe.**

> **Logs, backups, images, objects and temporary resources SHALL have
> explicit lifecycle/retention policies.**

> **Orphan resources SHALL be detected, investigated and safely
> decommissioned rather than blindly deleted.**

> **Tenant deprovisioning SHALL NOT destroy shared infrastructure.**

> **Long-term AWS commitments SHALL follow evidence of stable
> consumption rather than speculation.**

> **Cost optimization SHALL NOT override accepted security, compliance,
> isolation, SLO, RPO or RTO requirements.**

> **Architecture SHALL nevertheless avoid unjustified over-provisioning
> and unnecessary dedicated infrastructure.**

> **ZuriBeans SHALL pass the defined cost-governance gate before
> Production go-live.**

------------------------------------------------------------------------

## 80. Implementation Implications

Implementation SHALL progressively establish:

``` text
Cost Governance
│
├── Metadata
│   ├── mandatory tags
│   ├── cost centers
│   ├── owners
│   └── IsolationProfile
│
├── Visibility
│   ├── Cost Explorer/reporting
│   ├── budgets
│   ├── forecasts
│   └── anomaly detection
│
├── Optimization
│   ├── ECS right-sizing
│   ├── RDS/cache/broker sizing
│   ├── network review
│   └── commitments
│
├── Lifecycle
│   ├── log retention
│   ├── backup lifecycle
│   ├── ECR lifecycle
│   ├── object lifecycle
│   └── temporary-resource expiry
│
├── Hygiene
│   ├── orphan detection
│   ├── decommissioning
│   └── tenant deprovisioning
│
└── FinOps
    ├── shared-cost allocation
    ├── service economics
    ├── tenant economics
    └── periodic review
```

------------------------------------------------------------------------

## 81. Completion of the Initial Infrastructure ADR Baseline

With acceptance of ADR-Infra-0024, the initial Baobab infrastructure
architecture baseline comprises:

``` text
ADR-Infra-0001  Environment Provisioner Boundary
ADR-Infra-0002  AWS Account, Environment and Region Strategy
ADR-Infra-0003  Terraform Architecture and Module Strategy
ADR-Infra-0004  Terraform State, Locking and Bootstrap
ADR-Infra-0005  Network and Trust-Zone Architecture
ADR-Infra-0006  Production Compute Platform
ADR-Infra-0007  Container Registry and Immutable Artifact Strategy
ADR-Infra-0008  DNS, TLS, Edge and API Gateway Architecture
ADR-Infra-0009  APISIX and etcd Production Architecture
ADR-Infra-0010  PostgreSQL Production Architecture
ADR-Infra-0011  Redis Production Architecture
ADR-Infra-0012  RabbitMQ Production Architecture
ADR-Infra-0013  Infrastructure IAM and Workload Identity
ADR-Infra-0014  Secrets, Keys and Certificate Management
ADR-Infra-0015  Tenant and Workload Infrastructure Isolation
ADR-Infra-0016  Observability and Telemetry Architecture
ADR-Infra-0017  SLOs, Health, Capacity and Operational Monitoring
ADR-Infra-0018  Backup, Restore and Data Retention
ADR-Infra-0019  Availability, Disaster Recovery and Business Continuity
ADR-Infra-0020  CI/CD and Infrastructure Change Governance
ADR-Infra-0021  Application Deployment, Promotion and Release Manifests
ADR-Infra-0022  Deployment Rollback and Database Change Safety
ADR-Infra-0023  Infrastructure Security, Compliance and Audit
ADR-Infra-0024  Cost Governance, Tagging and Resource Lifecycle
```

These ADRs SHALL now serve as the architectural source of truth for
implementation in `nabhold/infrastructure`.

Implementation SHALL inspect the accepted ADRs in all affected
repositories before changing cross-repository contracts or runtime
responsibilities.

Material departures SHALL require a superseding or additional ADR rather
than silent implementation divergence.
