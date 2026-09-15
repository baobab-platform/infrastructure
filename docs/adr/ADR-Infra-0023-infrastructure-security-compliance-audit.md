# ADR-Infra-0023 --- Infrastructure Security, Compliance and Audit

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
    -   ADR-Infra-0013 --- Infrastructure IAM and Workload Identity
    -   ADR-Infra-0014 --- Secrets, Keys and Certificate Management
    -   ADR-Infra-0015 --- Tenant and Workload Infrastructure Isolation
    -   ADR-Infra-0016 --- Observability and Telemetry Architecture
    -   ADR-Infra-0018 --- Backup, Restore and Data Retention
    -   ADR-Infra-0019 --- Availability, Disaster Recovery and Business
        Continuity
    -   ADR-Infra-0020 --- CI/CD and Infrastructure Change Governance
    -   ADR-Infra-0021 --- Application Deployment, Promotion and Release
        Manifests
    -   ADR-Infra-0022 --- Deployment Rollback and Database Change
        Safety
-   **Follow-on:** ADR-Infra-0024 --- Cost Governance, Tagging and
    Resource Lifecycle

------------------------------------------------------------------------

## 1. Context

Baobab will process commercially sensitive, identity, operational and
potentially personal information across multiple legal entities, markets
and engines.

Infrastructure security must protect:

-   ZuriBeans and future tenant workloads;
-   Control Plane state;
-   IAM identities;
-   Trade and ERP data;
-   CMS content;
-   event infrastructure;
-   secrets and cryptographic material;
-   deployment infrastructure;
-   audit evidence;
-   backups.

Security must also remain compatible with Baobab's architecture:

``` text
Shared Platform
     │
     ├── Multiple Legal Entities
     ├── Multiple Digital Estates
     ├── Multiple Markets
     ├── Multiple Engines
     └── Multiple IsolationProfiles
```

Compliance is not achieved by enabling a single AWS security product.

The platform requires a layered, evidence-producing security
architecture.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL implement **defence in depth** across:

1.  identity;
2.  network;
3.  compute;
4.  data;
5.  secrets and cryptography;
6.  software supply chain;
7.  detection;
8.  audit;
9.  recovery;
10. governance.

Security controls SHALL be automated and continuously evaluated where
practical.

Compliance SHALL be evidence-based and mapped to actual legal,
contractual and policy obligations.

------------------------------------------------------------------------

## 3. Shared Responsibility

AWS secures the underlying cloud infrastructure.

Nabhold remains responsible for security **in** its cloud environment,
including:

-   IAM configuration;
-   workload permissions;
-   network exposure;
-   data classification;
-   encryption configuration;
-   application security;
-   secrets;
-   logging;
-   monitoring;
-   vulnerability response;
-   tenant isolation;
-   legal compliance.

Using a managed AWS service SHALL not transfer these responsibilities to
AWS.

------------------------------------------------------------------------

## 4. Security Principles

The Production security baseline SHALL follow:

``` text
Least Privilege
      +
Default Deny
      +
Strong Identity
      +
Encryption
      +
Immutable Delivery
      +
Continuous Detection
      +
Auditability
      +
Recoverability
```

------------------------------------------------------------------------

## 5. Security by Default

New Production resources SHALL inherit secure defaults.

Examples:

-   private networking unless public access is explicitly required;
-   encryption enabled;
-   no wildcard administrator workload roles;
-   logging enabled where meaningful;
-   secrets externalized;
-   public access blocked for data stores;
-   immutable artifacts;
-   mandatory ownership/environment tags.

A secure posture SHALL not depend on every engineer remembering optional
settings.

------------------------------------------------------------------------

## 6. Identity Security

ADR-Infra-0013 remains authoritative.

Production SHALL use:

-   federated human access;
-   MFA where applicable;
-   GitHub Actions OIDC;
-   workload IAM roles;
-   short-lived credentials;
-   least privilege;
-   dedicated break-glass procedures.

Long-lived AWS access keys SHALL not be normal operational credentials.

------------------------------------------------------------------------

## 7. Root Account

AWS root credentials SHALL not be used for routine administration.

Root access SHALL be:

-   strongly protected;
-   MFA secured;
-   monitored;
-   used only for operations requiring root.

Root activity SHALL generate a high-priority security signal.

------------------------------------------------------------------------

## 8. Privileged Access

Administrative privileges SHALL be separated from normal engineering
access.

``` text
Engineer
   │
   ├── normal read/deploy permissions
   │
   └── approved elevation
             │
             ▼
       privileged action
```

Persistent broad administrator access SHALL be minimized.

------------------------------------------------------------------------

## 9. Break-Glass

Break-glass access SHALL be:

-   exceptional;
-   strongly authenticated;
-   auditable;
-   time-limited where practical;
-   reviewed after use.

Break-glass SHALL not become a shortcut around CI/CD governance.

------------------------------------------------------------------------

## 10. Network Security

ADR-Infra-0005 remains authoritative.

The network baseline SHALL use:

``` text
Internet
   │
   ▼
Ingress Zone
   │
   ▼
Application Zone
   │
   ▼
Data Zone

Management Zone ── controlled separately
```

Data services SHALL remain private.

------------------------------------------------------------------------

## 11. Default-Deny Connectivity

Security groups SHALL permit only required flows.

Examples:

``` text
ALB      → APISIX
APISIX   → approved service
Service  → approved database/cache/broker
CI role  → approved AWS APIs
```

"Inside the VPC" SHALL NOT imply trusted.

------------------------------------------------------------------------

## 12. Public Exposure

Public endpoints SHALL be explicitly approved.

The following SHALL NOT be publicly reachable in Production:

-   PostgreSQL;
-   Redis/Valkey;
-   RabbitMQ management/AMQP endpoints;
-   etcd;
-   APISIX Admin API;
-   internal service management endpoints.

Public exposure discovered outside accepted architecture SHALL be
treated as a security defect.

------------------------------------------------------------------------

## 13. Edge Protection

Public Production services SHOULD use appropriate AWS edge protections
including:

-   TLS;
-   ALB;
-   WAF where risk justifies;
-   request limits;
-   rate limiting;
-   gateway authentication/authorization integration;
-   denial-of-service protections inherent in the selected AWS
    architecture.

Edge controls SHALL complement, not replace, application authorization.

------------------------------------------------------------------------

## 14. Encryption in Transit

Production network communication carrying credentials, personal
information or sensitive business data SHALL use encrypted transport.

TLS verification SHALL not be disabled merely to simplify integration.

Internal mTLS MAY be required for high-trust interfaces such as etcd or
management channels.

------------------------------------------------------------------------

## 15. Encryption at Rest

Sensitive Production data SHALL use encryption at rest.

This includes, where supported:

-   RDS;
-   ElastiCache;
-   S3;
-   backups;
-   Terraform state;
-   CloudTrail archives;
-   Secrets Manager;
-   logs containing sensitive operational metadata.

KMS usage SHALL follow ADR-Infra-0014.

------------------------------------------------------------------------

## 16. Data Classification

Data SHALL be classified sufficiently to drive security and retention.

A practical platform classification is:

  -----------------------------------------------------------------------
  Class                               Description
  ----------------------------------- -----------------------------------
  **Public**                          Approved for public disclosure

  **Internal**                        Operational/internal information

  **Confidential**                    Business, tenant or commercially
                                      sensitive

  **Restricted**                      High-impact personal, credential,
                                      key or regulated data
  -----------------------------------------------------------------------

Existing Baobab tenancy/data-classification contracts take precedence
where more specific.

------------------------------------------------------------------------

## 17. Data Minimization

Infrastructure and observability SHALL collect only data necessary for
their purpose.

Telemetry SHALL not become an uncontrolled secondary copy of:

-   customer records;
-   payment information;
-   identity documents;
-   secrets;
-   full request payloads.

ADR-Infra-0016 governs telemetry minimization.

------------------------------------------------------------------------

## 18. Tenant and Legal-Entity Isolation

ADR-Infra-0015 remains authoritative.

Security controls SHALL preserve separation among:

-   ZuriBeans;
-   Thamani;
-   Nabhold;
-   future legal entities;
-   external SaaS tenants.

Common ownership SHALL NOT imply shared authorization.

------------------------------------------------------------------------

## 19. Negative Authorization

Production security testing SHALL include explicit denial cases.

Examples:

``` text
ZuriBeans identity → Thamani secret       DENY
ZuriBeans identity → Thamani data         DENY
Unbound capability → engine               DENY
Application role → Terraform state        DENY
Application role → KMS administration     DENY
Public internet → RDS                     DENY
```

Expected-deny testing is mandatory for critical boundaries.

------------------------------------------------------------------------

## 20. Application IAM vs AWS IAM

AWS IAM SHALL govern AWS infrastructure/resource access.

`baobab-iam` SHALL govern application users, clients, roles and service
authorization according to accepted IAM ADRs.

AWS task-role possession SHALL not be treated as tenant membership.

------------------------------------------------------------------------

## 21. Secrets

ADR-Infra-0014 remains authoritative.

Secrets SHALL NOT be stored in:

-   Git;
-   images;
-   plaintext Terraform;
-   release manifests;
-   logs;
-   documentation.

Secret access SHALL be workload-specific and auditable.

------------------------------------------------------------------------

## 22. Cryptographic Keys

KMS key access SHALL separate:

-   administration;
-   encryption/decryption usage;
-   recovery;
-   deletion.

Key deletion SHALL receive heightened approval.

A key required to decrypt retained backup/audit data SHALL not be
removed prematurely.

------------------------------------------------------------------------

## 23. Software Supply Chain

Production artifacts SHALL follow ADR-Infra-0007 and ADR-Infra-0021.

Security controls SHOULD include:

-   dependency scanning;
-   container vulnerability scanning;
-   SBOM generation;
-   provenance;
-   artifact signing/verification where implemented;
-   immutable digests;
-   pinned CI dependencies.

Production SHALL not deploy arbitrary unverified images.

------------------------------------------------------------------------

## 24. Vulnerability Management

Security findings SHALL be triaged by:

-   severity;
-   exploitability;
-   exposure;
-   affected workload;
-   data sensitivity;
-   available mitigation.

A vulnerability scanner result alone SHALL not determine business
priority without context.

Critical exploitable vulnerabilities on exposed Production paths SHALL
receive urgent remediation.

------------------------------------------------------------------------

## 25. Base Images

Application repositories SHALL use maintained, approved base images.

Images SHOULD:

-   minimize unnecessary packages;
-   avoid embedded build tools in runtime stages where unnecessary;
-   run as non-root where compatible;
-   be rebuilt when critical dependencies require remediation.

Image age SHALL be monitored.

------------------------------------------------------------------------

## 26. ECS Runtime Security

Production ECS/Fargate workloads SHOULD use:

-   non-root containers where supported;
-   read-only root filesystem where compatible;
-   minimal Linux capabilities;
-   no privileged mode;
-   no host filesystem assumptions;
-   scoped task roles;
-   resource limits;
-   controlled ECS Exec.

Fargate reduces host-management burden but does not remove
application/container security responsibilities.

------------------------------------------------------------------------

## 27. ECS Exec

ECS Exec SHALL be disabled or tightly controlled for normal Production
workloads.

Where enabled, access SHALL be:

-   authorised;
-   audited;
-   temporary;
-   limited to operational need.

It SHALL not replace proper diagnostics or deployment processes.

------------------------------------------------------------------------

## 28. Security Logging

Security-relevant events SHALL be captured independently of ordinary
application debug logs.

Sources include:

-   CloudTrail;
-   IAM;
-   KMS;
-   Secrets Manager;
-   WAF;
-   GuardDuty;
-   Security Hub CSPM;
-   AWS Config;
-   application IAM;
-   gateway/security events.

------------------------------------------------------------------------

## 29. CloudTrail

Production AWS accounts SHALL maintain CloudTrail suitable for audit and
investigation.

The baseline SHOULD include:

-   multi-Region management-event coverage;
-   read/write management events;
-   protected S3 destination;
-   encryption;
-   log-file validation;
-   CloudWatch integration where required for detection;
-   controlled retention.

CloudTrail SHALL be enabled in every governed AWS account.

------------------------------------------------------------------------

## 30. CloudTrail Data Events

High-value data events SHOULD be enabled selectively where risk
justifies their cost and volume.

Candidates MAY include:

-   sensitive S3 object operations;
-   selected serverless/data-plane resources introduced later.

Data-event coverage SHALL be risk-based rather than blindly universal.

------------------------------------------------------------------------

## 31. Audit Log Protection

Audit logs SHALL be protected from alteration/deletion by normal
workload identities.

Controls SHOULD include:

-   dedicated log bucket/account as architecture matures;
-   encryption;
-   restricted deletion;
-   versioning/immutability where justified;
-   retention policy.

A compromised application role SHALL not be able to erase its
infrastructure audit trail.

------------------------------------------------------------------------

## 32. Centralized Security Account

As the AWS Organization matures, Baobab SHOULD establish a dedicated
Security/Log Archive account.

Conceptually:

``` text
Development ─┐
Staging ─────┼──► Security / Log Archive
Production ──┘
```

This account SHOULD centralize security findings and protected audit
evidence where practical.

------------------------------------------------------------------------

## 33. AWS Config

AWS Config SHOULD record relevant Production resource configurations.

It SHALL support:

-   configuration history;
-   drift/security evaluation;
-   Security Hub CSPM controls;
-   audit evidence.

Resource recording SHALL cover resources required by enabled controls.

------------------------------------------------------------------------

## 34. Security Hub CSPM

AWS Security Hub CSPM SHOULD be the initial AWS-native
aggregation/control-evaluation layer.

It SHOULD:

-   aggregate findings;
-   evaluate enabled standards/controls;
-   integrate GuardDuty and other supported services;
-   centralize security posture visibility.

Controls SHALL be deliberately selected and governed.

------------------------------------------------------------------------

## 35. Security Standards

Security Hub standards MAY include applicable AWS
foundational/CIS-aligned controls.

Enabling a standard SHALL not automatically mean Baobab is legally
"compliant" with every framework referenced by that standard.

Framework mappings are evidence aids, not legal certification.

------------------------------------------------------------------------

## 36. Control Exceptions

Security control exceptions SHALL be:

-   documented;
-   risk-assessed;
-   owned;
-   time-bounded where possible;
-   periodically reviewed.

A disabled noisy control without documented rationale is not acceptable
governance.

------------------------------------------------------------------------

## 37. GuardDuty

Amazon GuardDuty SHOULD be enabled for Production and, as the AWS
Organization matures, centrally governed across accounts/Regions where
supported.

Relevant protection capabilities SHOULD be evaluated for resources
actually used, including:

-   RDS;
-   S3;
-   ECS runtime;
-   other supported workload classes.

Cost and regional availability SHALL be verified before enablement.

------------------------------------------------------------------------

## 38. Security Findings

Findings SHALL have a lifecycle:

``` text
Finding
  │
  ▼
Triage
  │
  ├── false positive / accepted exception
  ├── mitigate
  ├── remediate
  └── escalate incident
  │
  ▼
Evidence / Closure
```

Findings SHALL not accumulate indefinitely without ownership.

------------------------------------------------------------------------

## 39. Security Severity

Security severity SHALL consider:

-   vendor severity;
-   exploitability;
-   internet exposure;
-   privilege level;
-   data sensitivity;
-   tenant impact;
-   active exploitation;
-   compensating controls.

A lower-scored issue on a critical trust boundary may deserve higher
operational priority.

------------------------------------------------------------------------

## 40. Security Alerts

High-confidence critical security findings SHALL route to an explicit
response owner.

Examples include:

-   root account use;
-   suspicious credential activity;
-   unexpected public exposure;
-   KMS/secret policy changes;
-   security logging disabled;
-   GuardDuty high-severity findings;
-   anomalous privileged role assumption.

------------------------------------------------------------------------

## 41. Security Incident Response

Security incidents SHALL follow an explicit lifecycle:

``` text
Detect
  │
  ▼
Triage
  │
  ▼
Contain
  │
  ▼
Preserve Evidence
  │
  ▼
Eradicate / Remediate
  │
  ▼
Recover
  │
  ▼
Review
```

Containment SHALL prioritize preventing further harm over preserving
normal deployment convenience.

------------------------------------------------------------------------

## 42. Evidence Preservation

During a material incident, operators SHALL preserve relevant:

-   CloudTrail events;
-   security findings;
-   IAM activity;
-   deployment evidence;
-   application logs/traces;
-   network/gateway evidence;
-   snapshots where appropriate.

Evidence handling SHALL avoid unnecessarily copying Restricted data.

------------------------------------------------------------------------

## 43. Infrastructure Audit Trail

For material infrastructure changes, Baobab SHOULD reconstruct:

``` text
PR / Commit
    │
    ▼
GitHub Workflow
    │
    ▼
OIDC Role Session
    │
    ▼
CloudTrail Event
    │
    ▼
AWS Resource Change
```

This is the minimum desired change-audit chain.

------------------------------------------------------------------------

## 44. Application Security Audit

Infrastructure audit SHALL complement application-domain audit.

Examples:

-   IAM login/admin events;
-   Trade order/payment changes;
-   ERP accounting actions;
-   tenant provisioning changes.

CloudTrail SHALL not be treated as a substitute for domain audit logs.

------------------------------------------------------------------------

## 45. Control Plane Audit

`baobab-cp` SHALL maintain auditable records for security-sensitive
provisioning/resolution actions according to its accepted ADRs.

Infrastructure SHALL preserve evidence of the resulting cloud-side
changes without becoming a duplicate business audit database.

------------------------------------------------------------------------

## 46. APISIX Security Audit

Gateway security monitoring SHOULD capture appropriate metadata for:

-   authentication failures;
-   authorization/routing rejection;
-   rate-limit enforcement;
-   suspicious request patterns;
-   administrative changes.

Sensitive request content SHALL not be indiscriminately logged.

------------------------------------------------------------------------

## 47. Database Audit

Database audit requirements SHALL be risk-based.

Infrastructure SHOULD capture:

-   administrative access;
-   security-relevant configuration changes;
-   unusual authentication failures;
-   engine events.

Application business changes belong primarily to domain audit trails.

Full SQL logging SHALL not be enabled indiscriminately if it risks
secrets/personal data or excessive volume.

------------------------------------------------------------------------

## 48. Backup Security

Backup security SHALL follow ADR-Infra-0018.

Backups SHALL be:

-   encrypted;
-   access controlled;
-   protected from normal workload deletion;
-   retention governed;
-   restore tested.

Security incidents SHALL consider whether backup credentials/keys were
compromised.

------------------------------------------------------------------------

## 49. Security Recovery

Security recovery MAY require:

-   credential rotation;
-   key rotation;
-   role/policy correction;
-   image replacement;
-   infrastructure reconstruction;
-   data restore;
-   tenant/session revocation.

Recovery SHALL not restore a known-compromised configuration blindly.

------------------------------------------------------------------------

## 50. Compliance Scope

Baobab SHALL maintain an explicit compliance scope.

A law, standard or customer requirement SHALL be mapped to:

``` text
Requirement
    │
    ▼
Control
    │
    ▼
Implementation
    │
    ▼
Evidence
    │
    ▼
Owner
```

This prevents compliance from becoming a list of product names.

------------------------------------------------------------------------

## 51. POPIA

For South African operations, Baobab infrastructure SHALL support the
security and data-governance obligations applicable to personal
information under POPIA.

Infrastructure implications MAY include:

-   appropriate technical safeguards;
-   access control;
-   encryption;
-   auditability;
-   data minimization;
-   retention/deletion support;
-   incident evidence;
-   controlled cross-border processing.

Legal interpretation and formal compliance determinations remain the
responsibility of qualified legal/privacy governance, not this ADR.

------------------------------------------------------------------------

## 52. Cross-Border Data

A business market SHALL not automatically determine an AWS region.

Before moving personal or regulated data across jurisdictions, Baobab
SHALL identify:

-   data category;
-   responsible legal entity;
-   processing purpose;
-   destination;
-   legal/contractual transfer basis;
-   security safeguards;
-   retention;
-   subprocessor/provider implications.

Infrastructure SHALL implement the approved placement decision; it SHALL
not invent the legal basis.

------------------------------------------------------------------------

## 53. Data Residency

Data residency requirements SHALL flow through accepted
policy/IsolationProfile decisions.

``` text
Legal / Contractual Requirement
          │
          ▼
Approved Placement Policy
          │
          ▼
IsolationProfile / Region
          │
          ▼
Infrastructure
```

Tenant country alone SHALL not be used as the infrastructure rule.

------------------------------------------------------------------------

## 54. Privacy by Design

Infrastructure SHOULD support privacy principles through:

-   least access;
-   separation;
-   encryption;
-   minimization;
-   explicit retention;
-   deletion workflows;
-   audit;
-   secure backups.

Privacy SHALL not be postponed until after Production deployment.

------------------------------------------------------------------------

## 55. Data Subject Deletion and Backups

Deletion from live systems and expiration from backups are distinct.

Where applicable, retention/deletion procedures SHALL document:

-   when live data is deleted;
-   how backup retention affects residual copies;
-   when those copies expire;
-   restrictions on restoring deleted data.

Restoring an old backup SHALL not silently reintroduce data that should
remain deleted without reconciliation.

------------------------------------------------------------------------

## 56. Non-Production Data

Production personal/confidential data SHALL NOT be copied into
Development by default.

Where realistic data is required:

-   synthetic data is preferred;
-   sanitization/anonymization SHOULD be used;
-   approved access and purpose are required.

Staging access SHALL remain controlled.

------------------------------------------------------------------------

## 57. Compliance Evidence

Evidence SHOULD be generated automatically where practical.

Examples:

-   Terraform configuration;
-   CI results;
-   Security Hub findings;
-   AWS Config history;
-   CloudTrail;
-   backup/restore tests;
-   IAM policy tests;
-   vulnerability scans;
-   DR exercises.

Manual screenshots SHALL not be the primary long-term evidence mechanism
where machine-verifiable evidence exists.

------------------------------------------------------------------------

## 58. Evidence Retention

Security/compliance evidence SHALL have explicit retention based on:

-   legal need;
-   contractual requirement;
-   incident-investigation need;
-   audit cycle;
-   cost.

Audit retention SHALL not automatically equal application-log retention.

------------------------------------------------------------------------

## 59. Policy as Code

ADR-Infra-0020 remains authoritative.

Security invariants SHOULD be enforced through CI and/or AWS
configuration controls.

Examples:

``` text
DENY public RDS
DENY public Redis
DENY public RabbitMQ
DENY public APISIX Admin
DENY unencrypted Production storage
DENY wildcard Production workload secrets
DENY mutable Production image tag
REQUIRE mandatory tags
```

------------------------------------------------------------------------

## 60. Preventive vs Detective Controls

Baobab SHALL use both.

``` text
Preventive
  IAM / SG / policy-as-code / protected environments
             +
Detective
  CloudTrail / Config / GuardDuty / Security Hub / alerts
```

Detection is not a substitute for prevention, and prevention is not
proof that compromise is impossible.

------------------------------------------------------------------------

## 61. Security Baseline Drift

Security posture SHALL be continuously evaluated.

If a resource drifts from the accepted baseline:

1.  detect;
2.  assess;
3.  contain if necessary;
4.  reconcile through source-controlled change;
5.  preserve evidence.

Blind auto-remediation SHALL only be used for proven safe controls.

------------------------------------------------------------------------

## 62. Security Testing

Production readiness SHOULD include:

-   IAM expected-allow/expected-deny tests;
-   network reachability tests;
-   secret isolation tests;
-   TLS verification;
-   dependency/container scans;
-   IaC scans;
-   public-exposure checks;
-   tenant isolation tests;
-   backup access tests;
-   audit-event verification.

Penetration/security testing MAY be added according to risk and release
maturity.

------------------------------------------------------------------------

## 63. ZuriBeans Go-Live Security Gate

Before ZuriBeans Production go-live, verify at minimum:

-   no unintended public data services;
-   HTTPS/TLS enforced;
-   APISIX Admin private;
-   workload IAM least privilege;
-   ZuriBeans cannot access Thamani resources;
-   secrets are external and scoped;
-   RDS/backups/state encrypted;
-   Production artifacts are immutable/scanned;
-   CloudTrail enabled;
-   AWS Config/security posture evaluation operational;
-   GuardDuty/Security Hub posture configured as approved;
-   critical security findings routed;
-   audit/change evidence traceable;
-   backup/restore security verified;
-   incident-response ownership documented.

------------------------------------------------------------------------

## 64. Security Acceptance

A Production security exception SHALL be explicit.

The platform SHALL NOT silently go live with known critical findings
merely because functionality works.

Any accepted exception SHALL identify:

-   finding;
-   risk;
-   compensating control;
-   owner;
-   approval;
-   expiry/review date where applicable.

------------------------------------------------------------------------

## 65. Production Verification

Before declaring this ADR implemented, verify:

-   security ownership exists;
-   AWS accounts use appropriate identity controls;
-   root is protected/monitored;
-   workload roles are scoped;
-   public exposure matches architecture;
-   data services are private;
-   encryption is enabled;
-   secrets are not in source/artifacts/manifests;
-   tenant negative tests pass;
-   CloudTrail audit coverage exists;
-   audit log storage is protected;
-   AWS Config records required resources;
-   Security Hub CSPM is configured as approved;
-   GuardDuty is configured as approved;
-   security findings have owners;
-   CI includes security/policy checks;
-   vulnerability management exists;
-   backups and recovery assets are protected;
-   Production data is not casually copied to Development;
-   compliance requirements map to controls/evidence;
-   ZuriBeans security gate passes.

------------------------------------------------------------------------

## 66. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  VPC = trusted network   Rejected                Network location is not
                                                  identity

  Managed AWS service =   Rejected                Shared responsibility
  automatically secure                            

  One admin role for      Rejected                Excessive blast radius
  everything                                      

  Long-lived AWS keys     Rejected                Temporary identity
                                                  preferred

  Public data services    Rejected                Unnecessary exposure
  with passwords                                  

  Secrets in              Rejected                Credential leakage risk
  Git/images/manifests                            

  CloudTrail alone =      Rejected                Domain audit still
  complete audit                                  required

  Security Hub enabled =  Rejected                Compliance requires
  compliant                                       mapped
                                                  controls/evidence

  Enable every control    Rejected                Noise/cost/false
  blindly                                         assumptions

  Disable noisy controls  Rejected                Governance failure
  without record                                  

  Tenant hostname =       Rejected                Spoofable/incomplete
  authorization                                   

  Copy Production data to Rejected                Privacy/security risk
  Dev by default                                  

  Logging full sensitive  Rejected                Data exposure
  payloads                                        

  Manual screenshots as   Rejected                Weak/non-repeatable
  primary compliance                              
  evidence                                        

  Security exceptions     Rejected                Permanent hidden risk
  without owner/expiry                            

  Active security finding Rejected                Uncontrolled risk
  ignored for go-live                             
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 67. Consequences

### Positive

-   Security controls become layered and auditable.
-   AWS-native detection and configuration history improve visibility.
-   Tenant/legal-entity isolation receives explicit security
    verification.
-   Compliance is tied to evidence rather than product enablement.
-   Supply-chain and deployment security integrate with infrastructure
    governance.
-   POPIA/data-placement concerns are incorporated without making
    infrastructure invent legal conclusions.
-   ZuriBeans receives a concrete Production security gate.

### Costs

-   CloudTrail, Config, Security Hub CSPM, GuardDuty and log retention
    create cost.
-   Security findings require operational ownership.
-   Policy controls and exceptions require maintenance.
-   Cross-account centralization adds organizational complexity.
-   Vulnerability remediation may require frequent rebuilds.
-   Compliance evidence and privacy governance require ongoing work.

These costs are accepted.

------------------------------------------------------------------------

## 68. Decision Rules

> **Baobab SHALL implement defence in depth and secure-by-default
> infrastructure.**

> **Least privilege, default deny and strong workload identity SHALL be
> mandatory Production principles.**

> **Production data services and management endpoints SHALL remain
> private unless an accepted ADR explicitly requires otherwise.**

> **Sensitive data SHALL be encrypted in transit and at rest using
> approved controls.**

> **ZuriBeans, Thamani and future tenants/legal entities SHALL remain
> independently authorized even on shared infrastructure.**

> **Expected-deny security tests SHALL validate critical tenant, secret
> and infrastructure boundaries.**

> **Production AWS activity SHALL be auditable through CloudTrail and
> complementary service/domain audit trails.**

> **AWS Config, Security Hub CSPM and GuardDuty SHOULD provide the
> initial AWS-native posture/detection foundation, subject to regional
> capability and cost validation.**

> **Security findings SHALL have owners, lifecycle and evidence.**

> **Compliance SHALL map requirements to controls, implementation and
> evidence; enabling a security product SHALL NOT itself constitute
> compliance.**

> **Infrastructure SHALL support applicable POPIA/privacy safeguards
> while legal interpretation remains with qualified governance.**

> **Production personal/confidential data SHALL NOT be copied to
> Development by default.**

> **Security exceptions SHALL be explicit, risk-accepted, owned and
> reviewed.**

> **ZuriBeans SHALL pass the defined security gate before Production
> go-live.**

------------------------------------------------------------------------

## 69. Implementation Implications

Implementation SHALL progressively establish:

``` text
Security & Compliance
│
├── Identity
│   ├── federation
│   ├── OIDC
│   ├── workload roles
│   └── break-glass
│
├── Protection
│   ├── network controls
│   ├── encryption
│   ├── secrets
│   ├── WAF/gateway
│   └── artifact security
│
├── Detection
│   ├── CloudTrail
│   ├── AWS Config
│   ├── Security Hub CSPM
│   ├── GuardDuty
│   └── security alerts
│
├── Audit
│   ├── infrastructure changes
│   ├── IAM activity
│   ├── gateway events
│   ├── domain audit
│   └── evidence retention
│
├── Compliance
│   ├── requirement mapping
│   ├── control evidence
│   ├── exceptions
│   ├── privacy/POPIA
│   └── data placement
│
└── Response
    ├── triage
    ├── containment
    ├── evidence
    ├── remediation
    └── recovery
```

Implementation SHALL verify AWS service availability and exact control
coverage in `af-south-1` before enabling regional security services.

------------------------------------------------------------------------

## 70. Technical Validation

Current AWS documentation confirms that:

-   Security Hub CSPM can evaluate CloudTrail security controls and
    relies on AWS Config resource recording for many configuration-based
    controls;
-   AWS recommends multi-Region CloudTrail management-event coverage,
    protected log storage and encryption as part of its security-control
    baseline;
-   GuardDuty integrates with Security Hub CSPM and currently exposes
    protections including RDS, S3 and ECS Runtime Monitoring controls;
-   security services and controls can vary by AWS Region.

Therefore, implementation SHALL validate current `af-south-1`
availability, pricing and supported control coverage rather than
assuming every capability available elsewhere is available in Cape Town.

------------------------------------------------------------------------

## 71. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0024 --- Cost Governance, Tagging and Resource Lifecycle**

It shall define:

-   mandatory AWS tags;
-   environment/service/owner/cost attribution;
-   shared-resource cost allocation;
-   tenant tagging rules;
-   budgets and alerts;
-   cost anomaly detection;
-   resource sizing;
-   non-Production scheduling;
-   storage/log/backup lifecycle;
-   orphan-resource detection;
-   reserved/committed capacity decisions;
-   FinOps review;
-   and how cost optimization remains subordinate to security,
    reliability and tenant-isolation requirements.
