# ADR-Infra-0022 --- Deployment Rollback and Database Change Safety

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0006 --- Production Compute Platform
    -   ADR-Infra-0007 --- Container Registry and Immutable Artifact
        Strategy
    -   ADR-Infra-0010 --- PostgreSQL Production Architecture
    -   ADR-Infra-0012 --- RabbitMQ Production Architecture
    -   ADR-Infra-0017 --- SLOs, Health, Capacity and Operational
        Monitoring
    -   ADR-Infra-0018 --- Backup, Restore and Data Retention
    -   ADR-Infra-0019 --- Availability, Disaster Recovery and Business
        Continuity
    -   ADR-Infra-0020 --- CI/CD and Infrastructure Change Governance
    -   ADR-Infra-0021 --- Application Deployment, Promotion and Release
        Manifests
-   **Platform Dependencies:** accepted application/engine ADRs and
    canonical contracts in `nabhold/shared`
-   **Follow-on:** ADR-Infra-0023 --- Infrastructure Security,
    Compliance and Audit

------------------------------------------------------------------------

## 1. Context

A Production deployment can fail after infrastructure and application
changes have already taken effect.

Failure modes include:

-   defective application code;
-   incompatible API/event changes;
-   unhealthy ECS tasks;
-   configuration errors;
-   database schema incompatibility;
-   incomplete migrations;
-   failed data backfills;
-   external side effects;
-   duplicate event publication;
-   gateway-routing errors;
-   IAM incompatibility;
-   irreversible data transformation.

"Rollback" is therefore not one operation.

Reverting Git or selecting an older image may be safe for a stateless
code-only change, but dangerous after a database schema or data
transformation has moved forward.

Baobab requires explicit rollback classes and database-change rules so
that recovery actions do not amplify an incident.

------------------------------------------------------------------------

## 2. Decision

Baobab SHALL distinguish:

1.  **Application rollback**
2.  **Configuration rollback**
3.  **Infrastructure rollback**
4.  **Database/schema recovery**
5.  **Data recovery**
6.  **External-effect reconciliation**

The default database evolution strategy SHALL be **expand → migrate →
contract** where technically applicable.

Production releases SHALL be designed so that the previous application
version remains compatible during the rollback window whenever
practical.

A rollback SHALL NOT be executed blindly merely because a deployment
failed.

------------------------------------------------------------------------

## 3. Rollback Is a Decision

``` text
Deployment Failure
       │
       ▼
Assess Change Class
       │
       ├── code/config only ──► rollback may be safe
       │
       ├── compatible DB expansion ──► rollback usually possible
       │
       ├── data transformation ──► analyse
       │
       ├── destructive schema ──► rollback may be unsafe
       │
       └── external side effect ──► reconcile
       ▼
Choose
Rollback / Forward Fix / Restore / Reconcile
```

------------------------------------------------------------------------

## 4. Rollback Classes

  -------------------------------------------------------------------------
  Class                   Typical Example           Default Response
  ----------------------- ------------------------- -----------------------
  **R0 --- Stateless**    application image defect  redeploy previous
                                                    digest

  **R1 ---                bad non-secret config     restore prior
  Configuration**                                   configuration

  **R2 --- Compatible     additive nullable column  app rollback generally
  Schema**                                          possible

  **R3 --- Data           backfill/transformation   evaluate data
  Migration**                                       compatibility

  **R4 --- Destructive    dropped/rewritten data    restore/forward-fix may
  Schema**                                          be required

  **R5 --- External       payment/message/partner   reconcile; code
  Effect**                action                    rollback insufficient
  -------------------------------------------------------------------------

Exact classification MAY be refined, but the distinction SHALL remain.

------------------------------------------------------------------------

## 5. Previous Known-Good Release

Every Production deployment SHALL retain identification of the previous
approved release:

-   image digest;
-   release manifest;
-   infrastructure revision;
-   configuration version/reference;
-   migration state.

Rollback SHALL use the prior immutable artifact rather than rebuild
historical source.

------------------------------------------------------------------------

## 6. Application Rollback

For stateless application failures:

``` text
New Digest
   │
   X unhealthy
   │
   ▼
Previous Approved Digest
   │
   ▼
ECS Deployment
   │
   ▼
Verification
```

Rollback SHALL still pass readiness and post-deployment verification.

------------------------------------------------------------------------

## 7. ECS Deployment Failure

ECS deployment circuit-breaker/rollback capabilities SHOULD be used
where appropriate.

However, ECS can only reason about runtime deployment health.

It cannot determine whether:

-   business data was transformed;
-   an external payment occurred;
-   a schema became incompatible;
-   an event caused an irreversible downstream action.

Application-level rollback governance remains required.

------------------------------------------------------------------------

## 8. Rolling Deployment Compatibility

During rolling deployment, old and new versions may run concurrently.

Therefore:

``` text
Old Version ─┐
             ├── Same DB / APIs / Events
New Version ─┘
```

Database, API and event changes SHALL tolerate this coexistence for the
deployment window unless a deliberately different deployment strategy is
approved.

------------------------------------------------------------------------

## 9. Expand--Migrate--Contract

The preferred schema evolution pattern is:

``` text
EXPAND
  Add backward-compatible structures
          │
          ▼
DEPLOY
  Old + new code remain compatible
          │
          ▼
MIGRATE
  Backfill/transform data safely
          │
          ▼
VERIFY
  New path proven
          │
          ▼
CONTRACT
  Remove obsolete structures later
```

Expansion and contraction SHOULD normally occur in different releases.

------------------------------------------------------------------------

## 10. Expand Phase

Safe expansion MAY include:

-   new nullable columns;
-   new tables;
-   new indexes using safe creation methods;
-   additive constraints introduced carefully;
-   new event/API fields that older consumers ignore.

Expansion SHALL avoid making the currently running application invalid.

------------------------------------------------------------------------

## 11. Migration Phase

Migration/backfill SHALL:

-   be idempotent or restartable where practical;
-   use bounded batches for large datasets;
-   expose progress;
-   log failures;
-   avoid uncontrolled long locks;
-   define retry/resume semantics;
-   be observable.

Large backfills SHALL NOT be hidden inside ordinary application startup.

------------------------------------------------------------------------

## 12. Contract Phase

Contract removes obsolete compatibility structures.

Examples:

-   dropping old columns;
-   removing old tables;
-   enforcing stricter constraints;
-   deleting compatibility code.

Contract SHALL occur only after:

-   all dependent versions have migrated;
-   rollback window has closed;
-   data verification passes;
-   old consumers are no longer active.

------------------------------------------------------------------------

## 13. Destructive Migration Rule

A destructive schema change SHALL be considered a separate high-risk
change.

It SHALL require:

-   explicit review;
-   dependency inventory;
-   confirmed backup/recovery point;
-   compatibility verification;
-   rollback/restore plan;
-   operational owner.

Destructive migration SHALL not be smuggled into an unrelated feature
release.

------------------------------------------------------------------------

## 14. Database Rollback Is Not `down`

A migration framework's `down` operation SHALL NOT automatically be
assumed safe in Production.

A reverse migration may:

-   discard new data;
-   be untested;
-   recreate structures without restoring values;
-   conflict with external effects.

Reverse migrations SHALL be used only when explicitly designed and
verified.

------------------------------------------------------------------------

## 15. Forward Fix

Forward-fix SHOULD be preferred when rollback would create greater risk.

Examples:

-   database schema already safely advanced;
-   old code cannot read newly written data;
-   external side effects already occurred;
-   migration is irreversible but repair is bounded.

Forward-fix SHALL remain controlled, tested and auditable.

------------------------------------------------------------------------

## 16. Restore vs Rollback

``` text
Rollback
  = return software/configuration to earlier known state

Restore
  = recover persisted data from backup/PITR

Reconcile
  = align divergent internal/external truth
```

These operations SHALL not be conflated.

ADR-Infra-0018 governs restore mechanisms.

------------------------------------------------------------------------

## 17. Point-in-Time Recovery

PITR MAY be required after destructive data corruption.

Before PITR, operators SHALL consider:

-   transactions written after the recovery point;
-   tenant impact;
-   external-system divergence;
-   event publication;
-   payments;
-   ERP/accounting state.

PITR is not a casual "undo" button.

------------------------------------------------------------------------

## 18. Shared Database Safety

Where multiple tenants share physical PostgreSQL infrastructure,
whole-database rollback may affect unaffected tenants.

For a tenant-specific incident, preferred recovery MAY be:

``` text
PITR to Temporary DB
        │
        ▼
Extract Affected Data
        │
        ▼
Validate
        │
        ▼
Controlled Repair
```

ZuriBeans recovery SHALL NOT casually roll back Thamani data.

------------------------------------------------------------------------

## 19. Legal-Entity Isolation

Rollback and recovery SHALL preserve legal-entity boundaries.

Common Nabhold ownership SHALL NOT justify:

-   cross-entity data overwrite;
-   shared recovery credentials;
-   copying Thamani data into ZuriBeans;
-   restoring one tenant by destroying another's valid transactions.

------------------------------------------------------------------------

## 20. Database Backup Gate

Before a high-risk Production migration, the deployment process SHOULD
verify that an acceptable recovery point exists.

For critical destructive changes, this SHALL be mandatory.

The recovery point SHALL remain decryptable and accessible under
ADR-Infra-0018.

------------------------------------------------------------------------

## 21. Migration Execution Identity

Migration tasks SHALL use a dedicated scoped identity.

The normal application runtime role SHOULD NOT automatically possess
unrestricted schema-administration privileges.

Migration credentials SHALL be available only to the controlled
migration path.

------------------------------------------------------------------------

## 22. Migration Execution Model

Where feasible, migrations SHOULD run as a controlled one-off task/job:

``` text
Release Approved
      │
      ▼
Migration Task
      │
      ▼
Migration Verification
      │
      ▼
Application Deployment
```

or, for compatible expansion:

``` text
Expand
  │
Deploy
  │
Backfill
  │
Verify
  │
Contract Later
```

The exact sequence is service-specific.

------------------------------------------------------------------------

## 23. Migration Concurrency

Only one incompatible migration sequence SHALL operate on the same
schema at a time.

Migration locking or equivalent coordination SHALL prevent concurrent
schema mutation.

Multiple ECS replicas SHALL not independently race to upgrade the same
Production schema.

------------------------------------------------------------------------

## 24. Long-Running Migrations

Large schema/data operations SHALL be designed to minimize:

-   table locks;
-   transaction duration;
-   WAL growth;
-   connection starvation;
-   replication/failover pressure;
-   application latency impact.

Staging/load testing SHALL estimate operational impact before
Production.

------------------------------------------------------------------------

## 25. Index Changes

Large index creation/rebuild operations SHALL use database-supported
low-impact methods where appropriate.

The migration SHALL account for:

-   duration;
-   locks;
-   disk/storage growth;
-   failure cleanup.

Index creation SHALL not be treated as operationally free.

------------------------------------------------------------------------

## 26. Constraint Changes

New strict constraints SHOULD be introduced in stages where necessary:

``` text
Add compatible structure
      │
      ▼
Clean/backfill data
      │
      ▼
Validate
      │
      ▼
Enforce constraint
```

Immediate enforcement SHALL only occur when existing data is known
compatible and operational impact is acceptable.

------------------------------------------------------------------------

## 27. Data Backfills

Backfills SHALL have:

-   stable selection criteria;
-   checkpoint/progress tracking where needed;
-   idempotency/restart safety;
-   bounded batches;
-   rate controls;
-   verification.

A failed backfill SHALL be resumable or have a documented recovery
procedure.

------------------------------------------------------------------------

## 28. Dual Read/Write

Temporary dual-read/dual-write patterns MAY be used during migration
where justified.

They SHALL have:

-   defined source of truth;
-   consistency checks;
-   cutover criteria;
-   rollback semantics;
-   removal plan.

Permanent accidental dual-write architecture is prohibited.

------------------------------------------------------------------------

## 29. Data Verification

Migration completion SHALL include validation beyond "command exited 0."

Verification MAY include:

-   row counts;
-   checksums;
-   null/error rates;
-   domain invariants;
-   tenant isolation;
-   application reads/writes;
-   reconciliation queries.

------------------------------------------------------------------------

## 30. API Change Safety

API changes SHALL be backward compatible during the supported
deployment/rollback window where practical.

Breaking changes require:

-   explicit versioning;
-   consumer migration;
-   compatibility testing;
-   coordinated release.

Rollback SHALL not strand clients on an incompatible API.

------------------------------------------------------------------------

## 31. Event Change Safety

Canonical event evolution SHALL tolerate producer/consumer version skew.

During rollback:

``` text
New Producer Event
        │
        ▼
Old Consumer?
```

If the old consumer cannot process events emitted by the new release,
application rollback is unsafe without an event compatibility plan.

------------------------------------------------------------------------

## 32. Event Redelivery

Rollback SHALL assume at-least-once event delivery.

Consumers SHALL remain idempotent.

Reverting application code SHALL not reset event identity or cause
already completed business actions to be repeated.

------------------------------------------------------------------------

## 33. Outbox Safety

Transactional outbox state SHALL remain aligned with authoritative
database state.

Rollback SHALL NOT delete outbox records merely to stop
duplicate-looking events.

Operators SHALL distinguish:

-   unpublished;
-   published;
-   retried;
-   processed;
-   reconciled events.

------------------------------------------------------------------------

## 34. RabbitMQ Rollback Boundary

RabbitMQ topology changes SHALL be backward compatible where old/new
consumers coexist.

Deleting queues/exchanges during the first release of a new topology is
discouraged.

Topology contraction SHOULD follow the same delayed-removal principle as
schema contraction.

------------------------------------------------------------------------

## 35. Configuration Rollback

Configuration changes SHALL be version-identifiable.

Rollback SHALL restore the previous approved configuration reference,
not manually reconstruct values from memory.

Secret values remain governed separately and SHALL not be copied into
rollback manifests.

------------------------------------------------------------------------

## 36. Secret Rotation

Rolling application code back SHALL NOT automatically roll secrets back.

If a release coincided with credential rotation, recovery SHALL
determine whether:

-   old credential remains valid;
-   new credential is required;
-   both are temporarily accepted;
-   rotation must be completed rather than reversed.

Security SHALL not be weakened merely to simplify rollback.

------------------------------------------------------------------------

## 37. IAM Rollback

IAM changes are high risk.

Rollback SHALL account for:

-   active sessions;
-   tokens already issued;
-   Keycloak client configuration;
-   roles/scopes;
-   signing keys;
-   downstream token expectations.

Deleting new IAM structures immediately after deployment failure may
break already issued identities.

------------------------------------------------------------------------

## 38. Gateway Rollback

APISIX route/policy changes SHOULD retain prior configuration
identity/history where practical.

Gateway rollback SHALL verify:

-   route ownership;
-   authentication;
-   authorization;
-   upstream health;
-   tenant context.

Restoring a route that bypasses newer security policy is prohibited.

------------------------------------------------------------------------

## 39. Infrastructure Rollback

Terraform source reversion MAY be used for reversible infrastructure
changes.

Before apply, operators SHALL inspect the resulting plan.

A Git revert SHALL NOT automatically be applied when it would destroy or
replace stateful resources.

------------------------------------------------------------------------

## 40. Terraform State Safety

Terraform state SHALL not be manually edited as the first rollback
technique.

If state repair is required:

-   stop concurrent applies;
-   preserve state versions;
-   document intended correction;
-   verify with plan;
-   use controlled Terraform state commands/procedures.

------------------------------------------------------------------------

## 41. External Side Effects

Some actions cannot be undone by code rollback.

Examples:

-   payment captured;
-   refund issued;
-   customer notification sent;
-   customs submission;
-   shipment booked;
-   ERP posting;
-   third-party API mutation.

Such effects require reconciliation or compensating business action.

------------------------------------------------------------------------

## 42. Compensation

Where a domain supports compensating transactions, they SHALL be
explicit domain operations.

Example:

``` text
Payment Captured
      │
      X cannot "uncapture" via code rollback
      │
      ▼
Approved Refund / Reversal Process
```

Infrastructure SHALL not invent financial/business compensation
semantics.

------------------------------------------------------------------------

## 43. ERP and Accounting Effects

Posted ERP/accounting transactions SHALL follow accepted
iDempiere/accounting reversal procedures.

Database rollback SHALL not be used casually to erase legally or
operationally significant accounting events.

------------------------------------------------------------------------

## 44. Payment Effects

Trade/payment integrations SHALL reconcile local state with
payment-provider truth after rollback or restore.

A local database state saying "not paid" SHALL not override an
externally captured payment without reconciliation.

------------------------------------------------------------------------

## 45. Cross-Border Effects

Customs, logistics, tax or cross-border partner actions may survive
application rollback.

Recovery SHALL explicitly reconcile such actions.

This is particularly relevant to ZuriBeans B2B cross-border workflows.

------------------------------------------------------------------------

## 46. Rollback Decision Gate

A material failed Production release SHOULD use:

  -----------------------------------------------------------------------
  Question                            If Yes
  ----------------------------------- -----------------------------------
  Is previous code DB-compatible?     rollback may proceed

  Did destructive migration occur?    analyse restore/forward-fix

  Was business data transformed?      validate compatibility

  Were external side effects emitted? reconcile

  Did new event/API shape escape?     check consumers

  Can rollback meet SLO faster than   favour rollback if safe
  forward-fix?                        

  Is security compromised?            prioritize containment over
                                      convenience
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 47. Rollback Authority

Production rollback SHALL be executable by authorised operational roles.

For a clearly unhealthy stateless release, automation MAY initiate
rollback according to pre-approved health criteria.

For data-destructive or externally consequential incidents, explicit
human authorization SHOULD be required.

------------------------------------------------------------------------

## 48. Automated Rollback

Automated rollback is appropriate when:

-   change is stateless/reversible;
-   previous artifact is compatible;
-   no irreversible migration occurred;
-   health criteria are reliable.

Automation SHALL stop and escalate when safety cannot be established.

------------------------------------------------------------------------

## 49. Rollback Window

A release SHOULD define a practical rollback window during which the
previous application remains compatible.

Contract/destructive cleanup SHALL occur only after that window closes
and verification is complete.

The window MAY vary by service.

------------------------------------------------------------------------

## 50. Feature Flags

Feature flags MAY reduce rollback risk by separating deployment from
activation.

A problematic feature MAY be disabled without replacing the image if:

-   flag behaviour is safe;
-   old/new data remains compatible;
-   disabling does not hide corrupted state.

Flags do not replace database safety.

------------------------------------------------------------------------

## 51. Release Markers

Rollback SHALL create its own deployment/release marker.

Telemetry SHALL make it possible to distinguish:

``` text
Deploy New
   │
Incident
   │
Rollback
   │
Recovery
```

Operators SHALL not infer rollback timing from logs manually.

------------------------------------------------------------------------

## 52. Post-Rollback Verification

Rollback success SHALL verify:

-   ECS/task health;
-   correct digest;
-   readiness;
-   critical synthetic journeys;
-   error/latency recovery;
-   DB compatibility;
-   queue behaviour;
-   external reconciliation status.

"Old tasks are running" is insufficient.

------------------------------------------------------------------------

## 53. Incident Evidence

Material rollback SHALL preserve:

-   failed release manifest;
-   prior release manifest;
-   Terraform plan/apply evidence;
-   migration logs;
-   telemetry;
-   rollback decision;
-   reconciliation actions.

Evidence supports post-incident analysis.

------------------------------------------------------------------------

## 54. ZuriBeans Go-Live Safety

Before ZuriBeans Production go-live, the platform SHALL demonstrate at
least one controlled rollback exercise covering:

``` text
ZuriBeans Release
      │
      ▼
Injected/Simulated Failure
      │
      ▼
Rollback Decision
      │
      ▼
Previous Digest Restored
      │
      ▼
B2B Critical Path Verified
```

Where Trade/ERP database changes are involved, the exercise SHALL also
validate migration compatibility/recovery.

------------------------------------------------------------------------

## 55. Engine-Specific Rules

This ADR establishes platform safety principles but SHALL NOT override
engine-specific supported procedures.

Implementation SHALL inspect accepted ADRs and vendor-supported
lifecycle rules for:

-   MedusaJS;
-   Keycloak;
-   iDempiere;
-   Payload CMS;
-   Haystack/Qdrant;
-   PostgreSQL;
-   other engines.

If an engine cannot safely support generic rollback, its supported
forward/recovery procedure takes precedence and SHALL be documented.

------------------------------------------------------------------------

## 56. Production Verification

Before declaring rollback architecture Production-ready, verify:

-   previous immutable release is identifiable;
-   stateless rollback is automated or documented;
-   ECS rollback health criteria exist;
-   migration ownership is explicit;
-   expand--migrate--contract is used where applicable;
-   old/new versions can coexist during rolling deployment;
-   destructive migrations are gated;
-   critical migration recovery point exists;
-   backfills are resumable/observable;
-   migration verification exists;
-   API/event compatibility is tested;
-   RabbitMQ topology contraction is delayed safely;
-   secret/IAM rollback semantics are documented;
-   external side effects have reconciliation procedures;
-   shared-database recovery does not blindly roll back unrelated
    tenants;
-   post-rollback verification exists;
-   ZuriBeans rollback has been exercised.

------------------------------------------------------------------------

## 57. Rejected Alternatives

  -----------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -----------------------
  Git revert = safe       Rejected                Runtime/data effects
  rollback                                        may differ

  Old image always safe   Rejected                DB/events may be
                                                  incompatible

  Migration `down` always Rejected                May lose data
  safe                                            

  Destructive schema +    Rejected                Removes rollback window
  code in one step                                

  Migration in every      Rejected                Concurrency/race risk
  replica startup                                 

  Large unbounded         Rejected                Operational risk
  backfill                                        

  Whole shared DB PITR    Rejected                Harms unaffected
  for one tenant by                               tenants
  default                                         

  Roll back secrets       Rejected                Security/rotation risk
  automatically                                   

  Delete new              Rejected                Breaks delivery
  events/outbox to undo                           integrity
  release                                         

  DB rollback to undo     Rejected                External truth persists
  payment                                         

  Terraform Git revert    Rejected                May destroy state
  applied blindly                                 

  Automatic rollback      Rejected                Can amplify incident
  after irreversible                              
  change                                          

  No post-rollback        Rejected                Recovery unproven
  verification                                    

  Generic rollback        Rejected                Unsupported/unsafe
  overrides engine                                
  lifecycle                                       
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 58. Consequences

### Positive

-   Rollback becomes a controlled recovery mechanism rather than reflex.
-   Database evolution preserves compatibility windows.
-   Shared-tenant data receives stronger protection.
-   Immutable artifacts make application rollback deterministic.
-   External effects are reconciled instead of incorrectly "undone."
-   Event and API compatibility become part of deployment safety.
-   ZuriBeans go-live gains a tested rollback requirement.

### Costs

-   Expand--migrate--contract can require multiple releases.
-   Backfills require tooling and observability.
-   Compatibility code may temporarily remain in the codebase.
-   High-risk migrations require stronger operational coordination.
-   Some incidents require forward-fix rather than simple rollback.
-   Domain teams must define compensation/reconciliation procedures.

These costs are accepted.

------------------------------------------------------------------------

## 59. Decision Rules

> **Rollback SHALL be classified before execution; not every failed
> deployment is safely reversible.**

> **The previous approved immutable artifact and release manifest SHALL
> remain identifiable.**

> **Database evolution SHOULD use expand → migrate → contract where
> technically applicable.**

> **Destructive contraction SHOULD occur only after the rollback
> compatibility window has closed.**

> **Application schema migrations SHALL be service-owned and executed
> through controlled migration paths.**

> **Migration framework reverse operations SHALL NOT automatically be
> considered safe Production rollback.**

> **Large backfills SHALL be bounded, observable and restartable where
> practical.**

> **Shared-database recovery SHALL NOT blindly roll back unaffected
> tenants/legal entities.**

> **API and event evolution SHALL account for old/new version
> coexistence and rollback.**

> **External business effects SHALL be reconciled or compensated by the
> owning domain; code/database rollback SHALL NOT pretend they never
> occurred.**

> **Terraform source reversion SHALL be reviewed through a new plan
> before Production apply.**

> **Automated rollback SHALL stop where irreversible data or external
> effects make safety uncertain.**

> **Every material rollback SHALL be followed by service and business
> verification.**

> **ZuriBeans SHALL complete a controlled rollback exercise before
> Production go-live.**

------------------------------------------------------------------------

## 60. Implementation Implications

Implementation SHALL establish:

``` text
Release Safety
│
├── Immutable Rollback
│   ├── previous digest
│   ├── previous manifest
│   └── ECS rollback
│
├── Database Safety
│   ├── expand
│   ├── migrate
│   ├── verify
│   ├── contract
│   └── recovery point
│
├── Data Migration
│   ├── bounded batches
│   ├── checkpoints
│   ├── idempotency
│   └── validation
│
├── Compatibility
│   ├── APIs
│   ├── events
│   ├── workers
│   └── old/new runtime
│
├── Reconciliation
│   ├── payments
│   ├── ERP
│   ├── logistics/customs
│   └── external systems
│
└── Verification
    ├── health
    ├── synthetics
    ├── telemetry
    ├── tenant isolation
    └── business correctness
```

Implementation SHALL consult the accepted ADRs in every affected
repository before defining rollback or migration commands.

------------------------------------------------------------------------

## 61. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0023 --- Infrastructure Security, Compliance and Audit**

It shall define:

-   security baseline;
-   least privilege;
-   encryption;
-   vulnerability management;
-   network/security posture;
-   audit logging;
-   CloudTrail;
-   AWS Config/Security Hub/GuardDuty where adopted;
-   policy enforcement;
-   Production access;
-   evidence retention;
-   POPIA/data-protection considerations;
-   tenant/legal-entity audit isolation;
-   incident evidence;
-   and security controls required before ZuriBeans Production go-live.
