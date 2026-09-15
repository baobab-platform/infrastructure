# ADR-Infra-0008 --- DNS, TLS, Edge and API Gateway Architecture

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0001 --- Environment Provisioner Boundary
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0005 --- Network and Trust-Zone Architecture
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0007 --- Container Registry and Immutable Artifact
        Strategy
-   **Follow-on:** ADR-Infra-0009 --- APISIX and etcd Production
    Architecture

------------------------------------------------------------------------

## 1. Context

Baobab requires a stable and secure path from public users, B2B clients,
digital estates and approved integrations to privately hosted platform
workloads.

The architecture must support:

-   ZuriBeans as the first production digital estate;
-   future estates such as Thamani;
-   Baobab platform APIs;
-   tenant-aware and capability-aware routing;
-   TLS;
-   controlled public exposure;
-   private internal services;
-   APISIX as the API gateway;
-   separation of the APISIX traffic and administrative planes;
-   future SaaS domains and custom domains;
-   multi-environment and future multi-region operation.

DNS, TLS, load balancing and API gateway concerns are related but have
different ownership boundaries and SHALL not collapse into one
uncontrolled edge component.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use an AWS-managed public edge in front of privately hosted
APISIX and application workloads.

The default public request path SHALL be:

``` text
Client
  │
  ▼
Route 53
  │
  ▼
AWS Edge Protection
  │
  ▼
Application Load Balancer
  │
  │ TLS
  ▼
APISIX Traffic Plane
  │
  ▼
Approved Private Service
```

The initial architecture SHALL use:

-   **Amazon Route 53** for AWS-managed DNS;
-   **AWS Certificate Manager (ACM)** for AWS-managed public TLS
    certificates;
-   **Application Load Balancer (ALB)** as the principal HTTP/HTTPS
    ingress load balancer;
-   **AWS WAF** for Internet-facing HTTP-layer protection where
    required;
-   **APISIX** as Baobab's API gateway and application-routing policy
    layer;
-   private DNS for internal service names where required.

APISIX SHALL remain private behind the approved edge.

------------------------------------------------------------------------

## 3. Responsibility Separation

``` text
Route 53
   │
   │ name resolution
   ▼
ALB / Edge
   │
   │ TLS + edge reachability
   ▼
APISIX
   │
   │ API routing/policy
   ▼
Baobab Service
   │
   │ application authorization
   ▼
Domain Capability
```

Each layer has a distinct responsibility.

  Layer             Primary Responsibility
  ----------------- ------------------------------------------------------
  Route 53          DNS resolution
  ACM               Certificate lifecycle
  WAF               Edge HTTP threat filtering
  ALB               Public ingress and load distribution
  APISIX            API routing, gateway policies and upstream selection
  IAM/Application   Authentication, authorization and tenant context
  Service           Domain behaviour

DNS SHALL NOT perform application authorization.

APISIX SHALL NOT become the tenant system of record.

------------------------------------------------------------------------

## 4. Public DNS

Public DNS zones SHALL be managed declaratively where Baobab owns the
zone.

Public DNS SHALL expose only services intentionally reachable from
outside the VPC.

Conceptually:

``` text
Public Hosted Zone
│
├── www.<estate-domain>
├── api.<estate-domain>
├── platform API names where approved
└── verification/service records
```

Databases, Redis, RabbitMQ, APISIX Admin endpoints and
infrastructure-management endpoints SHALL NOT be published through
public DNS.

------------------------------------------------------------------------

## 5. Private DNS

Private DNS MAY provide stable names for internal services.

``` text
Private Hosted Zone
       │
       ├── internal gateway/service names
       ├── infrastructure endpoints
       └── approved service discovery names
```

Private names SHALL resolve only inside approved network boundaries.

Private DNS does not grant network access or application authorization.

------------------------------------------------------------------------

## 6. Domain Ownership

Digital-estate domains remain application/business assets even where DNS
infrastructure is managed through `nabhold/infrastructure`.

Infrastructure MAY provision:

-   hosted zones;
-   DNS records;
-   validation records;
-   certificate resources;
-   edge routing targets.

It SHALL NOT invent estate branding or business-domain policy.

------------------------------------------------------------------------

## 7. Environment DNS

Production, Staging and Development endpoints SHALL be distinguishable.

Production SHALL not depend on a staging hostname.

Example conceptual pattern:

``` text
Production: api.example.com
Staging:    api.staging.example.com
Development: environment-specific internal/dev name
```

Exact domain names are workload configuration and SHALL not be
hard-coded as universal Baobab architectural constants.

------------------------------------------------------------------------

## 8. Custom Domains

Baobab MAY support tenant/digital-estate custom domains.

A custom domain SHALL require controlled onboarding including:

``` text
Domain Request
     │
     ▼
Ownership / DNS Validation
     │
     ▼
Certificate Provisioning
     │
     ▼
Approved Edge Mapping
     │
     ▼
APISIX Route Binding
     │
     ▼
Verification
```

A hostname SHALL NOT become active merely because a tenant supplies a
string through an API.

------------------------------------------------------------------------

## 9. TLS Policy

Public production traffic SHALL use HTTPS.

Plain HTTP MAY exist only to redirect to HTTPS where required.

``` text
HTTP :80
   │
   ▼
Redirect
   │
   ▼
HTTPS :443
```

Weak or obsolete TLS configurations SHALL not be deliberately enabled
for legacy compatibility without an accepted exception.

------------------------------------------------------------------------

## 10. Certificate Management

AWS-managed public certificates SHALL normally use ACM.

Certificate lifecycle SHOULD include:

-   DNS validation;
-   automatic renewal where supported;
-   controlled domain ownership;
-   monitoring for renewal failure;
-   no private-key export where unnecessary.

Application repositories SHALL NOT contain production TLS private keys.

------------------------------------------------------------------------

## 11. TLS Termination

The default public TLS termination point SHALL be the AWS
edge/load-balancing layer.

Traffic from the edge toward APISIX SHOULD use TLS where the selected
topology and threat model justify or require encryption in transit.

``` text
Client
  │ HTTPS
  ▼
ALB
  │ HTTPS preferred/required by policy
  ▼
APISIX
  │
  ▼
Private Service
```

TLS termination at ALB SHALL NOT eliminate authentication or
authorization at APISIX/application layers.

------------------------------------------------------------------------

## 12. Internal Encryption

Sensitive service-to-service traffic SHOULD use TLS where supported.

The platform SHALL progressively enforce encryption in transit for:

-   gateway-to-service traffic;
-   service-to-database connections;
-   RabbitMQ clients;
-   Redis clients where supported by the selected production
    architecture;
-   management interfaces.

Detailed service-specific TLS requirements are defined in their
respective ADRs.

------------------------------------------------------------------------

## 13. Application Load Balancer

ALB SHALL provide the primary public Layer-7 ingress for the initial AWS
deployment.

ALB responsibilities include:

-   HTTPS listener;
-   certificate attachment;
-   health-aware target distribution;
-   controlled redirect from HTTP;
-   integration with AWS WAF;
-   forwarding to APISIX.

ALB SHALL NOT contain the full Baobab application-routing model.

------------------------------------------------------------------------

## 14. Why ALB Does Not Replace APISIX

ALB and APISIX solve different problems.

``` text
ALB
 │
 ├── AWS edge integration
 ├── TLS
 ├── WAF attachment
 └── target availability
       │
       ▼
APISIX
 │
 ├── API routing
 ├── gateway plugins
 ├── request policy
 ├── rate policy
 ├── upstream abstraction
 └── Baobab API governance
```

Using ALB SHALL not remove APISIX from the platform architecture.

------------------------------------------------------------------------

## 15. APISIX Traffic Plane

APISIX's traffic plane SHALL receive only traffic from approved ingress
or internal sources.

APISIX SHALL route requests to private upstream services.

``` text
ALB SG
  │
  ▼
APISIX Traffic SG
  │
  ▼
Service SG
```

Security groups SHALL restrict direct access to APISIX where practical.

------------------------------------------------------------------------

## 16. APISIX Administrative Plane

The APISIX Admin API SHALL be isolated from public traffic.

``` text
Internet
   │
   X
APISIX Admin API

Authorised Control / Management Identity
   │
   ▼
Private Admin Endpoint
```

The Admin API SHALL NOT share unrestricted exposure with the public
gateway listener.

Administrative credentials SHALL not be distributed to digital estates.

------------------------------------------------------------------------

## 17. Gateway Configuration Ownership

Infrastructure owns the APISIX runtime infrastructure.

Baobab Control Plane and approved platform mechanisms MAY own desired
gateway configuration within their defined responsibility.

``` text
nabhold/infrastructure
        │
        └── APISIX runtime availability
                  │
                  ▼
            APISIX Gateway
                  ▲
                  │
baobab-cp / approved configuration mechanism
        └── desired routes/policies
```

Terraform SHALL NOT become the normal mechanism for every tenant route
or dynamic API policy.

Static infrastructure bootstrap configuration MAY be provisioned through
infrastructure code.

------------------------------------------------------------------------

## 18. Route Model

Gateway routes SHALL identify approved upstream capabilities.

A route SHALL not infer tenant identity solely from network location.

Request processing MAY consider:

-   hostname;
-   path;
-   method;
-   authenticated principal;
-   tenant context;
-   capability;
-   market/context;
-   gateway policy.

The authoritative tenant and capability semantics remain outside the
infrastructure repository.

------------------------------------------------------------------------

## 19. Host-Based Routing

Hostnames MAY distinguish digital estates and API surfaces.

``` text
api.zuribeans.<domain>
        │
        ▼
      APISIX
        │
        ▼
Approved ZuriBeans-facing capabilities
```

Host-based routing is a routing mechanism, not proof of authorization.

------------------------------------------------------------------------

## 20. Path-Based Routing

APISIX MAY route by controlled API paths.

Conceptually:

``` text
/api/trade/*  ─────► baobab-trade
/api/iam/*    ─────► baobab-iam
/api/cp/*     ─────► approved CP surface
```

Actual external API contracts SHALL be defined by the owning
repositories.

Infrastructure SHALL not invent domain API paths merely to simplify
gateway configuration.

------------------------------------------------------------------------

## 21. Authentication Boundary

APISIX MAY enforce gateway-level authentication mechanisms where defined
by Baobab IAM architecture.

However:

``` text
Gateway Authentication
          │
          ▼
Application Authorization
          │
          ▼
Tenant/Capability Enforcement
```

A successful gateway authentication SHALL NOT automatically authorise
access to every upstream capability.

------------------------------------------------------------------------

## 22. Rate Limiting

APISIX MAY enforce rate and quota policies.

Rate limiting MAY be based on:

-   client identity;
-   API key where approved;
-   tenant;
-   route;
-   capability;
-   source;
-   service protection requirements.

Rate limits SHALL be explicit policy, not arbitrary infrastructure
defaults that break legitimate B2B traffic.

------------------------------------------------------------------------

## 23. AWS WAF

Internet-facing ALBs SHOULD be protected by AWS WAF where appropriate.

WAF controls MAY include:

-   managed rule groups;
-   known malicious request patterns;
-   IP reputation controls;
-   request-size constraints;
-   targeted rate-based rules;
-   workload-specific protections.

WAF SHALL not replace application validation or authorization.

------------------------------------------------------------------------

## 24. DDoS Protection

Baobab SHALL rely on AWS's baseline platform DDoS protections and SHOULD
evaluate enhanced protections according to risk, exposure and commercial
requirements.

The architecture SHALL not claim comprehensive DDoS resilience merely
because an ALB exists.

Operational monitoring and response remain required.

------------------------------------------------------------------------

## 25. Origin Protection

Application services SHALL not be directly reachable from the public
Internet.

The intended path is:

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
Private Upstream
```

Bypassing APISIX to access private APIs directly from the Internet is
prohibited unless a separately accepted architecture requires it.

------------------------------------------------------------------------

## 26. Health Checks

Health checks SHALL be layered.

``` text
ALB
 │
 └── verifies APISIX reachability
          │
          ▼
APISIX
 │
 └── evaluates upstream health
          │
          ▼
Application
      meaningful health endpoint
```

Health endpoints SHALL avoid exposing sensitive configuration.

A healthy gateway does not prove every upstream capability is healthy.

------------------------------------------------------------------------

## 27. Failure Behaviour

The edge SHALL fail predictably.

Examples:

  Failure                       Expected Behaviour
  ----------------------------- -----------------------------------------------
  Unhealthy APISIX task         Removed from ALB targets
  Unhealthy upstream            APISIX avoids/fails according to route policy
  Invalid hostname              No unintended tenant routing
  Expired/invalid certificate   Alert and prevent insecure fallback
  WAF rejection                 Request blocked before application
  DNS failure                   Operational alert; no insecure bypass

Fallback SHALL NOT silently route one tenant hostname to another estate.

------------------------------------------------------------------------

## 28. Observability

The edge path SHALL emit sufficient telemetry to investigate requests
across layers.

Relevant telemetry SHOULD include:

-   DNS/edge health where available;
-   ALB request/access information;
-   WAF actions;
-   APISIX access/error metrics;
-   upstream latency;
-   status codes;
-   correlation/trace identifiers where appropriate.

Sensitive credentials and tokens SHALL not be logged.

------------------------------------------------------------------------

## 29. Request Correlation

A request should be traceable conceptually as:

``` text
Client
  │ request/correlation ID
  ▼
ALB
  │
  ▼
APISIX
  │
  ▼
Service
  │
  ▼
Downstream Engine
```

The platform SHALL avoid generating incompatible identifiers at every
layer where propagation is feasible.

------------------------------------------------------------------------

## 30. Public Control Plane Exposure

Baobab Control Plane APIs SHALL NOT automatically be public merely
because the Control Plane exists.

Only explicitly approved Control Plane surfaces SHALL be routable from
public ingress.

Administrative and reconciliation APIs SHOULD remain private or strongly
restricted according to their purpose.

------------------------------------------------------------------------

## 31. Digital Estate Routing

Digital estates MAY expose:

-   public web frontend;
-   public/customer API;
-   authenticated B2B API;
-   webhook endpoints.

Each exposure SHALL be intentional.

A digital estate SHALL not gain public access to all underlying Baobab
engines.

``` text
ZuriBeans Public Surface
        │
        ▼
Approved Gateway Routes
        │
        ▼
Required Capabilities Only
```

------------------------------------------------------------------------

## 32. ZuriBeans Initial Edge Path

The initial ZuriBeans production flow SHALL conceptually be:

``` text
B2B Customer
     │
     ▼
ZuriBeans Domain
     │
     ▼
Route 53
     │
     ▼
HTTPS / ACM
     │
     ▼
AWS WAF
     │
     ▼
ALB
     │
     ▼
APISIX
     │
     ├──► ZuriBeans frontend/API
     ├──► IAM capability
     ├──► Trade capability
     └──► other explicitly approved capabilities
```

The actual capability bindings remain governed by Baobab Control Plane
and application ADRs.

------------------------------------------------------------------------

## 33. Thamani and Future Estates

Future estates SHALL reuse the edge architecture without requiring a
separate edge stack by default.

``` text
                  Shared Edge
                      │
                    APISIX
            ┌─────────┼─────────┐
            ▼         ▼         ▼
       ZuriBeans   Thamani    Future
```

Dedicated ingress MAY be introduced when an accepted IsolationProfile,
regulatory requirement, scale requirement or operational need justifies
it.

Tenant SHALL NOT imply dedicated ALB or APISIX instance.

------------------------------------------------------------------------

## 34. SaaS Evolution

The architecture SHALL support future SaaS onboarding patterns such as:

-   platform-managed subdomains;
-   verified customer domains;
-   automated certificate lifecycle;
-   tenant-aware gateway configuration.

Dynamic onboarding SHALL occur through approved platform workflows
rather than manual DNS console operations.

------------------------------------------------------------------------

## 35. DNS Change Safety

Production DNS changes SHALL be reviewed and deployed declaratively
where infrastructure owns the records.

Changes affecting:

-   hosted zones;
-   apex records;
-   aliases;
-   delegation;
-   certificate validation;
-   public gateway targets

SHALL receive heightened review because DNS errors may cause broad
outages.

------------------------------------------------------------------------

## 36. TTL Strategy

DNS TTL values SHALL balance operational stability, caching and change
requirements.

Short TTLs SHALL not be used universally.

Changes involving planned endpoint migration SHOULD consider TTL
reduction sufficiently before cutover where appropriate.

------------------------------------------------------------------------

## 37. Certificate Renewal Monitoring

Automatic ACM renewal reduces operational burden but does not eliminate
operational responsibility.

Monitoring SHOULD detect:

-   failed validation;
-   certificates approaching expiry;
-   broken DNS validation;
-   certificate/domain mismatch.

Production SHALL not depend on discovering certificate failure from
customer reports.

------------------------------------------------------------------------

## 38. Edge Configuration as Code

Infrastructure-owned edge resources SHALL be declarative.

Terraform SHOULD own:

-   hosted zones where appropriate;
-   infrastructure DNS records;
-   ACM certificates;
-   ALBs;
-   listeners;
-   target groups;
-   WAF resources;
-   network/security integration.

Dynamic APISIX routes and tenant policy SHALL not be forced into
Terraform where the Control Plane owns their lifecycle.

------------------------------------------------------------------------

## 39. Administrative Separation

The following surfaces SHALL remain distinct:

``` text
PUBLIC
  │
  └── ALB → APISIX Traffic Plane

PRIVATE
  │
  ├── APISIX Admin Plane
  ├── infrastructure management
  ├── internal services
  └── data services
```

A convenience route from the public gateway to administrative APIs is
prohibited.

------------------------------------------------------------------------

## 40. Future CDN

A CDN such as Amazon CloudFront MAY be introduced later for:

-   static digital-estate assets;
-   global caching;
-   edge optimisation;
-   additional security controls.

CloudFront is NOT required by this ADR for the initial ZuriBeans
production architecture.

Its adoption SHALL be justified by measured performance, geographic,
caching or security requirements.

------------------------------------------------------------------------

## 41. Multi-Region Readiness

DNS and edge naming SHALL avoid assumptions that prevent future regional
routing.

However, this ADR does NOT authorise:

-   active-active regional ingress;
-   latency-based multi-region routing;
-   global failover;
-   multi-region APISIX state;
-   cross-region tenant placement.

Those require explicit future decisions aligned with DR and multi-region
architecture.

------------------------------------------------------------------------

## 42. Security Invariants

The edge architecture SHALL maintain:

1.  HTTPS for public Production traffic;
2.  private application origins;
3.  private APISIX Admin API;
4.  no public databases/brokers/caches;
5.  least-privilege network access;
6.  explicit route ownership;
7.  application authorization after gateway authentication;
8.  controlled certificate lifecycle;
9.  auditable edge configuration;
10. no tenant inference solely from network location.

------------------------------------------------------------------------

## 43. Verification

Production readiness SHALL verify:

-   DNS resolves to intended endpoints;
-   HTTP redirects safely to HTTPS where enabled;
-   certificates match intended domains;
-   WAF is associated where required;
-   ALB reaches healthy APISIX tasks;
-   APISIX Admin API is not publicly reachable;
-   private upstreams are not publicly reachable;
-   unknown hostnames do not leak another estate;
-   approved routes reach correct upstreams;
-   denied routes remain denied;
-   health checks behave under task failure;
-   telemetry is available.

Successful Terraform apply alone is insufficient.

------------------------------------------------------------------------

## 44. Rejected Alternatives

  ---------------------------------------------------------------------------
  Alternative                Decision                Reason
  -------------------------- ----------------------- ------------------------
  Public APISIX Admin API    Rejected                Administrative-plane
                                                     exposure

  Public ECS services        Rejected                Bypasses controlled edge
  directly                                           

  Public                     Rejected                Violates trust-zone
  databases/brokers/caches                           architecture

  ALB replacing APISIX       Rejected                Does not provide Baobab
                                                     gateway governance

  APISIX replacing AWS edge  Rejected                Loses useful managed
  entirely                                           TLS/WAF/load-balancing
                                                     boundary

  TLS keys stored in         Rejected                Secret-management risk
  repositories                                       

  HTTP-only Production       Rejected                Inadequate transport
                                                     security

  Tenant-specific ALB by     Rejected                Tenant does not imply
  default                                            physical edge

  Tenant-specific APISIX by  Rejected                Unnecessary
  default                                            infrastructure
                                                     duplication

  Terraform managing every   Rejected                Violates Control
  dynamic tenant route                               Plane/runtime ownership
                                                     boundary

  CloudFront mandatory from  Rejected                No current requirement
  day one                                            

  Network location as        Rejected                Network is not identity
  authorization                                      

  Manual DNS as normal       Rejected                Weak reproducibility and
  operation                                          auditability
  ---------------------------------------------------------------------------

------------------------------------------------------------------------

## 45. Consequences

### Positive

-   Clear public-to-private request boundary.
-   AWS-managed TLS lifecycle.
-   Strong separation of gateway traffic and administration.
-   WAF integration at the edge.
-   APISIX remains the canonical API gateway.
-   Supports multiple digital estates without infrastructure-per-tenant
    sprawl.
-   Preserves dynamic Control Plane ownership of tenant routing.
-   Provides a clear ZuriBeans go-live ingress path.
-   Supports future custom domains and SaaS onboarding.

### Costs

-   ALB and APISIX introduce two routing layers.
-   Certificate and DNS ownership require governance.
-   WAF rules require tuning and monitoring.
-   Dynamic gateway configuration requires a controlled integration
    mechanism.
-   Custom domains increase certificate/DNS lifecycle complexity.
-   Future multi-region routing will require additional architecture.

These costs are accepted.

------------------------------------------------------------------------

## 46. Decision Rules

The following rules are authoritative:

> **Amazon Route 53 SHALL be the default AWS-managed DNS service for
> Baobab-owned AWS DNS zones.**

> **AWS Certificate Manager SHALL be the default public TLS certificate
> mechanism for AWS-hosted Production ingress.**

> **Application Load Balancer SHALL provide the initial managed
> HTTP/HTTPS edge in front of APISIX.**

> **APISIX SHALL remain Baobab's API gateway and SHALL run privately
> behind the approved edge.**

> **The APISIX Admin API SHALL NOT be publicly accessible.**

> **Public Production traffic SHALL use HTTPS.**

> **Application origins and data services SHALL remain private by
> default.**

> **ALB SHALL NOT replace APISIX's API-governance responsibilities.**

> **Terraform SHALL own infrastructure edge resources, but SHALL NOT
> become the normal lifecycle manager for dynamic tenant routes.**

> **Gateway authentication SHALL NOT replace application authorization
> and tenant/capability enforcement.**

> **Tenant SHALL NOT imply dedicated ALB, DNS infrastructure or APISIX
> instance.**

> **ZuriBeans SHALL validate the shared edge architecture without
> becoming a platform-wide special case.**

------------------------------------------------------------------------

## 47. Implementation Implications

Implementation SHALL introduce or extend Terraform capabilities for:

``` text
terraform/modules/
├── dns/
│   ├── Route 53 zones
│   └── controlled records
├── certificates/
│   └── ACM certificates + validation
└── edge/
    ├── ALB
    ├── HTTPS listeners
    ├── HTTP redirect
    ├── target groups
    ├── WAF association
    ├── security groups
    └── health checks
```

APISIX infrastructure SHALL expose separately controlled traffic and
administrative interfaces.

The production implementation SHALL include edge verification tests and
certificate/DNS operational runbooks.

------------------------------------------------------------------------

## 48. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0009 --- APISIX and etcd Production Architecture**

It shall define:

-   APISIX production topology;
-   APISIX control and traffic planes;
-   etcd production topology;
-   etcd quorum;
-   TLS and mutual authentication;
-   persistence;
-   backup and restore;
-   APISIX configuration ownership;
-   Admin API security;
-   gateway availability;
-   upgrades;
-   failure modes;
-   and the boundary between `nabhold/infrastructure` and Baobab Control
    Plane gateway reconciliation.
