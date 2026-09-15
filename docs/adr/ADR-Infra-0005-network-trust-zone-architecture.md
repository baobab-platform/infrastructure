# ADR-Infra-0005 --- Network and Trust-Zone Architecture

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0001 --- Environment Provisioner Boundary
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0003 --- Terraform Architecture and Module Strategy
    -   ADR-Infra-0004 --- Terraform State, Locking and Bootstrap
-   **Follow-on:** ADR-Infra-0006 --- Production Compute Platform

------------------------------------------------------------------------

## 1. Context

Baobab requires a production network architecture that supports:

-   multi-tenant platform services;
-   independent digital estates such as ZuriBeans and Thamani;
-   headless engines including Trade, ERP, CMS, Pulse and IAM;
-   Baobab Control Plane orchestration;
-   APISIX ingress;
-   PostgreSQL, Redis and RabbitMQ;
-   controlled outbound integrations;
-   production-grade observability;
-   environment and workload isolation;
-   future regional expansion.

The existing local Docker Compose topology already establishes the
conceptual separation of **edge**, **control**, **data**, and
**observability** networks.

Production SHALL preserve and strengthen these trust boundaries rather
than reproduce the Docker Compose topology literally.

------------------------------------------------------------------------

## 2. Decision

Each Baobab AWS environment SHALL use an environment-owned VPC with
explicit trust zones.

The production network SHALL implement four principal logical zones:

1.  **Ingress Zone**
2.  **Application Zone**
3.  **Data Zone**
4.  **Management Zone**

Connectivity SHALL follow **default deny, explicit allow**.

Resources SHALL be private unless public reachability is an explicit
architectural requirement.

------------------------------------------------------------------------

## 3. High-Level Topology

``` text
                         Internet
                            │
                            ▼
                  ┌──────────────────┐
                  │ Approved Public  │
                  │ Edge / Load      │
                  │ Balancing / WAF  │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │   INGRESS ZONE   │
                  │      APISIX      │
                  └────────┬─────────┘
                           │
                     approved routes
                           │
                           ▼
        ┌────────────────────────────────────┐
        │          APPLICATION ZONE          │
        │                                    │
        │  baobab-cp    baobab-iam           │
        │  baobab-trade baobab-erp           │
        │  baobab-cms   baobab-pulse         │
        │  ZuriBeans    future estates       │
        └───────────────┬────────────────────┘
                        │
                  approved service access
                        │
                        ▼
        ┌────────────────────────────────────┐
        │             DATA ZONE              │
        │                                    │
        │ PostgreSQL   Redis   RabbitMQ       │
        │ engine-specific persistent stores  │
        └────────────────────────────────────┘

                  MANAGEMENT ZONE
                        │
       ┌────────────────┼────────────────┐
       ▼                ▼                ▼
    CI/CD           Telemetry        Break-glass
 Infrastructure    administration    operations
```

The Management Zone is a trust boundary, not necessarily a single
subnet.

------------------------------------------------------------------------

## 4. VPC Strategy

Development, Staging and Production SHALL have independent VPC
boundaries.

``` text
AWS Organization
│
├── Development Account
│   └── Development VPC
│
├── Staging Account
│   └── Staging VPC
│
└── Production Account
    └── Production VPC
```

VPC peering between environments SHALL NOT be enabled by default.

Production SHALL NOT depend on Development or Staging network resources.

------------------------------------------------------------------------

## 5. Availability Zone Strategy

Production networking SHOULD span at least two Availability Zones for
workloads requiring high availability.

``` text
                     Production VPC
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
             AZ-A                      AZ-B
              │                         │
      ┌───────┼────────┐        ┌───────┼────────┐
      ▼       ▼        ▼        ▼       ▼        ▼
   Ingress   App      Data   Ingress   App      Data
   subnet   subnet   subnet   subnet   subnet   subnet
```

A third Availability Zone MAY be used where service architecture,
resilience or cost analysis justifies it.

Multi-AZ design SHALL NOT be represented as regional disaster recovery.

------------------------------------------------------------------------

## 6. Subnet Classes

The VPC SHALL distinguish subnet classes by trust and routing
requirements.

  --------------------------------------------------------------------------------
  Subnet Class                     Public IP     Internet Inbound Typical
                                                                  Workloads
  --------------------- -------------------- -------------------- ----------------
  Public/Ingress                  Controlled        Yes, approved Public load
                                                   endpoints only balancer/NAT
                                                                  where required

  Private/Application                     No     No direct access Baobab services
                                                                  and digital
                                                                  estates

  Private/Data                            No                   No PostgreSQL,
                                                                  Redis, RabbitMQ,
                                                                  stateful
                                                                  services

  Management                   No by default                   No Administrative
                                                                  or
                                                                  infrastructure
                                                                  services where
                                                                  dedicated
                                                                  placement is
                                                                  required
  --------------------------------------------------------------------------------

Application and Data subnets SHALL NOT automatically receive public IP
addresses.

------------------------------------------------------------------------

## 7. Ingress Zone

Only explicitly approved public entry points SHALL be Internet-facing.

The expected request path is:

``` text
Internet
   │
   ▼
DNS
   │
   ▼
TLS / Edge Protection
   │
   ▼
Public Load Balancer
   │
   ▼
APISIX
   │
   ▼
Approved Internal Service
```

Application services SHALL NOT bypass the approved ingress architecture
for ordinary public traffic.

The detailed edge, DNS, TLS and APISIX architecture is governed by later
ADRs.

------------------------------------------------------------------------

## 8. Application Zone

The Application Zone SHALL host compute workloads that execute Baobab
platform and digital-estate logic.

Typical workloads include:

-   `baobab-cp`;
-   `baobab-iam`;
-   `baobab-trade`;
-   `baobab-erp`;
-   `baobab-cms`;
-   `baobab-pulse`;
-   ZuriBeans;
-   Thamani;
-   approved workers and integration services.

Application workloads SHALL:

-   use private networking;
-   expose only required service ports;
-   receive workload-specific security groups;
-   use workload identity;
-   access Data Zone services only where explicitly authorised.

------------------------------------------------------------------------

## 9. Data Zone

The Data Zone SHALL contain persistent and sensitive data
infrastructure.

``` text
Application Workload
        │
        │ explicit SG rule
        ▼
     Data Service
```

Data services SHALL NOT be publicly accessible.

Typical services include:

-   PostgreSQL;
-   Redis;
-   RabbitMQ;
-   engine-specific databases;
-   other approved persistent stores.

Access SHALL be granted to workloads, not broadly to entire networks
where finer controls are available.

------------------------------------------------------------------------

## 10. Management Zone

Management-plane access SHALL be separated from normal application
traffic.

Management functions include:

-   Terraform provisioning;
-   CI/CD deployment;
-   telemetry administration;
-   infrastructure APIs;
-   controlled database administration;
-   incident response;
-   break-glass operations.

Digital estates SHALL NOT receive Management Zone credentials merely
because they consume Baobab services.

``` text
Digital Estate
      │
      X
Management Credentials

Authorised Operator / CI
      │
      ▼
Management Boundary
```

------------------------------------------------------------------------

## 11. Security Groups

Security groups SHALL be the principal workload-level network access
control mechanism.

Rules SHOULD reference security groups rather than broad CIDR ranges
where practical.

Preferred:

``` text
Trade Service SG
       │
       ▼
PostgreSQL SG : 5432
```

Avoid:

``` text
10.0.0.0/8
    │
    ▼
PostgreSQL : 5432
```

Security groups SHALL follow least privilege and explicit service
relationships.

------------------------------------------------------------------------

## 12. Network ACLs

Network ACLs MAY provide coarse subnet-level safeguards.

They SHALL NOT replace workload-level security groups.

Complex NACL rule sets SHOULD be avoided unless a concrete security
requirement justifies them.

The architecture preference is:

``` text
Routing Boundary
      +
Security Groups
      +
Identity Controls
      +
Application Authorization
```

Network location alone SHALL NOT establish trust.

------------------------------------------------------------------------

## 13. Default-Deny Connectivity

New services SHALL NOT automatically receive access to all platform
services.

Connectivity must be justified by an explicit dependency.

``` text
New Workload
     │
     ▼
Required dependency?
   │       │
  Yes      No
   │       │
   ▼       ▼
Allow     Deny
minimum
ports
```

Security rules SHALL be reviewable as infrastructure code.

------------------------------------------------------------------------

## 14. East-West Traffic

Internal service-to-service traffic SHALL remain private.

Where services communicate across trust boundaries:

-   only required ports SHALL be permitted;
-   TLS SHOULD be used where supported and appropriate;
-   application authentication/authorization SHALL remain mandatory;
-   tenant context SHALL NOT be inferred from source IP.

``` text
Service A
   │
   │ network permission
   ▼
Service B
   │
   └── still validates identity + authorization + context
```

Network permission does not equal application authorization.

------------------------------------------------------------------------

## 15. Outbound Internet Access

Private workloads SHALL NOT receive unrestricted outbound Internet
access by default.

Outbound requirements SHALL be identified explicitly.

Typical legitimate requirements include:

-   external APIs;
-   package or image retrieval during controlled operations;
-   email/SMS providers;
-   payment providers;
-   government/open-data sources;
-   FX, weather and trade-data sources used by Baobab Pulse.

Where practical, outbound traffic SHOULD be:

-   routed through controlled egress;
-   observable;
-   restricted by destination/service;
-   minimised using VPC endpoints.

------------------------------------------------------------------------

## 16. NAT Strategy

NAT Gateways MAY provide outbound Internet connectivity for private
subnets where required.

Production design SHALL consider both availability and cost.

``` text
Private Application Subnet
          │
          ▼
      Route Table
          │
          ▼
      NAT Gateway
          │
          ▼
       Internet
```

NAT SHALL NOT be used as justification for unrestricted egress.

A highly available production design SHOULD avoid a single-AZ NAT
dependency for workloads whose availability requires continued outbound
connectivity.

------------------------------------------------------------------------

## 17. VPC Endpoints

AWS PrivateLink/VPC endpoints SHOULD be used where they materially
improve security, availability or NAT cost.

Candidates may include:

-   S3;
-   ECR;
-   CloudWatch;
-   Secrets Manager;
-   Systems Manager;
-   STS;
-   KMS;
-   other AWS services consumed privately.

Endpoint adoption SHALL be driven by actual workload requirements rather
than implemented speculatively.

------------------------------------------------------------------------

## 18. Administrative Access

Production SHALL NOT depend on publicly exposed SSH administration.

Preferred operational access SHALL use controlled AWS-native or
equivalent mechanisms with auditable identity.

``` text
Operator
   │
   ▼
Federated Identity
   │
   ▼
Approved Management Path
   │
   ▼
Private Resource
```

Bastion hosts SHALL NOT be introduced by default.

If a bastion becomes necessary, it requires explicit security
justification and hardened lifecycle controls.

------------------------------------------------------------------------

## 19. Database Administration

Production databases SHALL remain private during administrative
operations.

Administration MUST NOT be enabled by temporarily making a database
publicly accessible.

Approved paths MAY include:

-   controlled management workloads;
-   AWS-native secure session mechanisms;
-   tightly scoped temporary access.

Administrative access SHALL be logged and revocable.

------------------------------------------------------------------------

## 20. APISIX Boundary

APISIX is the Baobab API gateway and belongs to the Ingress/control
boundary.

Its public traffic plane and administrative plane SHALL be separated.

``` text
                    APISIX
                 ┌─────┴─────┐
                 ▼           ▼
           Traffic Plane   Admin Plane
                 │           │
            approved       management
             ingress         only
```

The APISIX Admin API MUST NOT be publicly exposed.

Only authorised infrastructure/control-plane identities SHALL reach
administrative endpoints.

------------------------------------------------------------------------

## 21. RabbitMQ Connectivity

RabbitMQ SHALL be private.

Only approved publishers, consumers and administrators SHALL reach
required RabbitMQ ports.

``` text
Publisher SG ───► RabbitMQ SG ◄─── Consumer SG
                       ▲
                       │
                 Management SG
```

RabbitMQ management interfaces SHALL NOT be Internet-facing.

------------------------------------------------------------------------

## 22. Redis Connectivity

Redis SHALL remain private and reachable only by authorised workloads.

Redis MUST NOT be treated as a public or cross-tenant integration
interface.

Where Redis contains tenant-aware projections or caches,
application-layer isolation remains mandatory.

------------------------------------------------------------------------

## 23. PostgreSQL Connectivity

PostgreSQL SHALL be hosted in private Data Zone subnets.

``` text
Authorised Service SG
        │
        ▼
PostgreSQL SG : 5432
```

`0.0.0.0/0` database ingress is prohibited.

Database isolation and tenancy semantics are governed separately;
network topology SHALL not invent tenant boundaries.

------------------------------------------------------------------------

## 24. Observability Traffic

Telemetry SHOULD use private internal paths where practical.

``` text
Workloads
   │
   ├── traces
   ├── metrics
   └── logs
       │
       ▼
OpenTelemetry
       │
       ▼
Approved Observability Backend
```

Observability infrastructure SHALL NOT sit in the synchronous
authentication or request-critical path.

Telemetry failure MUST NOT normally cause application request failure.

------------------------------------------------------------------------

## 25. DNS

Public and private DNS responsibilities SHALL be distinguished.

``` text
Public DNS
   │
   ▼
Approved External Endpoints

Private DNS
   │
   ▼
Internal Services
```

Internal databases, brokers, caches and management endpoints SHALL NOT
receive public DNS exposure merely for convenience.

Detailed DNS and certificate architecture is governed by ADR-Infra-0008.

------------------------------------------------------------------------

## 26. Tenant Isolation

Network architecture SHALL NOT equate tenant with VPC.

Default:

``` text
Production VPC
      │
      ├── Shared Platform
      ├── ZuriBeans
      ├── Thamani
      └── Future Estates
```

Isolation SHALL combine:

-   workload identity;
-   application authorization;
-   tenant context;
-   data isolation;
-   security groups;
-   capability bindings;
-   approved `IsolationProfile`.

Dedicated VPC or network infrastructure MAY be used where an
IsolationProfile or regulatory requirement explicitly demands it.

------------------------------------------------------------------------

## 27. Cross-Environment Connectivity

The default relationship is:

``` text
Development VPC     Staging VPC     Production VPC
      │                   │                 │
      X───────────────────X─────────────────X
                No implicit connectivity
```

Cross-environment peering or transit connectivity requires explicit
justification.

Production services MUST NOT depend on a Development endpoint.

------------------------------------------------------------------------

## 28. Third-Party Integrations

External integrations SHALL enter or leave Baobab through controlled
paths.

Inbound third-party callbacks SHOULD use approved ingress endpoints.

Outbound integrations SHOULD originate from known, observable network
paths where practical.

Direct third-party access to Data Zone resources is prohibited unless
governed by a specific architecture decision.

------------------------------------------------------------------------

## 29. Multi-Region Readiness

CIDR allocation and network naming SHALL avoid unnecessary assumptions
that prevent future regional expansion.

However, this ADR does NOT authorise:

-   cross-region VPC peering;
-   Transit Gateway;
-   active-active networking;
-   global database networking;
-   global traffic management.

These require explicit future decisions.

------------------------------------------------------------------------

## 30. CIDR Management

Environment CIDR ranges SHALL be centrally planned to prevent overlap.

The Terraform network module SHALL validate approved CIDR configuration
where practical.

CIDR ranges SHOULD reserve sufficient address capacity for:

-   multiple Availability Zones;
-   application workloads;
-   data services;
-   ingress;
-   future growth.

Exact ranges SHALL be implementation configuration rather than
hard-coded architectural constants unless separately approved.

------------------------------------------------------------------------

## 31. Network Change Safety

Changes affecting routing, security groups, subnet associations, NAT,
gateways or ingress SHALL be treated as potentially
production-impacting.

``` text
Network Change
     │
     ▼
Terraform Plan
     │
     ▼
Security Review
     │
     ▼
Staging Verification
     │
     ▼
Production Approval
     │
     ▼
Apply + Connectivity Tests
```

Network changes SHALL include rollback or recovery consideration.

------------------------------------------------------------------------

## 32. Verification

Infrastructure deployment SHALL verify critical network invariants.

Examples:

-   Data services are not publicly reachable;
-   APISIX Admin API is private;
-   application workloads can reach required dependencies;
-   unauthorised workloads cannot reach protected services;
-   public traffic reaches only approved ingress;
-   Production has no unintended Development dependency;
-   outbound connectivity matches policy.

A successful Terraform apply alone is insufficient evidence of network
correctness.

------------------------------------------------------------------------

## 33. ZuriBeans Go-Live Path

The initial production request path SHOULD conceptually be:

``` text
Customer
   │
   ▼
Public DNS / TLS
   │
   ▼
Edge / Load Balancer
   │
   ▼
APISIX
   │
   ▼
ZuriBeans / Required Baobab API
   │
   ├────► baobab-iam
   ├────► baobab-trade
   ├────► baobab-cp
   └────► other approved capabilities
                 │
                 ▼
           Private Data Zone
```

ZuriBeans SHALL NOT receive direct network access to every Baobab engine
merely because it is the first production estate.

Access SHALL correspond to required capabilities and approved service
relationships.

------------------------------------------------------------------------

## 34. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Flat VPC with           Rejected                Excessive blast radius
  unrestricted internal                           
  access                                          

  Public databases        Rejected                Unnecessary exposure

  Public RabbitMQ/Redis   Rejected                Data/control-plane risk

  Public APISIX Admin API Rejected                Administrative plane
                                                  exposure

  VPC per tenant by       Rejected                Tenant does not imply
  default                                         physical network

  Security by subnet      Rejected                Network location is not
  alone                                           identity

  Open outbound Internet  Rejected                Weak egress control
  by default                                      

  Public SSH              Rejected                Avoidable management
  administration                                  exposure

  Bastion host by default Rejected                Additional attack
                                                  surface and operations

  Cross-environment       Rejected                Weakens environment
  peering by default                              isolation

  Kubernetes network      Rejected                Compute platform
  architecture now                                decision remains
                                                  separate

  Premature multi-region  Rejected                No accepted requirement
  networking                                      yet
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 35. Consequences

### Positive

-   Strong trust boundaries.
-   Private application and data workloads.
-   Reduced lateral-movement risk.
-   Clear separation of ingress and administration.
-   Supports multi-tenant workloads without VPC-per-tenant sprawl.
-   Provides production parity with the conceptual local topology.
-   Supports future multi-AZ and regional evolution.
-   Gives Terraform explicit network invariants to enforce.

### Costs

-   Security-group relationships require disciplined maintenance.
-   NAT and private endpoints introduce cost.
-   Multi-AZ networking is more complex than a single subnet topology.
-   Troubleshooting requires good telemetry and network documentation.
-   Egress control requires knowledge of external dependencies.

These costs are accepted.

------------------------------------------------------------------------

## 36. Decision Rules

The following rules are authoritative:

> **Baobab AWS environments SHALL use independent VPC boundaries.**

> **Production networking SHALL implement Ingress, Application, Data and
> Management trust zones.**

> **Connectivity SHALL be default deny and explicitly allowed.**

> **Application and Data Zone resources SHALL be private by default.**

> **PostgreSQL, Redis and RabbitMQ SHALL NOT be publicly accessible.**

> **The APISIX administrative plane SHALL NOT be publicly accessible.**

> **Network permission SHALL NOT substitute for workload identity,
> authorization or tenant-context validation.**

> **Tenant SHALL NOT imply VPC.**

> **Cross-environment connectivity SHALL be prohibited by default.**

> **Production administration SHALL NOT depend on public SSH.**

> **Outbound Internet access SHALL be intentional and controlled.**

> **Multi-AZ availability SHALL NOT be described as regional disaster
> recovery.**

------------------------------------------------------------------------

## 37. Implementation Implications

Implementation SHALL introduce a reusable Terraform `network` module
capable of expressing at minimum:

``` text
terraform/modules/network/
├── VPC
├── Availability Zone placement
├── public/ingress subnets
├── private/application subnets
├── private/data subnets
├── route tables
├── Internet Gateway where required
├── NAT where approved
├── VPC endpoints where approved
├── security groups
├── network metadata/tags
└── validation outputs
```

Environment compositions SHALL supply environment-specific CIDR ranges
and capacity choices.

Production readiness SHALL include network verification tests rather
than relying solely on Terraform state.

------------------------------------------------------------------------

## 38. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0006 --- Production Compute Platform**

It shall decide and define:

-   the production workload execution platform;
-   ECS/Fargate versus alternative compute models;
-   service and worker deployment;
-   autoscaling;
-   workload isolation;
-   task/service networking;
-   health checks;
-   rolling deployment;
-   resource sizing;
-   workload identity;
-   image execution;
-   operational access;
-   failure recovery;
-   and why Kubernetes/EKS remains deferred or becomes justified.
