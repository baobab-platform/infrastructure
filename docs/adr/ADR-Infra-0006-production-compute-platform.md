# ADR-Infra-0006 --- Production Compute Platform

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
-   **Follow-on:** ADR-Infra-0007 --- Container Registry and Immutable
    Artifact Strategy

------------------------------------------------------------------------

## 1. Context

Baobab requires a production compute platform for independently
deployable containerised workloads including:

-   `baobab-cp`;
-   `baobab-iam`;
-   `baobab-trade`;
-   `baobab-erp`;
-   `baobab-cms`;
-   `baobab-pulse`;
-   ZuriBeans;
-   Thamani;
-   workers and future digital estates.

The platform is polyrepo and polyglot. Infrastructure must therefore
provide a common execution substrate without imposing
application-language assumptions.

The current requirement favours operational simplicity, strong workload
isolation, private VPC networking, horizontal scaling, immutable
container deployment and low infrastructure-management overhead.

Kubernetes/EKS has previously been deliberately deferred.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use **Amazon ECS with AWS Fargate** as its default
production container compute platform.

ECS services SHALL run using **Fargate capacity providers** and `awsvpc`
networking.

Fargate is available in the selected initial region, AWS Africa (Cape
Town), `af-south-1`.

ECS on EC2, ECS Managed Instances, AWS Lambda, EKS or other compute
models MAY be adopted for specific workloads only where a demonstrated
requirement cannot be met appropriately by Fargate.

Kubernetes/EKS remains **deferred, not prohibited**.

------------------------------------------------------------------------

## 3. Rationale

Fargate provides the required production capabilities while avoiding
premature cluster-node management.

``` text
Container Image
      │
      ▼
ECS Task Definition
      │
      ▼
ECS Service / Task
      │
      ▼
Fargate Capacity
      │
      ▼
Private VPC Networking
```

This removes the immediate need to manage:

-   EC2 worker fleets;
-   node operating systems;
-   cluster patching;
-   instance packing;
-   node autoscaling;
-   Kubernetes control-plane conventions;
-   Kubernetes add-on lifecycle.

Baobab retains container portability and can revisit the compute
decision later.

------------------------------------------------------------------------

## 4. Compute Topology

``` text
                         Public Traffic
                              │
                              ▼
                     Edge / Load Balancer
                              │
                              ▼
                           APISIX
                              │
                              ▼
                    ┌───────────────────┐
                    │    ECS Cluster    │
                    │                   │
                    │  Fargate Services │
                    └─────────┬─────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
      Platform             Engines          Digital Estates
      Services
          │                   │                   │
     baobab-cp           baobab-trade          ZuriBeans
     baobab-iam          baobab-erp            Thamani
                         baobab-cms
                         baobab-pulse
                              │
                              ▼
                         Data Zone
```

The ECS cluster is a scheduling boundary, not a tenant boundary.

------------------------------------------------------------------------

## 5. Environment Model

Each AWS environment SHALL own its compute environment.

``` text
Development Account ──► Development ECS
Staging Account     ──► Staging ECS
Production Account  ──► Production ECS
```

Production workloads SHALL NOT execute in Development or Staging
clusters.

A shared Production ECS cluster MAY host multiple Baobab services and
digital estates where their approved IsolationProfiles permit it.

------------------------------------------------------------------------

## 6. Workload Unit

Each independently deployable workload SHALL normally have its own:

-   ECS task definition family;
-   ECS service or task execution model;
-   IAM task role;
-   security group;
-   log configuration;
-   health model;
-   scaling policy where required;
-   deployment lifecycle.

Unrelated applications SHALL NOT be combined into one task merely to
reduce task count.

``` text
ZuriBeans Task Definition  ──► ZuriBeans Service
Trade Task Definition      ──► Trade Service
CP Task Definition         ──► CP Service
```

Containers that must share lifecycle and localhost communication MAY
share a task definition when architecturally justified.

------------------------------------------------------------------------

## 7. Service Versus Task

Long-running workloads SHALL use ECS Services.

Examples:

-   APIs;
-   web applications;
-   gateway components;
-   continuously running workers;
-   long-lived engine services.

Finite, scheduled or event-triggered jobs MAY use standalone ECS Tasks.

``` text
Workload
   │
   ├── Long-running ──► ECS Service
   │
   └── Finite job ────► ECS Task
```

The compute platform SHALL NOT convert every background operation into a
permanent service.

------------------------------------------------------------------------

## 8. Networking

Fargate tasks SHALL use `awsvpc` networking and receive private VPC
connectivity.

Application tasks SHALL normally run in private Application Zone
subnets.

``` text
Fargate Task
     │
     ├── private IP
     ├── workload SG
     └── task IAM role
```

Public IP assignment to application tasks is prohibited by default.

Public traffic SHALL enter through the approved ingress architecture.

------------------------------------------------------------------------

## 9. Service Exposure

Internal services SHALL not be Internet-facing merely because they
expose HTTP APIs.

``` text
Internet
   │
   ▼
Approved Edge
   │
   ▼
APISIX
   │
   ▼
Private ECS Service
```

Direct public load balancers for individual workloads require explicit
justification.

Internal service discovery MAY use approved AWS/ECS mechanisms where
needed.

------------------------------------------------------------------------

## 10. Capacity Providers

ECS capacity provider strategies SHALL be preferred over directly
specifying launch type for service placement.

Production critical services SHALL use **FARGATE on-demand capacity**
for their required baseline.

`FARGATE_SPOT` MAY be used for interruption-tolerant workloads.

``` text
                   ECS Workload
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
         FARGATE               FARGATE_SPOT
     critical baseline       interrupt-tolerant
```

Critical availability SHALL NOT depend exclusively on Fargate Spot.

------------------------------------------------------------------------

## 11. Fargate Spot

Fargate Spot is subject to interruption and provides a short
interruption warning.

Appropriate workloads MAY include:

-   development workloads;
-   staging workloads where interruption is acceptable;
-   batch processing;
-   asynchronous recomputable work;
-   non-critical Pulse processing;
-   disposable workers.

It SHALL NOT be the sole capacity source for:

-   APISIX;
-   production IAM;
-   customer-facing critical APIs;
-   critical Control Plane services;
-   workloads unable to tolerate interruption.

------------------------------------------------------------------------

## 12. Availability

Production services requiring high availability SHOULD run multiple
tasks distributed across available subnets/AZs.

``` text
                   ECS Service
                       │
             desired_count >= 2
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
           AZ-A                AZ-B
          Task A               Task B
```

The exact minimum task count SHALL be determined by workload criticality
and SLOs.

A blanket requirement for two tasks SHALL NOT be imposed on every
workload irrespective of cost or failure semantics.

------------------------------------------------------------------------

## 13. Autoscaling

ECS Service Auto Scaling SHOULD be configured for workloads whose demand
varies materially.

Signals MAY include:

-   CPU utilisation;
-   memory utilisation;
-   request/load-balancer metrics;
-   queue depth;
-   workload-specific CloudWatch metrics.

``` text
Metric
  │
  ▼
Scaling Policy
  │
  ├── scale out
  └── scale in
        │
        ▼
   ECS Desired Count
```

Scaling limits SHALL define both minimum and maximum capacity.

Autoscaling SHALL NOT substitute for capacity planning.

------------------------------------------------------------------------

## 14. CPU and Memory

Each task definition SHALL declare explicit CPU and memory requirements.

Sizing SHALL be based on:

1.  measured workload behaviour;
2.  staging load tests;
3.  runtime characteristics;
4.  safety margin;
5.  cost.

Resource sizing SHALL NOT be copied blindly across different engines.

Java-based iDempiere, Go-based Control Plane, Node-based services and
Python-based Pulse may have materially different runtime profiles.

------------------------------------------------------------------------

## 15. Container Images

ECS SHALL execute immutable container image versions.

Production deployments MUST NOT rely on mutable tags such as:

``` text
latest
main
production
```

Deployment SHALL resolve to an immutable image digest or equivalently
immutable artifact reference.

The detailed registry, signing, provenance and SBOM policy is defined by
ADR-Infra-0007.

------------------------------------------------------------------------

## 16. Task Identity

Every workload SHALL use a dedicated ECS **task IAM role** appropriate
to its AWS permissions.

The task execution role and application task role SHALL remain
conceptually separate.

``` text
ECS
 │
 ├── Execution Role
 │     ├── image retrieval
 │     ├── log bootstrap
 │     └── approved secret injection
 │
 └── Task Role
       └── application AWS permissions
```

Applications SHALL NOT inherit broad infrastructure-deployment
permissions.

------------------------------------------------------------------------

## 17. Secrets

Secrets SHALL NOT be baked into container images or committed into task
definitions as plaintext.

Tasks SHALL obtain approved secrets through the secrets architecture.

``` text
Task
 │
 ▼
Workload Identity
 │
 ▼
Secrets Manager / Approved Store
```

Secret access SHALL be workload-specific.

------------------------------------------------------------------------

## 18. Persistent State

Fargate tasks SHALL be treated as replaceable compute.

Application state MUST NOT depend on the lifetime of a task's local
filesystem.

``` text
Task dies
   │
   ▼
Replacement Task
   │
   ▼
Service continues using external durable state
```

Durable state SHALL reside in approved external services such as
PostgreSQL, object storage or explicitly approved persistent storage.

Fargate persistent volume mechanisms MAY be used only where a workload
genuinely requires filesystem semantics.

------------------------------------------------------------------------

## 19. Ephemeral Storage

Fargate ephemeral storage MAY be used for:

-   temporary processing;
-   caches safe to lose;
-   transient files;
-   image/runtime working space.

It SHALL NOT be considered a backup or authoritative data store.

Workloads requiring unusually large temporary storage SHALL declare and
monitor that requirement explicitly.

------------------------------------------------------------------------

## 20. Health Checks

Every long-running service SHALL expose meaningful health signals.

Where applicable, distinguish:

-   process/container health;
-   service readiness;
-   downstream dependency degradation.

``` text
Task Starts
   │
   ▼
Container Health
   │
   ▼
Service Ready
   │
   ▼
Receives Traffic
```

A process merely listening on a port SHALL not automatically be
considered operationally healthy.

------------------------------------------------------------------------

## 21. Deployment Strategy

Production services SHALL use controlled rolling deployment by default.

Deployment configuration SHALL define:

-   minimum healthy capacity;
-   maximum deployment capacity;
-   health grace period where required;
-   rollback/failure detection;
-   deployment verification.

``` text
Old Revision
     │
     ▼
New Tasks Start
     │
     ▼
Health Verified
     │
     ▼
Traffic Shifts
     │
     ▼
Old Tasks Stop
```

Customer-facing services SHOULD avoid avoidable downtime during routine
deployment.

------------------------------------------------------------------------

## 22. Deployment Failure

Where supported, ECS deployment failure detection/circuit-breaker
capabilities SHOULD be enabled for appropriate services.

A failed revision SHALL NOT continue replacing healthy tasks
indefinitely.

``` text
Deploy
  │
  ▼
New Tasks
  │
  ├── Healthy ──► Continue
  │
  └── Failing ──► Stop / Roll Back
```

Detailed application rollback policy is governed by ADR-Infra-0022.

------------------------------------------------------------------------

## 23. Graceful Shutdown

Applications and workers SHALL handle termination signals gracefully.

Before termination they SHOULD, where applicable:

-   stop accepting new work;
-   complete or safely abandon in-flight operations;
-   release leases;
-   close connections;
-   flush telemetry within bounded time.

Long-running jobs SHALL define interruption semantics explicitly.

------------------------------------------------------------------------

## 24. Background Workers

Workers SHALL be independently deployable where they scale or fail
differently from APIs.

Preferred:

``` text
Trade API ───────► ECS Service A
Trade Worker ────► ECS Service B
```

Avoid:

``` text
Trade API + every worker
        │
        ▼
one inseparable scaling unit
```

This allows queue consumers and APIs to scale according to different
signals.

------------------------------------------------------------------------

## 25. Scheduled Work

Scheduled jobs SHOULD use event-driven scheduling of ECS tasks rather
than permanently running containers whose only purpose is waiting for a
schedule.

The selected scheduling mechanism SHALL preserve:

-   retry semantics;
-   observability;
-   workload identity;
-   failure reporting.

------------------------------------------------------------------------

## 26. Administrative Access

Routine production administration SHALL NOT require SSH access to
compute nodes because Fargate exposes no customer-managed worker nodes.

Where interactive container access is operationally necessary,
ECS-native controlled execution mechanisms MAY be enabled under least
privilege and audit controls.

Interactive production access SHALL be exceptional, authenticated and
auditable.

------------------------------------------------------------------------

## 27. Logging and Telemetry

Every task SHALL emit logs and telemetry through approved infrastructure
mechanisms.

At minimum, the compute platform SHALL support:

-   central logs;
-   task/service metrics;
-   deployment events;
-   resource utilisation;
-   distributed tracing where instrumented;
-   correlation identifiers.

Observability details are governed by ADR-Infra-0016.

------------------------------------------------------------------------

## 28. Service Discovery

Internal service discovery SHALL use an approved mechanism rather than
hard-coded task IP addresses.

Task IPs SHALL be considered ephemeral.

Potential mechanisms include:

-   load balancers;
-   private DNS;
-   ECS Service Connect;
-   Cloud Map where justified.

The simplest mechanism satisfying the service relationship SHOULD be
selected.

A service mesh SHALL NOT be introduced merely for internal naming.

------------------------------------------------------------------------

## 29. Stateful Engines

Fargate SHALL be the default compute platform, but this does not mean
every infrastructure dependency must run on Fargate.

Managed AWS services SHOULD be preferred for stateful infrastructure
where the relevant service ADR selects them.

``` text
Stateless / replaceable compute
           │
           ▼
      ECS Fargate

Persistent platform state
           │
           ▼
 Approved managed/durable service
```

Running a database in Fargate merely to standardise on containers is
rejected.

------------------------------------------------------------------------

## 30. Engine Compatibility

Before an engine is deployed to Fargate, implementation SHALL verify:

-   supported container architecture;
-   CPU/memory needs;
-   startup and shutdown behaviour;
-   filesystem requirements;
-   persistence requirements;
-   network ports;
-   health checks;
-   licensing;
-   horizontal-scaling behaviour;
-   background processing model.

A headless engine's container availability does not by itself prove
Fargate suitability.

------------------------------------------------------------------------

## 31. ZuriBeans Go-Live

ZuriBeans SHALL be the first end-to-end validation of the production
compute model.

Conceptually:

``` text
                       ECS / Fargate
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
      ZuriBeans         Baobab APIs        Workers
          │                 │                 │
          └─────────────────┼─────────────────┘
                            ▼
                         APISIX
                            │
                    approved routing
```

ZuriBeans SHALL receive only the Baobab capabilities required for its
B2B estate.

Its deployment SHALL not establish assumptions that force Thamani or
future tenants into the same application topology.

------------------------------------------------------------------------

## 32. Isolation Model

A shared ECS cluster SHALL NOT imply shared application identity or
shared data access.

Isolation SHALL be enforced through:

-   task IAM roles;
-   security groups;
-   task definitions;
-   service boundaries;
-   tenant-aware application authorization;
-   data isolation;
-   secrets;
-   approved IsolationProfiles.

Dedicated ECS clusters MAY be introduced where an accepted isolation or
operational requirement justifies them.

------------------------------------------------------------------------

## 33. Cost Strategy

Fargate is selected primarily for operational simplicity and workload
isolation, not because it is guaranteed to be the cheapest compute
option at every scale.

Cost SHALL be monitored.

A workload MAY be reconsidered for ECS Managed Instances, EC2 capacity
or another compute model where evidence demonstrates a material benefit
and operational implications are accepted.

Compute optimisation SHALL follow measurement, not speculation.

------------------------------------------------------------------------

## 34. When Fargate Is Not Appropriate

A workload MAY require another compute platform where it needs
capabilities such as:

-   specialised hardware unavailable to the selected Fargate
    configuration;
-   host-level control;
-   unusual networking;
-   economics materially favouring sustained instance-based capacity;
-   runtime constraints incompatible with Fargate;
-   platform functionality Fargate cannot provide.

Such exceptions SHALL be explicit and documented.

------------------------------------------------------------------------

## 35. Kubernetes / EKS Position

EKS remains deferred.

Baobab SHALL reconsider Kubernetes only when concrete requirements
justify its additional operational platform.

Potential triggers include:

-   a substantial Kubernetes-native ecosystem requirement;
-   scheduling capabilities unavailable through ECS;
-   portability requirements with measurable value;
-   complex platform operators/controllers;
-   workload scale or topology where Kubernetes provides demonstrable
    operational advantage.

``` text
Need Kubernetes?
      │
      ▼
Concrete unmet requirement?
   │             │
  No            Yes
   │             │
   ▼             ▼
Stay ECS      Evaluate ADR
```

Team familiarity or industry popularity alone is insufficient
justification.

------------------------------------------------------------------------

## 36. Serverless Functions

AWS Lambda MAY complement ECS for narrowly scoped event-driven functions
where appropriate.

Lambda SHALL NOT replace ECS as Baobab's general application runtime
under this ADR.

Introducing Lambda SHALL consider deployment, observability, IAM,
tenancy and operational ownership consistently with the wider platform.

------------------------------------------------------------------------

## 37. Compute Change Safety

Compute changes SHALL follow controlled promotion.

``` text
Container / Task Change
         │
         ▼
      CI Tests
         │
         ▼
    Development
         │
         ▼
      Staging
         │
         ▼
Load + Health Verification
         │
         ▼
 Production Approval
         │
         ▼
Controlled Deployment
         │
         ▼
Post-deploy Verification
```

Production deployment success SHALL require workload health, not merely
successful ECS API calls.

------------------------------------------------------------------------

## 38. Production Verification

The compute platform SHALL verify at minimum:

-   tasks run only in approved subnets;
-   public IPs are absent unless explicitly approved;
-   security groups match workload dependencies;
-   task roles are least-privilege;
-   immutable images are deployed;
-   health checks function;
-   unhealthy deployment behaviour is bounded;
-   logs and metrics are available;
-   critical services tolerate expected task replacement;
-   required multi-AZ placement works;
-   secrets are not exposed in task definitions or logs.

------------------------------------------------------------------------

## 39. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  EKS/Kubernetes now      Rejected                Operational complexity
                                                  without demonstrated
                                                  requirement

  Self-managed EC2 as     Rejected                Unnecessary
  default                                         node-management burden

  ECS on EC2 as default   Rejected                Fargate better matches
                                                  current operational
                                                  requirements

  ECS Managed Instances   Deferred                Re-evaluate when
  as default                                      workload
                                                  economics/control
                                                  justify it

  Docker Compose in       Rejected                Development-only model
  Production                                      

  One VM per Baobab       Rejected                Poor scaling and
  repository                                      operational consistency

  Lambda as general       Rejected                Not appropriate for all
  runtime                                         platform workloads

  Fargate Spot for all    Rejected                Interruption risk
  Production                                      

  Public IP per task      Rejected                Violates network
                                                  architecture

  Database containers on  Rejected                Stateful data requires
  Fargate by default                              dedicated architecture

  Shared task role across Rejected                Excessive privilege
  all services                                    

  Mutable production      Rejected                Weak release
  image tags                                      determinism

  Tenant-specific ECS     Rejected                Tenant does not imply
  cluster by default                              physical compute
                                                  boundary
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 40. Consequences

### Positive

-   No EC2 worker-node management.
-   Lower operational complexity than Kubernetes.
-   Strong task-level isolation.
-   Native private VPC networking.
-   Independent scaling of services and workers.
-   Supports the polyrepo/polyglot Baobab architecture.
-   Compatible with `af-south-1`.
-   Straightforward workload IAM.
-   Preserves future migration options through containerisation.
-   Provides a practical production path for ZuriBeans.

### Costs

-   Fargate may cost more than well-utilised instance fleets at
    sustained scale.
-   Fargate imposes runtime and task-definition constraints.
-   Task ENIs consume subnet address capacity.
-   Persistent filesystem requirements require separate design.
-   Some specialised workloads may need another compute model.
-   AWS ECS becomes part of the platform's operational dependency set.

These costs are accepted.

------------------------------------------------------------------------

## 41. Decision Rules

The following rules are authoritative:

> **Amazon ECS with AWS Fargate SHALL be Baobab's default production
> container compute platform.**

> **Fargate capacity providers SHALL be preferred for service
> placement.**

> **Production critical baseline capacity SHALL NOT depend exclusively
> on Fargate Spot.**

> **Fargate tasks SHALL use private `awsvpc` networking unless an
> explicit exception is approved.**

> **Each independently deployable workload SHALL normally have an
> independent task definition, IAM role and deployment lifecycle.**

> **Fargate tasks SHALL be replaceable; authoritative application state
> SHALL not depend on task-local storage.**

> **Production SHALL deploy immutable container artifacts.**

> **Tenant SHALL NOT imply ECS cluster.**

> **Kubernetes/EKS remains deferred until a concrete requirement
> justifies its operational cost.**

> **Compute selection exceptions SHALL be evidence-based and explicitly
> documented.**

> **ZuriBeans SHALL validate the compute architecture but SHALL NOT
> define platform-wide compute assumptions.**

------------------------------------------------------------------------

## 42. Implementation Implications

Implementation SHALL introduce a reusable Terraform compute capability
capable of expressing:

``` text
terraform/modules/compute/
├── ECS cluster
├── capacity providers
├── service definitions
├── task definitions
├── private subnet placement
├── workload security groups
├── task execution roles
├── task IAM roles
├── health configuration
├── autoscaling
├── logging integration
├── deployment controls
└── operational outputs
```

Application-specific definitions MAY be composed outside the generic
module where necessary to prevent the module from becoming a catalogue
of Baobab business applications.

Infrastructure SHALL support both long-running ECS Services and finite
ECS Tasks.

------------------------------------------------------------------------

## 43. References

This decision was checked against current AWS documentation on
2026-09-15:

-   AWS, **Supported Regions for Amazon ECS on AWS Fargate** ---
    confirms `af-south-1` support.
-   AWS, **Architect for AWS Fargate for Amazon ECS** --- Fargate
    serverless compute, task isolation, load balancing and capacity
    model.
-   AWS, **Amazon ECS task networking options for Fargate** --- `awsvpc`
    task ENIs and private VPC networking.
-   AWS, **Amazon ECS launch types and capacity providers** ---
    recommends capacity providers for compute-capacity configuration.
-   AWS, **Amazon ECS clusters for Fargate** --- Fargate and Fargate
    Spot capacity-provider behaviour.
-   AWS, **Amazon ECS task definition differences for Fargate** ---
    logging and persistent/ephemeral storage capabilities.

------------------------------------------------------------------------

## 44. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0007 --- Container Registry and Immutable Artifact
Strategy**

It shall define:

-   container registry ownership;
-   GHCR versus ECR responsibilities;
-   immutable image promotion;
-   digest-pinned deployment;
-   image naming;
-   semantic/release tagging;
-   SBOM generation;
-   provenance;
-   image signing;
-   vulnerability scanning;
-   retention;
-   cross-account access;
-   deployment artifact verification;
-   and the boundary between application repositories and
    `nabhold/infrastructure`.
