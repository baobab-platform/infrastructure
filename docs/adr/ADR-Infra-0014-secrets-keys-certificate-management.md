# ADR-Infra-0014 --- Secrets, Keys and Certificate Management

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0002 --- AWS Account, Environment and Region Strategy
    -   ADR-Infra-0004 --- Terraform State, Locking and Bootstrap
    -   ADR-Infra-0007 --- Container Registry and Immutable Artifact
        Strategy
    -   ADR-Infra-0008 --- DNS, TLS, Edge and API Gateway Architecture
    -   ADR-Infra-0009 --- APISIX and etcd Production Architecture
    -   ADR-Infra-0010 --- PostgreSQL Production Architecture
    -   ADR-Infra-0011 --- Redis Production Architecture
    -   ADR-Infra-0012 --- RabbitMQ Production Architecture
    -   ADR-Infra-0013 --- Infrastructure IAM and Workload Identity
-   **Follow-on:** ADR-Infra-0015 --- Tenant and Workload Infrastructure
    Isolation

------------------------------------------------------------------------

## 1. Context

Baobab requires controlled management of:

-   database credentials;
-   RabbitMQ credentials;
-   APISIX administrative credentials;
-   application client secrets;
-   external API credentials;
-   encryption keys;
-   signing keys;
-   TLS certificates;
-   internal trust material;
-   bootstrap credentials;
-   recovery secrets.

These assets span multiple repositories, workloads, environments and
legal-entity contexts.

Secrets SHALL not become configuration files copied between
repositories, GitHub Actions and runtime environments.

Encryption keys SHALL have explicit ownership and administration
boundaries.

Certificates SHALL have managed issuance, validation, renewal and
revocation processes.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL use AWS-native managed services as the default Production
secret, key and certificate control plane:

  -----------------------------------------------------------------------
  Requirement                         Default Service
  ----------------------------------- -----------------------------------
  Secrets                             AWS Secrets Manager

  Non-secret configuration parameters AWS Systems Manager Parameter Store

  Encryption keys                     AWS KMS

  Public TLS certificates             AWS Certificate Manager

  Internal/private PKI                AWS Private CA or explicitly
                                      approved alternative where
                                      justified

  Workload access                     AWS IAM roles / temporary
                                      credentials
  -----------------------------------------------------------------------

Secrets SHALL NOT be stored in Git, container images, plaintext
Terraform configuration, release manifests or application source code.

------------------------------------------------------------------------

## 3. High-Level Architecture

``` text
                         AWS IAM
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        Secrets Manager    KMS            ACM
              │             │             │
              ▼             ▼             ▼
         Workload       Encryption      TLS Edge
          Secret           Keys        Certificates
              │
              ▼
         ECS Task Role
```

Identity controls access. Secrets, keys and certificates remain separate
managed asset classes.

------------------------------------------------------------------------

## 4. Secrets Manager

AWS Secrets Manager SHALL be the default location for Production secrets
requiring controlled retrieval and lifecycle management.

Examples include:

-   database passwords where password authentication is required;
-   RabbitMQ users/passwords;
-   APISIX administrative credentials;
-   Keycloak/bootstrap secrets;
-   third-party API credentials;
-   OAuth/OIDC client secrets where applicable;
-   application signing secrets not better represented by KMS asymmetric
    keys.

------------------------------------------------------------------------

## 5. Parameter Store Boundary

AWS Systems Manager Parameter Store MAY hold non-secret operational
configuration.

Examples:

``` text
/service/endpoint
/feature/configuration
/runtime/region
/non-sensitive/resource-id
```

Secrets Manager SHALL be preferred for credentials and secret material.

Parameter Store SHALL NOT be used merely to avoid Secrets Manager
governance or cost.

SecureString MAY be used only where its lifecycle requirements fit the
accepted design.

------------------------------------------------------------------------

## 6. Configuration Is Not Secret

Baobab SHALL distinguish:

``` text
Configuration
     │
     ├── non-sensitive ──► environment/release config or Parameter Store
     │
     └── sensitive ──────► Secrets Manager / KMS-backed mechanism
```

Not every environment variable is a secret.

Not every secret should be converted into ordinary environment
configuration.

------------------------------------------------------------------------

## 7. Secret Ownership

Every secret SHALL have an identifiable owner.

Ownership SHALL identify:

-   workload/service;
-   environment;
-   purpose;
-   operational owner;
-   rotation expectation;
-   consumers.

A secret with no identifiable owner SHALL be considered unmanaged.

------------------------------------------------------------------------

## 8. Secret Naming

Secret names SHOULD follow a predictable hierarchy such as:

``` text
baobab/{environment}/{service}/{purpose}
```

Examples:

``` text
baobab/production/baobab-trade/database
baobab/production/baobab-iam/keycloak-admin
baobab/production/apisix/admin
```

Tenant/legal-entity identifiers SHALL appear only where the secret
genuinely belongs to dedicated tenant-specific infrastructure or
integration.

------------------------------------------------------------------------

## 9. Environment Isolation

Development, Staging and Production SHALL NOT share normal runtime
secrets.

``` text
Development Secret  ≠  Staging Secret  ≠  Production Secret
```

Production secrets SHALL not be copied into Development for convenience.

Where representative testing requires credentials, non-Production
credentials SHALL be separately issued.

------------------------------------------------------------------------

## 10. Workload Access

Secrets SHALL be retrieved using workload IAM identity.

``` text
ECS Task
   │
   ▼
Task Role
   │
   ▼
Secrets Manager
   │
   ▼
Authorised Secret
```

A task role SHALL retrieve only secrets required by that workload.

------------------------------------------------------------------------

## 11. No Universal Secret Reader

A universal Production application role with:

``` text
secretsmanager:GetSecretValue
Resource: *
```

is prohibited.

Administrative recovery identities MAY require broader access, but such
access SHALL be exceptional, audited and governed.

------------------------------------------------------------------------

## 12. Secret Injection

Secrets MAY be supplied to workloads through supported ECS secret
integration or retrieved programmatically at runtime.

The selected method SHALL consider:

-   rotation behaviour;
-   application reload capability;
-   exposure through process environment;
-   logging risk;
-   startup dependency;
-   failure semantics.

No injection mechanism makes a secret safe to log.

------------------------------------------------------------------------

## 13. Environment Variables

Secret values MAY appear in a process environment only where the runtime
integration requires it and the risk is accepted.

Applications SHALL NOT:

-   print full environments;
-   expose diagnostic endpoints containing environment variables;
-   include secrets in crash reports;
-   include secrets in health responses.

Where practical, direct runtime retrieval SHOULD be preferred for
secrets requiring dynamic rotation.

------------------------------------------------------------------------

## 14. Secret Rotation

Secrets SHOULD be rotatable without rebuilding application images.

``` text
Current Secret
      │
      ▼
Create/Rotate
      │
      ▼
Update Consumers
      │
      ▼
Verify
      │
      ▼
Retire Old Secret
```

Rotation frequency SHALL reflect:

-   credential type;
-   provider capabilities;
-   exposure risk;
-   operational impact;
-   regulatory requirements.

------------------------------------------------------------------------

## 15. Automatic Rotation

Secrets Manager automatic rotation SHOULD be used where the target
service and application lifecycle support it safely.

Automatic rotation SHALL not be enabled blindly.

Before enabling it, implementation SHALL verify:

-   both old/new credential transition behaviour;
-   connection pool behaviour;
-   application refresh/restart requirements;
-   rollback;
-   monitoring.

------------------------------------------------------------------------

## 16. Rotation Failure

A failed rotation SHALL not silently revoke all valid application
access.

Rotation workflows SHALL expose:

-   failure status;
-   current/previous version state;
-   consumer health;
-   rollback/recovery procedure.

Critical rotations SHALL be tested in Staging.

------------------------------------------------------------------------

## 17. Secret Versioning

Where supported, secret version stages SHALL be used deliberately.

Conceptually:

``` text
AWSCURRENT
AWSPENDING
AWSPREVIOUS
```

Applications SHOULD normally consume the current approved secret version
rather than hardcoding version identifiers unless a controlled
transition requires it.

------------------------------------------------------------------------

## 18. Terraform Boundary

Terraform SHALL provision:

-   secret containers;
-   KMS keys;
-   IAM policies;
-   rotation infrastructure;
-   metadata;
-   integrations.

Terraform SHOULD NOT contain plaintext Production secret values.

``` text
Terraform
   │
   ├── create secret container
   └── grant access

Secret Value
   │
   └── secure population/rotation path
```

------------------------------------------------------------------------

## 19. Terraform State Risk

A value marked `sensitive` in Terraform can still exist in Terraform
state.

Therefore:

> **Terraform `sensitive = true` SHALL NOT be treated as secret-state
> avoidance.**

Secret values SHOULD be generated/populated through mechanisms that
minimise persistent plaintext exposure in Terraform state.

Where unavoidable, the risk SHALL be explicitly documented and protected
by the Terraform-state controls in ADR-Infra-0004.

------------------------------------------------------------------------

## 20. Secret Generation

Machine credentials SHOULD use high-entropy generated values.

Human-memorable passwords SHALL not be used for service credentials
merely for convenience.

Generation SHALL use cryptographically secure mechanisms.

------------------------------------------------------------------------

## 21. GitHub Secrets Boundary

GitHub repository/environment secrets SHALL be minimised.

AWS OIDC SHALL replace stored AWS access keys.

GitHub secrets MAY still be used where a third-party integration cannot
use workload federation, but each such secret SHALL have:

-   owner;
-   scope;
-   rotation;
-   environment restriction;
-   documented necessity.

------------------------------------------------------------------------

## 22. Secret Scanning

Repositories SHALL use automated secret scanning where available.

CI SHOULD detect common credential patterns before merge.

If a Production secret is committed to Git, deleting the commit alone is
insufficient.

Required response:

``` text
Exposure
   │
   ▼
Revoke/Rotate Secret
   │
   ▼
Assess Access/Audit
   │
   ▼
Remove from Repository History as appropriate
   │
   ▼
Prevent Recurrence
```

------------------------------------------------------------------------

## 23. Logging and Telemetry

Secrets SHALL NOT be emitted into:

-   application logs;
-   APISIX logs;
-   CI logs;
-   Terraform plans/artifacts;
-   OpenTelemetry attributes;
-   exception traces;
-   audit comments.

Sensitive headers such as `Authorization` SHALL be redacted according to
logging policy.

------------------------------------------------------------------------

## 24. KMS

AWS KMS SHALL be the default key-management service for AWS-managed
encryption requirements.

KMS SHALL support encryption for resources such as:

-   Terraform state;
-   RDS;
-   ElastiCache where supported;
-   backups/snapshots;
-   S3;
-   Secrets Manager;
-   logs where required;
-   other approved AWS resources.

------------------------------------------------------------------------

## 25. Key Ownership

KMS keys SHALL have explicit ownership and purpose.

A single universal Baobab KMS key SHALL NOT encrypt every resource by
default.

Key separation SHOULD consider:

-   environment;
-   data classification;
-   service;
-   blast radius;
-   legal/regulatory requirements;
-   operational lifecycle.

------------------------------------------------------------------------

## 26. Key Administrators vs Key Users

Key administration and key usage SHALL be separated where practical.

``` text
Key Administrator
      │
      ├── policy/rotation/lifecycle
      │
      X
      └── not automatically application decrypt

Workload Key User
      │
      └── encrypt/decrypt required resource only
```

Key administrators SHALL not automatically become consumers of protected
application data.

------------------------------------------------------------------------

## 27. KMS Key Policies

KMS key policies SHALL explicitly define trusted principals.

Broad account-wide or wildcard decrypt access SHALL be avoided.

Policies SHALL preserve:

-   administrative recovery;
-   workload least privilege;
-   service integration;
-   auditability.

------------------------------------------------------------------------

## 28. Key Rotation

KMS key rotation SHALL follow AWS capabilities and accepted
cryptographic policy.

Automatic rotation SHOULD be enabled for eligible customer-managed
symmetric keys unless a documented reason prevents it.

Rotation SHALL not imply deletion of old key material required to
decrypt existing ciphertext.

------------------------------------------------------------------------

## 29. Key Deletion

KMS key deletion is destructive and SHALL require heightened approval.

``` text
Request Deletion
      │
      ▼
Dependency Review
      │
      ▼
Approval
      │
      ▼
Mandatory Waiting Period
      │
      ▼
Deletion
```

A key SHALL not be scheduled for deletion while required ciphertext,
snapshots or backups still depend on it.

------------------------------------------------------------------------

## 30. Encryption Context

Where KMS encryption context is used, it SHOULD strengthen contextual
authorization and auditability.

Encryption context SHALL not contain confidential plaintext because it
may appear in logs/audit records.

------------------------------------------------------------------------

## 31. Public TLS Certificates

AWS Certificate Manager SHALL be the default mechanism for public TLS
certificates used by AWS edge services.

``` text
Route 53
   │ DNS validation
   ▼
ACM Certificate
   │
   ▼
ALB / approved AWS edge
```

Production public certificates SHALL use automated renewal where
supported.

------------------------------------------------------------------------

## 32. Certificate Ownership

Every certificate SHALL have identifiable ownership:

-   domain/service;
-   environment;
-   issuer;
-   renewal mechanism;
-   deployment target;
-   expiry monitoring.

Unowned certificates are prohibited in Production.

------------------------------------------------------------------------

## 33. DNS Validation

ACM DNS validation SHOULD be preferred where Baobab controls DNS.

Validation records SHALL be managed declaratively where practical.

Removing certificate validation records without understanding renewal
impact is prohibited.

------------------------------------------------------------------------

## 34. Certificate Renewal

Certificate renewal SHALL be monitored.

Automatic renewal capability does not remove operational responsibility.

Alerts SHOULD provide sufficient time to remediate:

-   failed validation;
-   expired authorization;
-   broken DNS;
-   deployment mismatch.

Production SHALL not rely on discovering expiry from customer TLS
failures.

------------------------------------------------------------------------

## 35. Private/Internal Certificates

Internal mTLS requirements MAY use AWS Private CA or another explicitly
approved PKI mechanism.

Examples include:

-   etcd peer certificates;
-   etcd client authentication;
-   sensitive internal service mTLS;
-   infrastructure administrative endpoints.

The platform SHALL not create an unmanaged collection of self-signed
Production certificates across repositories.

------------------------------------------------------------------------

## 36. Private CA Decision

AWS Private CA SHALL be considered when Baobab requires managed internal
certificate issuance at sufficient scale or assurance to justify it.

For small, tightly scoped infrastructure use cases, an approved
alternative MAY be used if it provides:

-   secure CA-key custody;
-   controlled issuance;
-   rotation;
-   revocation;
-   audit;
-   automation.

The selected approach SHALL be documented before Production use.

------------------------------------------------------------------------

## 37. etcd Certificates

Production etcd SHALL use the certificate controls required by
ADR-Infra-0009.

At minimum, the architecture SHALL distinguish:

``` text
etcd peer identity
etcd client identity
APISIX client identity
administrative identity
```

Private keys SHALL not be committed to `nabhold/infrastructure`.

------------------------------------------------------------------------

## 38. APISIX Certificates and Credentials

Public TLS for the APISIX edge path SHALL follow ADR-Infra-0008.

APISIX administrative credentials SHALL reside in Secrets Manager.

Any APISIX internal TLS private key SHALL use the approved
certificate/key mechanism rather than repository storage.

------------------------------------------------------------------------

## 39. Database Certificates

RDS clients SHALL use the AWS-supported trust chain for TLS validation.

Applications SHALL maintain supported RDS CA bundles through controlled
runtime/image dependency management.

Database TLS verification SHALL not be disabled as a shortcut during
certificate transitions.

------------------------------------------------------------------------

## 40. Third-Party Credentials

Third-party API keys and client secrets SHALL be treated as Production
secrets.

They SHALL be scoped by:

-   provider account;
-   environment;
-   consuming service;
-   permitted operations where provider supports them.

Shared third-party credentials across unrelated services SHOULD be
avoided.

------------------------------------------------------------------------

## 41. Signing Keys

Where Baobab requires cryptographic signing, the private signing key
SHOULD remain in a managed cryptographic service where feasible.

Examples include:

-   KMS asymmetric keys;
-   approved managed HSM/key service;
-   workload-specific signing service.

Exportable private signing keys SHALL be avoided where a managed
non-exportable key can satisfy the requirement.

------------------------------------------------------------------------

## 42. Application JWT/OIDC Keys

Keycloak/application token-signing key lifecycle belongs primarily to
`baobab-iam`.

Infrastructure SHALL provide the secure persistence, encryption, backup
and access mechanisms required by the accepted IAM architecture.

Infrastructure SHALL not independently rotate application signing keys
without IAM lifecycle coordination.

------------------------------------------------------------------------

## 43. Tenant Secrets

Tenant-specific integration secrets MAY exist for external systems.

Example:

``` text
baobab/production/integrations/{tenant}/{provider}
```

Such secrets SHALL:

-   be accessible only to the owning integration workload;
-   preserve legal-entity isolation;
-   have explicit owner/rotation;
-   not imply dedicated AWS infrastructure.

Tenant SHALL NOT imply a KMS key or secret hierarchy beyond what
isolation requirements justify.

------------------------------------------------------------------------

## 44. ZuriBeans and Thamani

ZuriBeans and Thamani SHALL not share credentials merely because both
are Nabhold subsidiaries.

If each has a credential for the same external provider, they SHALL
normally receive separate secrets where the provider/business
relationship permits.

``` text
ZuriBeans Credential ≠ Thamani Credential
```

This preserves legal-entity and operational independence.

------------------------------------------------------------------------

## 45. Secret Access Audit

Secret access SHALL be auditable through AWS logging/audit mechanisms.

Security review SHOULD be able to determine:

-   which principal requested a secret;
-   when;
-   from which environment/account;
-   whether the access was expected.

Secret values themselves SHALL not appear in audit logs.

------------------------------------------------------------------------

## 46. Break-Glass Secret Access

Human secret retrieval SHALL not be normal operations.

Where emergency retrieval is required:

``` text
Incident
   │
   ▼
Break-Glass Authorization
   │
   ▼
Temporary Secret Access
   │
   ▼
Audited Retrieval
   │
   ▼
Rotate if Exposure Risk Exists
```

The incident record SHALL document why direct secret access was
required.

------------------------------------------------------------------------

## 47. Secret Recovery

Recovery procedures SHALL account for secrets required to restore:

-   databases;
-   RabbitMQ;
-   APISIX;
-   IAM;
-   backups;
-   encryption keys;
-   third-party integrations.

A backup that cannot be decrypted or reconnected because its required
key/secret is unavailable is not a viable recovery capability.

------------------------------------------------------------------------

## 48. Key Recovery Boundary

KMS architecture SHALL avoid creating unrecoverable dependency chains.

Critical backup data SHALL not depend on a key scheduled for deletion.

Cross-region recovery plans SHALL account for regional KMS/key
availability and replication strategy where required by ADR-Infra-0019.

------------------------------------------------------------------------

## 49. Secret Replication

Secrets SHALL NOT be replicated across regions or accounts by default.

Replication requires an explicit requirement such as:

-   accepted disaster recovery;
-   regional workload deployment;
-   regulatory placement.

Replicated secrets SHALL preserve least privilege and independent audit.

------------------------------------------------------------------------

## 50. Certificate Revocation

Compromised private certificates SHALL have a defined
revocation/replacement procedure.

Where the certificate system supports revocation lists or equivalent
mechanisms, operational processes SHALL use them appropriately.

Short certificate lifetimes MAY reduce exposure but do not eliminate
compromise response.

------------------------------------------------------------------------

## 51. Expiry Inventory

Infrastructure SHALL maintain or derive an inventory of expiring
certificates and credentials where expiry applies.

Monitoring SHALL prevent silent expiry of:

-   TLS certificates;
-   external API credentials;
-   client secrets;
-   private CA certificates;
-   other time-bound authentication material.

------------------------------------------------------------------------

## 52. No Secrets in Images

Container images SHALL contain no Production secret values.

``` text
Image
 ├── application code
 ├── runtime dependencies
 └── non-secret defaults

Runtime
 └── secret retrieval
```

A new image SHALL not be required solely because a password rotated.

------------------------------------------------------------------------

## 53. No Secrets in Release Manifests

Release manifests MAY identify secret references but SHALL NOT contain
secret values.

Allowed:

``` text
database_secret_ref: baobab/production/baobab-trade/database
```

Prohibited:

``` text
database_password: actual-password
```

------------------------------------------------------------------------

## 54. No Secrets in Canonical Contracts

`nabhold/shared` canonical contracts SHALL define secret references or
credential requirements where necessary, not actual secret values.

Cross-repository contracts SHALL never become secret distribution
mechanisms.

------------------------------------------------------------------------

## 55. Infrastructure as Code

Terraform SHALL manage secret/key/certificate infrastructure such as:

``` text
terraform/modules/
├── secrets/
│   ├── secret containers
│   ├── access policies
│   └── rotation integration
├── kms/
│   ├── keys
│   ├── aliases
│   └── key policies
└── certificates/
    ├── ACM certificates
    ├── validation records
    └── approved private-PKI integration
```

Sensitive values SHALL be kept out of Terraform configuration/state
wherever technically practical.

------------------------------------------------------------------------

## 56. Rotation Testing

Production readiness SHALL test rotation of representative critical
credentials.

At minimum, testing SHOULD cover:

-   one database credential where password authentication is used;
-   one RabbitMQ credential;
-   one application/third-party secret where applicable;
-   APISIX administrative credential;
-   certificate renewal/replacement path.

Rotation SHALL be considered incomplete until consuming services remain
healthy.

------------------------------------------------------------------------

## 57. Failure Scenarios

  -----------------------------------------------------------------------
  Failure                             Expected Response
  ----------------------------------- -----------------------------------
  Secret unavailable                  Workload fails/degrades safely;
                                      alerts

  Secret rotated                      Consumers refresh/restart through
                                      controlled path

  Secret leaked                       Revoke/rotate immediately; audit
                                      exposure

  KMS access denied                   Fail closed for protected
                                      operation; alert

  KMS key pending deletion            Dependency review and
                                      cancellation/recovery if still
                                      required

  Certificate near expiry             Alert before service impact

  Certificate renewal fails           Investigate validation/DNS and
                                      remediate

  Private key compromise              Revoke/replace and audit

  Terraform state contains unintended Treat as exposure; rotate and
  secret                              remediate state process
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 58. Production Verification

Before go-live, verification SHALL demonstrate:

-   no Production secrets are committed to repositories;
-   normal GitHub AWS authentication uses OIDC;
-   workload roles can read only their approved secrets;
-   unrelated workload secret access is denied;
-   secrets are absent from container images;
-   secrets are absent from release manifests;
-   sensitive Terraform-state exposure is reviewed;
-   KMS policies enforce intended users/admin separation;
-   RDS/backup/storage encryption uses approved keys;
-   public TLS certificates are valid and renewable;
-   private certificate paths are controlled;
-   secret rotation works for representative workloads;
-   secret and key access is auditable;
-   break-glass access is controlled;
-   ZuriBeans cannot retrieve Thamani-specific credentials.

------------------------------------------------------------------------

## 59. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Secrets committed to    Rejected                Persistent credential
  Git                                             exposure

  `.env` files as         Rejected                Weak lifecycle/audit
  Production secret store                         

  Secrets baked into      Rejected                Rotation/exposure risk
  images                                          

  Secret values in        Rejected                Artifact leakage
  release manifests                               

  Long-lived AWS keys in  Rejected                OIDC available
  GitHub                                          

  One shared Production   Rejected                Excessive lateral
  secret-reader role                              access

  One KMS key for         Rejected                Excessive blast radius
  everything by default                           

  Terraform `sensitive`   Rejected                Value may remain in
  as sufficient                                   state
  protection                                      

  Unmanaged self-signed   Rejected                Renewal/trust/audit
  certs across repos                              risk

  Manual public           Rejected                Avoidable expiry risk
  certificate renewal                             

  Production secrets      Rejected                Breaks environment
  shared across                                   isolation
  environments                                    

  ZuriBeans/Thamani       Rejected                Breaks legal-entity
  shared credentials by                           independence
  default                                         

  Direct human secret     Rejected                Weak operational
  retrieval as normal                             control
  operation                                       
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 60. Consequences

### Positive

-   Central managed secret lifecycle.
-   Strong workload-level access control.
-   Reduced credential exposure in repositories and CI.
-   Explicit KMS ownership and administration.
-   Managed public TLS renewal.
-   Clear private-PKI decision boundary.
-   Rotation without rebuilding images.
-   Preserves ZuriBeans/Thamani legal-entity separation.
-   Improves auditability and disaster-recovery readiness.

### Costs

-   More IAM/KMS policies must be managed.
-   Secrets Manager and Private CA may add cost.
-   Rotation requires application compatibility.
-   Private PKI introduces lifecycle complexity.
-   Terraform workflows must avoid convenient plaintext secret
    injection.
-   Recovery planning must include keys and credentials, not only data.

These costs are accepted.

------------------------------------------------------------------------

## 61. Decision Rules

> **AWS Secrets Manager SHALL be Baobab's default Production secret
> store.**

> **AWS Systems Manager Parameter Store SHALL primarily hold non-secret
> operational configuration; it SHALL NOT become an unmanaged substitute
> for Secrets Manager.**

> **AWS KMS SHALL be the default key-management service for AWS-managed
> Production encryption.**

> **AWS Certificate Manager SHALL be the default public TLS certificate
> mechanism for AWS edge services.**

> **Production secrets SHALL NOT be stored in Git, container images,
> plaintext Terraform configuration or release manifests.**

> **Terraform `sensitive` SHALL NOT be treated as sufficient protection
> against secret persistence in Terraform state.**

> **Workload IAM roles SHALL access only the secrets and keys required
> by that workload.**

> **Secrets SHOULD be rotatable independently of application image
> builds.**

> **Production public certificate renewal SHALL be automated where
> supported and monitored.**

> **Internal/private certificates SHALL use a controlled PKI mechanism
> rather than unmanaged repository-generated certificates.**

> **ZuriBeans and Thamani SHALL NOT share credentials merely because
> they share a parent company.**

> **Human secret access SHALL be exceptional and auditable.**

------------------------------------------------------------------------

## 62. Implementation Implications

Implementation SHALL progressively establish:

``` text
Secrets & Cryptography
│
├── Secrets Manager
│   ├── workload secrets
│   ├── integration secrets
│   ├── access policies
│   └── rotation
│
├── KMS
│   ├── environment keys
│   ├── workload/data-class keys where justified
│   ├── key policies
│   └── rotation/lifecycle
│
├── ACM
│   ├── public certificates
│   ├── DNS validation
│   └── renewal monitoring
│
├── Private PKI
│   ├── etcd peer/client certificates
│   └── other approved mTLS
│
└── Governance
    ├── secret scanning
    ├── access audit
    ├── expiry monitoring
    ├── rotation tests
    └── break-glass procedures
```

Implementation SHALL inspect each consuming repository's accepted ADRs
before assigning secrets, keys or certificate responsibilities.

------------------------------------------------------------------------

## 63. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0015 --- Tenant and Workload Infrastructure Isolation**

It shall define:

-   logical versus physical tenant isolation;
-   IsolationProfiles;
-   shared versus dedicated infrastructure;
-   legal-entity boundaries;
-   database/schema/instance isolation;
-   cache and broker isolation;
-   compute isolation;
-   network isolation;
-   secrets and IAM isolation;
-   tenant onboarding implications;
-   regulatory escalation;
-   noisy-neighbour controls;
-   dedicated-environment criteria;
-   and how ZuriBeans, Thamani, Nabhold and future Baobab customers map
    onto infrastructure without equating tenant with AWS deployment.
