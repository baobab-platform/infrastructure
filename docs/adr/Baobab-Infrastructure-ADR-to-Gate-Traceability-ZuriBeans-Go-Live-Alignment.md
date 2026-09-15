# Baobab Infrastructure ADR-to-Gate Traceability & ZuriBeans Go-Live Alignment Matrix

-   **Status:** Implementation Master Plan
-   **Date:** 2026-09-15
-   **Primary repository:** `nabhold/infrastructure`
-   **Architectural authority:** ADR-Infra-0001 through ADR-Infra-0024
    --- Accepted
-   **First production proving estate:** ZuriBeans
-   **Companion plan:** Existing ZuriBeans Go-Live Implementation
    Masterplan
-   **Affected repositories:** `nabhold/infrastructure`,
    `nabhold/shared`, `nabhold/baobab-cp`, `nabhold/baobab-iam`,
    `nabhold/baobab-trade`, `nabhold/baobab-erp`, `nabhold/baobab-cms`,
    `nabhold/baobab-pulse`, `nabhold/zuribeans`

------------------------------------------------------------------------

# 1. Purpose

This document converts the 24 accepted infrastructure ADRs into an
executable, dependency-ordered implementation programme.

It does **not** replace the ZuriBeans Go-Live Implementation Masterplan.

Instead:

``` text
Infrastructure ADRs
      │
      ▼
INFRA Gates
      │
      │ provide production platform capability
      ▼
ZuriBeans Go-Live Gates
      │
      │ consume and prove those capabilities
      ▼
ZuriBeans Production Go-Live
```

The two plans operate at different levels:

-   **INFRA Gates** implement the physical/cloud/platform deployment
    substrate.
-   **ZuriBeans Go-Live Gates** implement and prove ZuriBeans
    business/runtime readiness.
-   **Cross-repository gates** prove canonical context, IAM, Trade, ERP
    and event integration.
-   **Final qualification** proves the whole system together.

------------------------------------------------------------------------

# 2. Governing Implementation Rule

Do not implement ADRs mechanically one at a time.

Use:

``` text
Accepted ADR
    │
    ▼
Normative Requirement
    │
    ▼
Implementation Task
    │
    ▼
Dependency-Ordered INFRA Gate
    │
    ▼
PR + CI + Review
    │
    ▼
Verification Evidence
    │
    ▼
ZuriBeans Go-Live Consumption/Proof
```

Every material task SHALL identify:

1.  ADR authority;
2.  affected repository;
3.  implementation change;
4.  acceptance criteria;
5.  verification evidence;
6.  ZuriBeans dependency where applicable.

------------------------------------------------------------------------

# 3. Gate Naming

Infrastructure gates use the prefix `INFRA-`.

This deliberately avoids collision with the existing ZuriBeans/Trade
gates.

``` text
INFRA-01 ... INFRA-12
```

Existing ZuriBeans B2B Commerce gates remain:

``` text
ZB-00 Discovery
ZB-01 Core Medusa Health
ZB-02 Production Infrastructure
ZB-03 Baobab Context
ZB-04 Uganda and South Africa Markets
ZB-05 ZuriBeans B2B
ZB-06 B2B Catalogue and Pricing
ZB-07 Inventory
ZB-08 Payments
ZB-09 Fulfilment
ZB-10 Tax
ZB-11 Trade Readiness
ZB-12 ERP Integration
ZB-13 Events and Outbox
ZB-14 Future Engine Ports
ZB-15 Security
ZB-16 Observability
ZB-17 CI/CD
ZB-18 Simulation Readiness
```

------------------------------------------------------------------------

# 4. Overall Dependency Graph

``` text
INFRA-01 Governance / Conformance
          │
          ▼
INFRA-02 AWS Bootstrap / State / OIDC
          │
          ▼
INFRA-03 Network / Trust Zones
          │
          ├──────────────────────────┐
          ▼                          ▼
INFRA-04 Stateful Services      INFRA-05 Compute / Edge
          │                          │
          └────────────┬─────────────┘
                       ▼
          INFRA-06 IAM / Secrets / Isolation
                       │
                       ▼
          INFRA-07 Observability / SLOs
                       │
                       ▼
          INFRA-08 Backup / Restore / DR
                       │
                       ▼
          INFRA-09 CI/CD / Release Platform
                       │
                       ▼
          INFRA-10 Security / Compliance / FinOps
                       │
                       ▼
          INFRA-11 ZuriBeans Staging Vertical Slice
                       │
                       ▼
          INFRA-12 ZuriBeans Production Qualification
```

`INFRA-09` work begins earlier for CI foundations, but its gate closes
only after deploy/promotion/rollback mechanisms are proven.

------------------------------------------------------------------------

# 5. Gate Summary

  ---------------------------------------------------------------------------------
  Gate              Name              Primary Outcome             Main ADRs
  ----------------- ----------------- --------------------------- -----------------
  INFRA-01          Governance &      Repo and implementation     0001, 0003, 0020,
                    Conformance       control plane               0023, 0024
                    Foundation                                    

  INFRA-02          AWS Bootstrap,    Safe AWS/Terraform          0002, 0004, 0013,
                    State &           foundation                  0014, 0020, 0023,
                    Deployment                                    0024
                    Identity                                      

  INFRA-03          Network & Trust   Private/default-deny        0005, 0008, 0013,
                    Zones             network substrate           0015, 0023, 0024

  INFRA-04          Core Stateful     Production                  0009, 0010, 0011,
                    Platform Services data/cache/broker/gateway   0012, 0014, 0018,
                                      state                       0019

  INFRA-05          Compute, Edge &   ECS/Fargate +               0006, 0007, 0008,
                    Runtime Platform  ALB/DNS/TLS/APISIX runtime  0009, 0013, 0014,
                                                                  0017

  INFRA-06          IAM, Secrets &    Workload identity and       0013, 0014, 0015,
                    Isolation         tenant-safe runtime         0023
                    Enforcement                                   

  INFRA-07          Observability,    Operable platform           0016, 0017, 0023,
                    SLOs &                                        0024
                    Operational                                   
                    Readiness                                     

  INFRA-08          Backup, Restore,  Recoverable platform        0018, 0019, 0022,
                    HA & DR                                       0023, 0024

  INFRA-09          CI/CD, Artifact   Controlled immutable        0007, 0020, 0021,
                    Promotion &       delivery                    0022, 0023
                    Release Platform                              

  INFRA-10          Security,         Production governance       0023, 0024 plus
                    Compliance &      controls                    cross-cutting
                    FinOps                                        controls

  INFRA-11          ZuriBeans Staging End-to-end production-like  All relevant ADRs
                    Vertical Slice    proof                       

  INFRA-12          ZuriBeans         Go-live evidence and        All 24 ADRs
                    Production        controlled launch           
                    Qualification                                 
  ---------------------------------------------------------------------------------

------------------------------------------------------------------------

# 6. INFRA-01 --- Governance & Conformance Foundation

## Objective

Turn `nabhold/infrastructure` into the controlled implementation
authority for environment provisioning and deployment without absorbing
application or tenant-management business logic.

## Tasks

  ----------------------------------------------------------------------------------------------------------------------------------
  ID             Task                                        Repositories      ADR Authority  Acceptance / Evidence
  -------------- ------------------------------------------- ----------------- -------------- --------------------------------------
  I01-01         Audit current infrastructure repo against   infrastructure    0001--0024     Written gap report:
                 all 24 ADRs                                                                  implemented/partial/missing/conflict

  I01-02         Treat ADR-Infra-0001--0024 as Accepted and  infrastructure    all            ADR index generated; no Proposed
                 validate metadata/index                                                      ambiguity

  I01-03         Create ADR requirement register extracting  infrastructure    all            Machine/reviewable requirement IDs
                 SHALL/MUST/SHOULD statements                                                 

  I01-04         Establish target repo directories:          infrastructure    0001, 0003     Structure exists without premature
                 `terraform/`, `deploy/`, `observability/`,                                   resources
                 `backup/`, `docs/runbooks/`                                                  

  I01-05         Define Terraform formatting/validation/lint infrastructure,   0003, 0020     CI rejects invalid Terraform
                 conventions                                 shared                           

  I01-06         Define module/environment composition rules infrastructure    0003           No primary environment separation via
                                                                                              workspaces

  I01-07         Define environment naming and               infrastructure    0002, 0024     dev/staging/prod vocabulary canonical
                 account/region metadata                                                      

  I01-08         Implement mandatory tag schema and          infrastructure    0024           Tag tests pass
                 Terraform tag helper                                                         

  I01-09         Extend CODEOWNERS for Terraform, IAM,       infrastructure    0020, 0023     Sensitive paths require owners
                 security, production manifests                                               

  I01-10         Add policy-as-code skeleton for accepted    infrastructure,   0020, 0023,    Baseline policies execute in CI
                 invariants                                  shared            0024           

  I01-11         Preserve `shared` as cross-repo             infrastructure,   0001, 0020     No duplicate canonical contracts
                 contract/workflow authority                 shared                           

  I01-12         Create implementation evidence              infrastructure    0020, 0023     Each gate can record verification
                 directory/convention                                                         evidence

  I01-13         Create gate status ledger:                  infrastructure    all            Single implementation status source
                 NOT_STARTED/IN_PROGRESS/BLOCKED/PASS/FAIL                                    

  I01-14         Document exception/superseding-ADR process  infrastructure    0020, 0023     Silent architecture divergence
                                                                                              prohibited
  ----------------------------------------------------------------------------------------------------------------------------------

## Exit Gate

``` text
[ ] ADR inventory complete
[ ] requirement register complete
[ ] current-state gap analysis complete
[ ] CI foundation active
[ ] tagging vocabulary established
[ ] implementation/evidence conventions established
[ ] no implementation conflict silently overrides an ADR
```

## ZuriBeans Alignment

Supports **ZB-00 Discovery** and **ZB-17 CI/CD**. The ZuriBeans plan
already requires discovery before modification and production quality
gates; this INFRA gate provides the infrastructure-side equivalent.

------------------------------------------------------------------------

# 7. INFRA-02 --- AWS Bootstrap, Terraform State & Deployment Identity

## Objective

Create the minimum secure AWS/Terraform control foundation before
application infrastructure.

## Tasks

  --------------------------------------------------------------------------------------------------
  ID             Task                        Repositories     ADR Authority  Acceptance / Evidence
  -------------- --------------------------- ---------------- -------------- -----------------------
  I02-01         Confirm AWS                 infrastructure   0002           Explicit
                 environment/account                                         dev/staging/prod
                 topology                                                    account decision
                                                                             recorded

  I02-02         Establish `af-south-1` as   infrastructure   0002           No market→region
                 initial production region                                   hardcoding
                 in environment composition                                  

  I02-03         Build Terraform bootstrap   infrastructure   0004           Bootstrap can be run
                 root for remote state                                       independently

  I02-04         Create encrypted/versioned  infrastructure   0004, 0023     Encryption/versioning
                 S3 state storage                                            verified

  I02-05         Configure Terraform state   infrastructure   0004           Concurrent apply test
                 locking using approved                                      fails safely
                 current Terraform/AWS                                       
                 mechanism                                                   

  I02-06         Restrict state bucket/KMS   infrastructure   0004, 0013,    Workload roles cannot
                 access                                       0014           read state

  I02-07         Create GitHub Actions OIDC  infrastructure   0013, 0020     No long-lived AWS key
                 provider/trust                                              required

  I02-08         Create distinct Terraform   infrastructure   0013, 0020     Read/plan privileges
                 plan roles                                                  only

  I02-09         Create distinct environment infrastructure   0013, 0020     Production role
                 apply roles                                                 isolated

  I02-10         Restrict Production role    infrastructure   0013, 0020,    Untrusted PR assumption
                 trust to approved                            0023           DENY
                 repo/workflow/environment                                   

  I02-11         Establish baseline KMS key  infrastructure   0014, 0023     Key admin/use
                 strategy                                                    separation verified

  I02-12         Establish baseline Secrets  infrastructure   0014           No plaintext secrets
                 Manager/Parameter Store                                     
                 namespaces                                                  

  I02-13         Apply baseline              infrastructure   0024           Cost allocation
                 cost/ownership tags                                         metadata visible

  I02-14         Configure Terraform state   infrastructure   0004, 0018     Version recovery
                 recovery runbook                                            procedure tested

  I02-15         Add CloudTrail visibility   infrastructure   0023           OIDC role session
                 for deployment-role                                         traceable
                 assumption                                                  

  I02-16         Document bootstrap          infrastructure   0004, 0018,    Recovery evidence
                 disaster/recovery procedure                  0019           produced
  --------------------------------------------------------------------------------------------------

## Exit Gate

``` text
GitHub Actions
      │ OIDC
      ▼
Plan Role / Apply Role
      │
      ▼
Terraform
      │
      ├── encrypted state
      ├── locking
      ├── KMS
      └── auditable AWS actions
```

No static AWS deployment credentials SHALL be required.

## ZuriBeans Alignment

Prerequisite for **ZB-02 Production Infrastructure** and **ZB-17
CI/CD**.

------------------------------------------------------------------------

# 8. INFRA-03 --- Network & Trust-Zone Architecture

## Objective

Implement the accepted ingress/application/data/management trust
boundaries.

## Tasks

  -----------------------------------------------------------------------------------------------
  ID             Task                        Repositories     ADR Authority  Acceptance /
                                                                             Evidence
  -------------- --------------------------- ---------------- -------------- --------------------
  I03-01         Implement VPC module        infrastructure   0003, 0005     Terraform tests/plan

  I03-02         Create multi-AZ             infrastructure   0005, 0019     AZ placement
                 ingress/public subnets only                                 verified
                 where required                                              

  I03-03         Create private application  infrastructure   0005           No direct internet
                 subnets                                                     ingress

  I03-04         Create private data subnets infrastructure   0005, 0023     Public route absent

  I03-05         Define management/control   infrastructure   0005, 0013     No public
                 access paths                                                SSH/bastion by
                                                                             default

  I03-06         Implement security-group    infrastructure   0005           Explicit
                 composition                                                 source→destination
                                                                             rules

  I03-07         Implement default-deny      infrastructure   0005, 0023     Negative
                 between trust zones                                         connectivity tests

  I03-08         Define ALB→APISIX permitted infrastructure   0008           Only approved ports
                 flow                                                        

  I03-09         Define APISIX→service       infrastructure   0008           Backend not public
                 permitted flow                                              

  I03-10         Define                      infrastructure   0005           Workload-scoped SG
                 service→RDS/Redis/Rabbit                                    tests
                 permitted flows                                             

  I03-11         Keep APISIX Admin and etcd  infrastructure   0008, 0009,    Internet
                 management paths private                     0023           reachability DENY

  I03-12         Evaluate NAT topology       infrastructure   0019, 0024     Decision recorded
                 against HA/cost                                             

  I03-13         Evaluate VPC endpoints for  infrastructure   0005, 0024     Cost/security
                 ECR/S3/Secrets/CloudWatch                                   tradeoff recorded
                 etc.                                                        

  I03-14         Add reachability/security   infrastructure   0023           Public
                 fitness tests                                               DB/cache/broker
                                                                             tests DENY

  I03-15         Document network diagram    infrastructure   0005           Docs match Terraform
                 and trust flows                                             
  -----------------------------------------------------------------------------------------------

## Exit Gate

``` text
Internet
   │
   ▼
Ingress
   │
   ▼
Application
   │
   ▼
Data

Management = separately controlled
```

## ZuriBeans Alignment

Provides physical prerequisites for **ZB-02**, **ZB-03**, **ZB-15** and
later staging/go-live.

------------------------------------------------------------------------

# 9. INFRA-04 --- Core Stateful Platform Services

## Objective

Provide production-grade data, cache, messaging and gateway
configuration state.

## Tasks

  ------------------------------------------------------------------------------------------------------
  ID             Task                              Repositories       ADR Authority  Acceptance /
                                                                                     Evidence
  -------------- --------------------------------- ------------------ -------------- -------------------
  I04-01         Implement RDS PostgreSQL 17       infrastructure     0010           Private/encrypted
                 Terraform module                                                    instance

  I04-02         Configure Multi-AZ for critical   infrastructure     0010, 0019     Failover
                 Production PostgreSQL                                               configuration
                                                                                     verified

  I04-03         Configure RDS                     infrastructure     0010, 0018     Restore point
                 backups/PITR/deletion protection                                    exists

  I04-04         Define service/database ownership infrastructure +   0010, 0015     No shared
                 model                             consuming repos                   application schema
                                                                                     authority

  I04-05         Implement                         infrastructure     0011           Private/TLS/auth as
                 ElastiCache/Valkey-compatible                                       supported
                 cache module                                                        

  I04-06         Define cache                      infrastructure +   0011, 0018     Cache loss test
                 eviction/TTL/reconstructability   apps                              planned
                 defaults                                                            

  I04-07         Implement Amazon MQ RabbitMQ      infrastructure     0012           Private
                 production topology                                                 AMQPS/cluster as
                                                                                     required

  I04-08         Configure RabbitMQ monitoring and infrastructure,    0012, 0016     Broker health
                 durable topology assumptions      shared                            observable

  I04-09         Define DLQ/retry topology         shared,            0012           App-owned
                 contract boundaries               infrastructure,                   semantics, infra
                                                   apps                              substrate

  I04-10         Implement production APISIX       infrastructure     0009           Multiple APISIX
                 runtime state dependencies                                          nodes supported

  I04-11         Implement three-member etcd       infrastructure     0009           Quorum/TLS/auth
                 quorum design                                                       verified

  I04-12         Implement encrypted etcd snapshot infrastructure     0009, 0018     Snapshot restore
                 process                                                             test

  I04-13         Confirm Redis is not accidental   consuming repos    0011, 0018     Recovery test
                 source of truth                                                     reconstructs
                                                                                     projections

  I04-14         Define RDS/Redis/Rabbit/etcd      infrastructure     0017           Alert evidence
                 alarms                                                              

  I04-15         Validate stateful resource        infrastructure     0024           Ownership/cost
                 tags/lifecycle                                                      visible
  ------------------------------------------------------------------------------------------------------

## Exit Gate

All stateful services are private, encrypted where required, observable
and recoverable. Creating a resource is insufficient; restore/failure
semantics must be known.

## ZuriBeans Alignment

Directly supports **ZB-02 Production Infrastructure**, **ZB-07
Inventory**, **ZB-12 ERP Integration**, **ZB-13 Events and Outbox**, and
**ZB-16 Observability**.

------------------------------------------------------------------------

# 10. INFRA-05 --- Production Compute, Edge & Runtime Platform

## Objective

Provide the production runtime substrate for Baobab services and digital
estates.

## Tasks

  ---------------------------------------------------------------------------------------------
  ID             Task                         Repositories       ADR Authority  Acceptance /
                                                                                Evidence
  -------------- ---------------------------- ------------------ -------------- ---------------
  I05-01         Implement ECS                infrastructure     0006           ECS/Fargate
                 cluster/environment module                                     operational

  I05-02         Implement reusable ECS       infrastructure     0006           Multiple
                 service/task module                                            services deploy
                                                                                independently

  I05-03         Separate ECS execution role  infrastructure     0013           IAM tests
                 from task role                                                 

  I05-04         Enforce immutable image      infrastructure     0007, 0021     Mutable-only
                 digest input                                                   deployment
                                                                                rejected

  I05-05         Configure task logging/OTel  infrastructure     0016           Telemetry
                 hooks                                                          emitted

  I05-06         Configure                    infrastructure +   0017           Unready tasks
                 readiness/liveness/startup   apps                              receive no
                 semantics per service                                          traffic

  I05-07         Implement ALB                infrastructure     0008           Multi-AZ health
                                                                                verified

  I05-08         Implement Route53 DNS        infrastructure     0008           DNS controlled
                 records                                                        by Terraform

  I05-09         Implement ACM certificate    infrastructure     0008, 0014     HTTPS
                 lifecycle                                                      certificate
                                                                                valid

  I05-10         Implement APISIX behind      infrastructure     0008, 0009     Admin remains
                 approved edge path                                             private

  I05-11         Evaluate/configure WAF for   infrastructure     0008, 0023     Policy recorded
                 public estate/API paths                                        

  I05-12         Configure ECS rolling        infrastructure     0006, 0022     Failure
                 deployment/circuit breaker                                     exercise
                 defaults                                                       

  I05-13         Define workload resource     infrastructure     0017, 0024     CPU/memory
                 sizing/capacity profiles                                       evidence

  I05-14         Validate Fargate Spot only   infrastructure     0006, 0024     Critical path
                 for interruption-tolerant                                      not Spot-only
                 work                                                           

  I05-15         Document static/edge hosting infrastructure     0006, 0021     Same immutable
                 exception path if a digital                                    release
                 estate is not containerized                                    governance
                                                                                retained
  ---------------------------------------------------------------------------------------------

## Exit Gate

A trivial reference service SHALL deploy through ALB/APISIX to private
ECS using an immutable digest, workload identity, TLS, health checks and
telemetry.

## ZuriBeans Alignment

Foundation for **ZB-02**, **ZB-16**, **ZB-17**, and the ZuriBeans
frontend/digital estate go-live.

------------------------------------------------------------------------

# 11. INFRA-06 --- IAM, Secrets & Tenant/Workload Isolation

## Objective

Prove that infrastructure identity and Baobab application identity
remain distinct and that ZuriBeans cannot cross legal-entity boundaries.

## Tasks

  ----------------------------------------------------------------------------------------------------------------------------------
  ID             Task                                                       Repositories       ADR Authority  Acceptance / Evidence
  -------------- ---------------------------------------------------------- ------------------ -------------- ----------------------
  I06-01         Define per-workload ECS task roles                         infrastructure     0013           No shared universal
                                                                                                              runtime role

  I06-02         Implement least-privilege Secrets Manager policies         infrastructure     0014           Wrong-workload secret
                                                                                                              DENY

  I06-03         Implement Parameter Store configuration namespaces         infrastructure     0014           Environment separation

  I06-04         Implement KMS use/admin separation                         infrastructure     0014           Task role cannot
                                                                                                              administer key

  I06-05         Deploy/host `baobab-iam`/Keycloak according to its         infrastructure,    0013, 0015,    IAM health and
                 accepted ADRs                                              baobab-iam         0023           persistence proven

  I06-06         Ensure AWS IAM is not used as tenant authorization         infrastructure,    0013, 0015     Architecture fitness
                                                                            baobab-iam, cp                    test

  I06-07         Implement physical consequences of `IsolationProfile`      infrastructure,    0015           Profile→resource
                                                                            cp, shared                        mapping deterministic

  I06-08         Preserve                                                   cp, shared,        0015           Contract/conformance
                 `Tenant ≠ LegalEntity ≠ DigitalEstate ≠ Market ≠ Region`   infrastructure                    tests

  I06-09         Add ZuriBeans→Thamani secret negative test                 infrastructure     0015, 0023     DENY

  I06-10         Add Thamani→ZuriBeans secret negative test                 infrastructure     0015, 0023     DENY

  I06-11         Add app-role→Terraform-state negative test                 infrastructure     0013, 0023     DENY

  I06-12         Add app-role→KMS-admin negative test                       infrastructure     0013, 0014     DENY

  I06-13         Establish break-glass path and audit                       infrastructure     0013, 0023     Controlled
                                                                                                              test/evidence

  I06-14         Establish secret rotation procedure                        infrastructure +   0014, 0022     Rotation exercise
                                                                            apps                              

  I06-15         Document legal-entity/isolation responsibility matrix      infrastructure,    0015           No tenant=VPC
                                                                            shared, cp                        assumption
  ----------------------------------------------------------------------------------------------------------------------------------

## Exit Gate

``` text
ZuriBeans workload → ZuriBeans-authorized resource  ALLOW
ZuriBeans workload → Thamani secret/resource        DENY
Application role   → Terraform state/admin KMS      DENY
```

## ZuriBeans Alignment

Directly complements **ZB-03 Baobab Context**, **ZB-05 B2B
authorization**, and **ZB-15 Security**. The existing
platform-resolution work also requires ZuriBeans↛Thamani,
Thamani↛ZuriBeans and no implicit Nabhold subsidiary authority.

------------------------------------------------------------------------

# 12. INFRA-07 --- Observability, SLOs & Operational Readiness

## Objective

Make the platform diagnosable before it is declared production-ready.

## Tasks

  -------------------------------------------------------------------------------------------------
  ID             Task                      Repositories       ADR Authority  Acceptance / Evidence
  -------------- ------------------------- ------------------ -------------- ----------------------
  I07-01         Implement production OTel infrastructure     0016           HA/health appropriate
                 collector deployment                                        to role

  I07-02         Configure logs            infrastructure     0016           Structured logs
                 backend/CloudWatch                                          queryable

  I07-03         Configure metrics backend infrastructure     0016           Runtime/platform
                                                                             metrics visible

  I07-04         Configure                 infrastructure     0016           Cross-service trace
                 traces/X-Ray-compatible                                     proven
                 path                                                        

  I07-05         Enforce W3C trace         shared + apps      0016           HTTP trace continuity
                 propagation                                                 

  I07-06         Propagate                 shared + apps      0016           Async trace evidence
                 correlation/trace                                           
                 metadata through RabbitMQ                                   

  I07-07         Define stable             shared,            0016           No ambiguous telemetry
                 service/environment       infrastructure                    
                 identity attributes                                         

  I07-08         Define safe tenant        infrastructure,    0016, 0023,    No customer/order IDs
                 metadata/cardinality      shared             0024           as uncontrolled metric
                 policy                                                      dimensions

  I07-09         Establish service         infrastructure +   0017           No arbitrary invented
                 SLIs/SLO candidates from  apps                              SLOs
                 measurements                                                

  I07-10         Implement                 infrastructure     0017           Alert test
                 burn-rate/critical alerts                                   
                 where SLOs accepted                                         

  I07-11         Implement                 infrastructure     0017, 0024     ECS/RDS/cache/broker
                 capacity/saturation                                         visible
                 dashboards                                                  

  I07-12         Implement ZuriBeans       infrastructure,    0017           B2B journey observable
                 synthetic critical        zuribeans, trade                  
                 journeys                                                    

  I07-13         Create alert              infrastructure     0017           Every critical alert
                 ownership/runbook links                                     actionable

  I07-14         Set explicit log          infrastructure     0024           No accidental infinite
                 retention                                                   ordinary logs

  I07-15         Add release markers to    infrastructure     0021, 0022     Deploy/rollback
                 telemetry                                                   correlation
  -------------------------------------------------------------------------------------------------

## Exit Gate

An operator can answer:

``` text
What failed?
Where?
For which service/context?
Since which release?
What dependency is saturated?
What customer journey is affected?
```

## ZuriBeans Alignment

Directly fulfills infrastructure dependencies of **ZB-16 Observability**
and supports the Control Plane resolution gate requiring operators to
explain why a request routed to an EngineInstance.

------------------------------------------------------------------------

# 13. INFRA-08 --- Backup, Restore, HA & Disaster Recovery

## Objective

Prove recoverability rather than merely configure backup checkboxes.

## Tasks

  ----------------------------------------------------------------------------------------------------------------------------------
  ID             Task                   Repositories       ADR Authority  Acceptance / Evidence
  -------------- ---------------------- ------------------ -------------- ----------------------------------------------------------
  I08-01         Classify every         infrastructure +   0018           Authoritative/durable/reconstructable/ephemeral register
                 production state store service owners                    

  I08-02         Assign recovery tier   infrastructure +   0018, 0019     No universal invented targets
                 and proposed RPO/RTO   business/service                  
                 ownership              owners                            

  I08-03         Implement RDS          infrastructure     0018           Restore test
                 automated backup/PITR                                    
                 policy                                                   

  I08-04         Implement etcd         infrastructure     0009, 0018     Restore APISIX config
                 snapshot                                                 
                 schedule/storage                                         

  I08-05         Define RabbitMQ        infrastructure,    0012, 0018     Broker loss does not become data-authority loss
                 topology               shared                            
                 reconstruction                                           

  I08-06         Prove Redis/Valkey     infrastructure +   0011, 0018     Cache loss exercise
                 reconstruction         apps                              

  I08-07         Protect Terraform      infrastructure     0004, 0018     State restore test
                 state recovery chain                                     

  I08-08         Verify Keycloak        infrastructure,    0018           Authentication works after restore
                 recovery dependencies  iam                               

  I08-09         Verify Trade database  infrastructure,    0018           Orders/inventory/payment refs intact
                 recovery               trade                             

  I08-10         Verify ERP recovery    infrastructure,    0018           Business partner/order/financial mapping intact
                                        erp                               

  I08-11         Verify CMS DB/object   infrastructure,    0018           DB/media consistency
                 recovery               cms                               

  I08-12         Implement              infrastructure     0019           Failure exercise
                 multi-AZ/failover for                                    
                 critical components                                      

  I08-13         Define active-passive  infrastructure     0019           Reconstruction steps documented
                 regional DR runbook                                      

  I08-14         Preserve immutable     infrastructure     0007, 0019     No source rebuild required
                 artifacts for DR                                         

  I08-15         Test recovery          all affected       0019           Identity→network→keys→data→IAM→CP→gateway→engines→estate
                 sequencing                                               

  I08-16         Test tenant-specific   infrastructure +   0018, 0022     ZuriBeans repair does not damage Thamani
                 recovery without whole apps                              
                 shared DB destructive                                    
                 rollback                                                 

  I08-17         Run tabletop DR        all affected       0019           Evidence and corrections
                 exercise                                                 

  I08-18         Define                 infrastructure     0019           One authoritative writer by default
                 failback/split-brain                                     
                 controls                                                 
  ----------------------------------------------------------------------------------------------------------------------------------

## Exit Gate

At least one end-to-end critical restore SHALL be demonstrated before
ZuriBeans production qualification.

## ZuriBeans Alignment

Supports **ZB-07**, **ZB-12**, **ZB-13**, **ZB-15**, **ZB-16**, and
final go-live. ERP outage must not corrupt committed commerce state;
cache/broker failures must be bounded and recoverable.

------------------------------------------------------------------------

# 14. INFRA-09 --- CI/CD, Immutable Artifacts, Release Manifests & Rollback

## Objective

Create the controlled delivery mechanism from application repository to
Production.

## Tasks

  ---------------------------------------------------------------------------------------------------------------------------
  ID             Task                              Repositories       ADR Authority  Acceptance / Evidence
  -------------- --------------------------------- ------------------ -------------- ----------------------------------------
  I09-01         Implement Terraform PR workflow   infrastructure,    0020           fmt/validate/lint/security/policy/plan
                                                   shared                            

  I09-02         Implement protected post-merge    infrastructure     0020           PR cannot apply Production
                 deploy workflow                                                     

  I09-03         Configure environment             infrastructure     0004, 0020     Concurrent prod apply prevented
                 concurrency/locking                                                 

  I09-04         Pin third-party Actions/reusable  infrastructure,    0020, 0023     Supply-chain review
                 workflows according to policy     shared                            

  I09-05         Implement drift-detection         infrastructure     0020           Report, no blind destructive remediation
                 workflow                                                            

  I09-06         Define component-release contract shared             0021           Versioned schema
                 in `shared`                                                         

  I09-07         Define                            shared             0021           Versioned schema
                 environment-release-manifest                                        
                 contract in `shared`                                                

  I09-08         Implement manifest validation     infrastructure     0021           Invalid/mutable/secret-bearing manifest
                                                                                     rejected

  I09-09         Verify artifact                   infrastructure     0007, 0021,    Unknown artifact fails
                 digest/provenance/security before                    0023           
                 deploy                                                              

  I09-10         Implement                         app repos +        0007, 0021     Staging digest == Production digest
                 build-once/promote-same-digest    infrastructure                    
                 flow                                                                

  I09-11         Render/register ECS task          infrastructure     0006, 0021     Reproducible task revision
                 definitions from manifest/config                                    
                 refs                                                                

  I09-12         Externalize environment           infrastructure     0014, 0021     No secret values in manifest
                 config/secrets                                                      

  I09-13         Implement controlled migration    infrastructure +   0010, 0022     No Terraform `local-exec` app migration
                 task mechanism                    app repos                         

  I09-14         Implement                         app repos +        0022           Destructive contraction delayed
                 expand→migrate→verify→contract    infrastructure                    
                 gate metadata                                                       

  I09-15         Retain previous known-good        infrastructure     0021, 0022     Rollback target known
                 release manifest/digest                                             

  I09-16         Implement ECS stateless rollback  infrastructure     0022           Controlled exercise passes
                 path                                                                

  I09-17         Implement rollback decision       infrastructure +   0022           No blind rollback
                 checklist for DB/external effects domain repos                      

  I09-18         Record deployment evidence        infrastructure     0020, 0021,    PR→workflow→role→resource→verification
                                                                      0023           chain

  I09-19         Implement post-deploy             infrastructure     0017, 0021     Apply success alone insufficient
                 synthetic/health gates                                              

  I09-20         Create                            infrastructure     0020, 0022     Operational test
                 failed-release/emergency-change                                     
                 runbooks                                                            
  ---------------------------------------------------------------------------------------------------------------------------

## Exit Gate

``` text
App Repo
  │
  ▼
Immutable Artifact
  │
  ▼
Release Manifest PR
  │
  ▼
Protected Deployment
  │
  ▼
Verification
  │
  ├── PASS → release
  └── FAIL → safe rollback/forward-fix decision
```

## ZuriBeans Alignment

Directly fulfills **ZB-17 CI/CD** and supports all go-live release
gates. Existing ZuriBeans requirements already demand
format/lint/typecheck/unit/integration/contract/migration/build/container/dependency/secret
scanning; infrastructure adds governed Production promotion.

------------------------------------------------------------------------

# 15. INFRA-10 --- Security, Compliance & FinOps

## Objective

Close the production governance controls that cut across every resource.

## Tasks

  -------------------------------------------------------------------------------------------------------
  ID             Task                              Repositories       ADR Authority  Acceptance /
                                                                                     Evidence
  -------------- --------------------------------- ------------------ -------------- --------------------
  I10-01         Configure organization/account    infrastructure     0023           Multi-region
                 CloudTrail baseline                                                 management
                                                                                     events/audit storage

  I10-02         Protect audit log storage/KMS     infrastructure     0023           Workload cannot
                 access                                                              erase audit trail

  I10-03         Configure AWS Config for required infrastructure     0023           Configuration
                 resources                                                           history available

  I10-04         Configure Security Hub CSPM       infrastructure     0023           Findings aggregated
                 controls as approved                                                

  I10-05         Configure GuardDuty capabilities  infrastructure     0023           Finding path tested
                 supported/approved in target                                        
                 region                                                              

  I10-06         Route critical security findings  infrastructure     0023           Alert exercise
                 to explicit owner                                                   

  I10-07         Implement expected-deny security  infrastructure +   0015, 0023     Cross-tenant/admin
                 tests                             apps                              paths DENY

  I10-08         Implement vulnerability/security  infrastructure +   0023           Unaccepted critical
                 policy in CI                      shared + apps                     artifact blocked

  I10-09         Establish security exception      infrastructure     0023           Owner/risk/expiry
                 lifecycle                                                           

  I10-10         Map applicable privacy/POPIA      infrastructure +   0023           No claim beyond
                 requirements to controls/evidence governance                        evidence

  I10-11         Verify no Production sensitive    all affected       0023           Data-handling
                 data copied to Dev by default                                       test/process

  I10-12         Activate approved AWS             infrastructure     0024           Billing dimensions
                 cost-allocation tags                                                visible

  I10-13         Configure Production              infrastructure     0024           Alert test
                 budget/forecast alerts                                              

  I10-14         Configure cost anomaly detection  infrastructure     0024           Owner receives
                                                                                     anomaly

  I10-15         Implement explicit CloudWatch/log infrastructure     0024           Retention policy
                 retention                                                           

  I10-16         Implement ECR lifecycle           infrastructure     0007, 0024     Known-good artifact
                 preserving rollback digests                                         retained

  I10-17         Implement backup/object lifecycle infrastructure     0018, 0024     Retention matches
                 policies                                                            policy

  I10-18         Implement temporary-resource      infrastructure     0024           Cleanup candidate
                 expiry metadata/reporting                                           report

  I10-19         Implement orphan-resource         infrastructure     0024           Detect before delete
                 detection                                                           

  I10-20         Establish periodic                infrastructure     0017, 0024     Review
                 right-sizing/FinOps review                                          template/report

  I10-21         Document shared-vs-dedicated cost infrastructure     0015, 0024     ZuriBeans not
                 allocation                                                          assigned all shared
                                                                                     infra

  I10-22         Create                            infrastructure, cp 0015, 0024     Shared resources
                 decommissioning/tenant-resource                                     preserved
                 cleanup runbook                                                     
  -------------------------------------------------------------------------------------------------------

## Exit Gate

Security findings, compliance evidence, ownership, cost visibility and
lifecycle governance are operational---not merely documented.

## ZuriBeans Alignment

Completes infrastructure-side requirements for **ZB-15 Security**,
**ZB-16 Observability**, **ZB-17 CI/CD**, and final production
readiness.

------------------------------------------------------------------------

# 16. INFRA-11 --- ZuriBeans Staging Vertical Slice

## Objective

Use ZuriBeans as the first real estate to prove that the infrastructure
ADRs work together.

This gate SHALL NOT create duplicate ZuriBeans business functionality.
It deploys and verifies the business capabilities already implemented by
the ZuriBeans/Trade/ERP/IAM/Control Plane plans.

## Tasks

  ----------------------------------------------------------------------------------------------------------------------------
  ID          Task                              Repositories       ADR Authority   ZuriBeans   Evidence
                                                                                   Alignment   
  ----------- --------------------------------- ------------------ --------------- ----------- -------------------------------
  I11-01      Re-audit affected repos and       all affected       0001, 0020      ZB-00       Cross-repo readiness report
              accepted ADRs before deployment                                                  

  I11-02      Publish immutable staging         app repos          0007, 0021      ZB-17       Digests/provenance
              artifacts for CP/IAM/Trade/ERP                                                   
              adapters/CMS/Pulse/ZuriBeans as                                                  
              applicable                                                                       

  I11-03      Create staging environment        infrastructure,    0021            ZB-17       Valid manifest
              release manifest                  shared                                         

  I11-04      Deploy Control Plane              infrastructure, cp 0006,           ZB-03       Health/telemetry
                                                                   0013--0017                  

  I11-05      Deploy IAM/Keycloak               infrastructure,    0013--0015,     ZB-03,      Auth journey
                                                iam                0018            ZB-15       

  I11-06      Deploy Baobab Trade               infrastructure,    0006,           ZB-01--14   Commerce health
                                                trade              0010--0012                  

  I11-07      Deploy ERP/iDempiere              infrastructure,    0006, 0010,     ZB-12       ERP projection/reconciliation
              integration/runtime               erp                0018                        

  I11-08      Deploy CMS/Pulse dependencies     infrastructure,    0006, 0016      ZB-16       Degradation tests
              required by ZuriBeans without     cms, pulse                                     
              making them hard checkout                                                        
              dependencies                                                                     

  I11-09      Deploy APISIX routes and          infrastructure, cp 0008, 0009      ZB-03       Routing/auth tests
              ZuriBeans edge path                                                              

  I11-10      Deploy ZuriBeans estate           infrastructure,    0006, 0021      ZB-05       Estate health
                                                zuribeans                          onward      

  I11-11      Provision ZuriBeans tenant/legal  cp, iam, trade,    0015, 0021      ZB-03       Provisioning evidence
              entity/context through CP---not   erp                                            
              release manifest                                                                 

  I11-12      Verify Uganda/South Africa market cp, trade, erp     0002, 0015      ZB-04       UG/ZA context tests
              configuration                                                                    

  I11-13      Verify B2B organization           iam, trade,        0015, 0023      ZB-05       Buyer isolation
              authorization                     zuribeans                                      

  I11-14      Verify                            trade, zuribeans   cross-cutting   ZB-06       B2B journey
              catalogue/pricing/MOQ/order                                                      
              multiples                                                                        

  I11-15      Verify inventory reservation +    trade, erp         0010--0012      ZB-07,      Reconciliation evidence
              ERP projection/reconciliation                                        ZB-12       

  I11-16      Verify payment/invoice-term flow  trade, erp         0010, 0022      ZB-08,      Payment/accounting
              without conflating ERP accounting                                    ZB-12       reconciliation
              authority                                                                        

  I11-17      Verify local/bulk/cross-border    trade, erp         cross-cutting   ZB-09,      Scenario tests
              fulfilment                                                           ZB-11       

  I11-18      Verify tax provenance and         trade              0015, 0023      ZB-10       UG/ZA tests
              contextual resolution                                                            

  I11-19      Verify HS/origin/Incoterm/customs trade              cross-cutting   ZB-11       Cross-border scenario
              metadata and TradeCompliancePort                                                 

  I11-20      Verify canonical Business         cp, trade, erp,    0015            ZB-12       Mapping tests
              Partner/Product/Warehouse/Order   shared                                         
              mappings                                                                         

  I11-21      Verify transactional              trade, shared, erp 0012, 0016      ZB-13       Retry/idempotency/correlation
              outbox/canonical event path                                                      

  I11-22      Verify future engine ports remain trade              0001            ZB-14       Architecture test
              boundaries, not empty services                                                   

  I11-23      Run ZuriBeans↛Thamani/Nabhold     cp, iam, trade,    0015, 0023      ZB-15       DENY evidence
              isolation tests                   erp,                                           
                                                infrastructure                                 

  I11-24      Run end-to-end trace across       all                0016            ZB-16       Trace ID evidence
              estate→gateway→Trade→event→ERP                                                   

  I11-25      Run CI/release promotion          infrastructure +   0020, 0021      ZB-17       Release evidence
              rehearsal                         apps                                           

  I11-26      Load ZuriBeans                    trade, erp, cp     all relevant    ZB-18       Simulation report
              simulation/reference dataset only                                                
              after prerequisite gates pass                                                    

  I11-27      Run dependency outage tests       all                0017--0019      ZB-16       Safe degradation

  I11-28      Produce staging conformance       infrastructure     all             ZB-17/18    ADR→task→test→evidence
              matrix                                                                           
  ----------------------------------------------------------------------------------------------------------------------------

## Staging Critical Journeys

At minimum:

``` text
Authenticated B2B buyer
    │
    ▼
Trusted ZuriBeans Context
    │
    ▼
Organisation authorization
    │
    ▼
UG/ZA Market
    │
    ▼
B2B price/MOQ
    │
    ▼
Inventory availability
    │
    ▼
Order / PO reference
    │
    ▼
Payment terms
    │
    ▼
Fulfilment / Trade metadata
    │
    ▼
Canonical event/outbox
    │
    ▼
ERP projection
    │
    ▼
Reconciliation
```

## Exit Gate

Staging must prove **business correctness + platform isolation +
infrastructure operability**, not simply successful deployment.

------------------------------------------------------------------------

# 17. INFRA-12 --- ZuriBeans Production Go-Live Qualification

## Objective

Produce the evidence package that allows a deliberate PASS/FAIL/BLOCKED
production decision.

## Tasks

  ---------------------------------------------------------------------------------------------------------
  ID                Task                               ADR Authority     Evidence Required
  ----------------- ---------------------------------- ----------------- ----------------------------------
  I12-01            Re-run ADR conformance audit       all               No unexplained divergence
                    against deployed staging                             

  I12-02            Confirm production Terraform plan  0003, 0020        Approved plan
                    and destructive-change review                        

  I12-03            Confirm Production                 0013, 0020        No static AWS credentials
                    OIDC/protected-environment path                      

  I12-04            Confirm immutable production       0007, 0021        Artifact provenance
                    release manifest/digests                             

  I12-05            Confirm Production                 0014              Secret isolation/TLS
                    secrets/KMS/certificates                             

  I12-06            Confirm network/public exposure    0005, 0008, 0023  Reachability tests
                    posture                                              

  I12-07            Confirm ZuriBeans/Thamani/Nabhold  0015, 0023        DENY suite
                    negative isolation                                   

  I12-08            Execute representative             0017, 0024        Baseline report
                    load/capacity test                                   

  I12-09            Validate SLO/alert thresholds from 0017              SLO proposal/acceptance
                    measured behaviour                                   

  I12-10            Execute RDS restore/PITR exercise  0018              Recovery evidence

  I12-11            Execute etcd snapshot restore      0009, 0018        APISIX config recovered

  I12-12            Execute Redis reconstruction test  0011, 0018        No authoritative loss

  I12-13            Execute RabbitMQ                   0012, 0018        Durable business state preserved
                    failure/replay/idempotency test                      

  I12-14            Execute ZuriBeans controlled       0022              Previous digest restored
                    application rollback                                 

  I12-15            Execute DB migration               0022              No corrupt state
                    rollback/forward-fix safety                          
                    exercise                                             

  I12-16            Exercise secret rotation           0014, 0022        Service recovers safely

  I12-17            Exercise certificate               0008, 0014        TLS continuity
                    renewal/rotation path                                

  I12-18            Execute AZ/component failure       0019              HA evidence
                    exercise                                             

  I12-19            Execute DR tabletop/reconstruction 0019              RTO/RPO observations
                    exercise                                             

  I12-20            Verify security                    0023              CloudTrail/Config/Security
                    services/findings/incident path                      Hub/GuardDuty evidence as approved

  I12-21            Verify backup/audit evidence       0018, 0023        Workload deletion DENY
                    protection                                           

  I12-22            Verify Production                  0024              FinOps evidence
                    budget/anomaly/tagging/lifecycle                     

  I12-23            Verify synthetic B2B critical      0017              PASS
                    journeys                                             

  I12-24            Verify external-effect             0022              Payments/ERP/trade effects
                    reconciliation procedures                            

  I12-25            Verify emergency change and        0013, 0020, 0023  Controlled exercise
                    break-glass procedure                                

  I12-26            Verify runbooks and operational    0017--0023        Named owners
                    ownership                                            

  I12-27            Freeze final release candidate and 0021              Approved production candidate
                    manifest                                             

  I12-28            Produce final Production Readiness all               PASS/FAIL/BLOCKED by gate
                    Report                                               

  I12-29            Obtain explicit go-live approval   all               Recorded decision

  I12-30            Deploy through protected           0020, 0021        Deployment evidence
                    production workflow                                  

  I12-31            Run immediate post-deploy          0017, 0021        Health/synthetics/reconciliation
                    verification                                         

  I12-32            Observe defined stabilization      0017, 0022        No unresolved critical regression
                    window before declaring complete                     
  ---------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

# 18. Complete ADR-to-INFRA-Gate Traceability Matrix

  -----------------------------------------------------------------------
  ADR               Decision Area     Primary Gates     Secondary/Proof
                                                        Gates
  ----------------- ----------------- ----------------- -----------------
  ADR-Infra-0001    Environment       INFRA-01          09, 11, 12
                    Provisioner                         
                    Boundary                            

  ADR-Infra-0002    AWS Account,      INFRA-02          03, 11, 12
                    Environment and                     
                    Region Strategy                     

  ADR-Infra-0003    Terraform         INFRA-01, 02      03--10, 12
                    Architecture and                    
                    Module Strategy                     

  ADR-Infra-0004    Terraform State,  INFRA-02          08, 09, 12
                    Locking and                         
                    Bootstrap                           

  ADR-Infra-0005    Network and       INFRA-03          05, 06, 10--12
                    Trust-Zone                          
                    Architecture                        

  ADR-Infra-0006    Production        INFRA-05          07, 09, 11, 12
                    Compute Platform                    

  ADR-Infra-0007    Container         INFRA-05, 09      08, 11, 12
                    Registry and                        
                    Immutable                           
                    Artifact Strategy                   

  ADR-Infra-0008    DNS, TLS, Edge    INFRA-03, 05      06, 10--12
                    and API Gateway                     
                    Architecture                        

  ADR-Infra-0009    APISIX and etcd   INFRA-04, 05      08, 11, 12
                    Production                          
                    Architecture                        

  ADR-Infra-0010    PostgreSQL        INFRA-04          08, 09, 11, 12
                    Production                          
                    Architecture                        

  ADR-Infra-0011    Redis Production  INFRA-04          07, 08, 11, 12
                    Architecture                        

  ADR-Infra-0012    RabbitMQ          INFRA-04          07--09, 11, 12
                    Production                          
                    Architecture                        

  ADR-Infra-0013    Infrastructure    INFRA-02, 06      05, 09--12
                    IAM and Workload                    
                    Identity                            

  ADR-Infra-0014    Secrets, Keys and INFRA-02, 06      04, 05, 08--12
                    Certificate                         
                    Management                          

  ADR-Infra-0015    Tenant and        INFRA-06          03, 04, 10--12
                    Workload                            
                    Infrastructure                      
                    Isolation                           

  ADR-Infra-0016    Observability and INFRA-07          04, 05, 09, 11,
                    Telemetry                           12
                    Architecture                        

  ADR-Infra-0017    SLOs, Health,     INFRA-07          05, 09, 11, 12
                    Capacity and                        
                    Operational                         
                    Monitoring                          

  ADR-Infra-0018    Backup, Restore   INFRA-08          04, 10--12
                    and Data                            
                    Retention                           

  ADR-Infra-0019    Availability, DR  INFRA-08          03--05, 11, 12
                    and Business                        
                    Continuity                          

  ADR-Infra-0020    CI/CD and         INFRA-01, 09      02, 10--12
                    Infrastructure                      
                    Change Governance                   

  ADR-Infra-0021    Application       INFRA-09          05, 11, 12
                    Deployment,                         
                    Promotion and                       
                    Release Manifests                   

  ADR-Infra-0022    Deployment        INFRA-08, 09      04, 11, 12
                    Rollback and                        
                    Database Change                     
                    Safety                              

  ADR-Infra-0023    Infrastructure    INFRA-10          01--09, 11, 12
                    Security,                           
                    Compliance and                      
                    Audit                               

  ADR-Infra-0024    Cost Governance,  INFRA-01, 10      02--08, 11, 12
                    Tagging and                         
                    Resource                            
                    Lifecycle                           
  -----------------------------------------------------------------------

No ADR is considered implemented merely because its primary Gate passes.
Cross-cutting ADRs close only when their final proof gates pass.

------------------------------------------------------------------------

# 19. Infrastructure-to-ZuriBeans Gate Alignment

  INFRA Gate   ZuriBeans Gates Enabled/Proven
  ------------ -------------------------------------------------------
  INFRA-01     ZB-00, ZB-17
  INFRA-02     ZB-02, ZB-17
  INFRA-03     ZB-02, ZB-03, ZB-15
  INFRA-04     ZB-02, ZB-07, ZB-12, ZB-13, ZB-16
  INFRA-05     ZB-02, ZB-03, ZB-16, ZB-17
  INFRA-06     ZB-03, ZB-05, ZB-15
  INFRA-07     ZB-16, ZB-17
  INFRA-08     ZB-07, ZB-12, ZB-13, ZB-15, ZB-16
  INFRA-09     ZB-12, ZB-13, ZB-17
  INFRA-10     ZB-15, ZB-16, ZB-17
  INFRA-11     ZB-03 through ZB-18 integrated staging proof
  INFRA-12     Final production qualification of ZB-00 through ZB-18

------------------------------------------------------------------------

# 20. ZuriBeans Gate Dependencies on Infrastructure

## ZB-00 --- Discovery

Requires INFRA-01 conventions and cross-repo audit. No code changes
before current architecture, ADRs, contracts, migrations and runtime
assumptions are inspected.

## ZB-01 --- Core Medusa Health

Primarily `baobab-trade`; infrastructure must not interfere with
Medusa's native module authority.

## ZB-02 --- Production Infrastructure

This ZuriBeans gate should no longer create ad-hoc infrastructure inside
`baobab-trade`. Its production Redis, PostgreSQL, S3/object storage,
observability and related dependencies SHALL consume the governed
capabilities delivered by INFRA-02 through INFRA-07.

## ZB-03 --- Baobab Context

Depends on `baobab-cp`, `shared`, `baobab-iam`, INFRA-06 and the
accepted platform-resolution spine.
Tenant/LegalEntity/Market/DigitalEstate remain distinct.

## ZB-04 --- Uganda and South Africa Markets

Infrastructure supplies region-neutral runtime capability. Commercial
Market configuration remains application/platform context; Uganda/South
Africa do not automatically imply separate AWS regions.

## ZB-05 --- ZuriBeans B2B

Application-domain gate. INFRA-06 supplies secure
identity/secret/isolation substrate but SHALL NOT implement B2B
organisations, buyers or commercial terms.

## ZB-06 --- Catalogue and Pricing

Application-domain gate. Infrastructure provides runtime/data durability
only.

## ZB-07 --- Inventory

INFRA-04 supplies resilient Trade/ERP data services and cache/broker
substrate. Trade/ERP remain responsible for inventory
authority/projection semantics.

## ZB-08 --- Payments

Infrastructure protects secrets, connectivity, telemetry and recovery.
Trade/ERP own payment/accounting semantics.

## ZB-09 --- Fulfilment

Infrastructure provides runtime/eventing; application owns fulfilment
semantics.

## ZB-10 --- Tax

Infrastructure provides secure runtime/configuration. Tax
reference/provider semantics remain application/governance concerns.

## ZB-11 --- Trade Readiness

Infrastructure supports reliable runtime/eventing. Do not turn
infrastructure into customs/compliance authority.

## ZB-12 --- ERP Integration

INFRA-04, 06--09 provide data/event/identity/release substrate.
Canonical mappings remain Control Plane/shared authority.

## ZB-13 --- Events and Outbox

RabbitMQ is transport; transactional outbox remains in the owning
application database. Infrastructure SHALL not make RabbitMQ the system
of record.

## ZB-14 --- Future Engine Ports

No new empty infrastructure services are created merely because a future
port exists.

## ZB-15 --- Security

Closes only after both application authorization tests and
infrastructure negative-isolation/security tests pass.

## ZB-16 --- Observability

Closes only after logs/metrics/traces and business reconciliation are
visible end-to-end.

## ZB-17 --- CI/CD

Application CI and infrastructure deployment governance are
complementary. Application repos publish immutable artifacts;
infrastructure promotes/deploys them.

## ZB-18 --- Simulation Readiness

Simulation data is loaded only after prerequisite
platform/infrastructure gates are healthy. Simulation is evidence, not a
substitute for production controls.

------------------------------------------------------------------------

# 21. Cross-Repository Responsibility Matrix

  --------------------------------------------------------------------------------------------------------------------------
  Concern          infrastructure   shared      baobab-cp     baobab-iam     baobab-trade   baobab-erp     zuribeans
  ---------------- ---------------- ----------- ------------- -------------- -------------- -------------- -----------------
  AWS/Terraform    **Own**          standards   no            no             no             no             no

  Canonical        consume          **Own**     implement     consume        consume        consume        consume
  contracts                                                                                                

  Tenant/context   physical         schema      **Own**       authorize      consume        consume        consume
  resolution       consequences                                                                            
                   only                                                                                    

  Application      host/runtime     contracts   context       **Own**        consume        consume        consume
  identity                                                                                                 

  Commerce         runtime          contracts   route         auth           **Own**        integrate      UX

  ERP/accounting   runtime          contracts   route/map     auth           project        **Own**        consume

  Release artifact no               workflow    own artifact  own artifact   own artifact   own artifact   own artifact
  build                             standards                                                              

  Production       **Own**          workflow    no direct     no             no             no             no
  deployment                        standards   infra                                                      
                                                mutation                                                   

  Secrets          **Own**          standards   consume       consume        consume        consume        consume
  infrastructure                                                                                           

  Observability    **Own**          telemetry   emit          emit           emit           emit           emit
  substrate                         contracts                                                              

  Business audit   preserve         contracts   domain audit  domain audit   domain audit   domain audit   UX audit as
                   substrate                                                                               applicable

  Backup           **Own**          standards   recovery      recovery       recovery       recovery       estate
  infrastructure                                correctness   correctness    correctness    correctness    correctness

  Tenant           physical         contracts   **Own desired identity       commerce       ERP            request/consume
  provisioning     realization only             state**       provisioning   provisioning   provisioning   
  --------------------------------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

# 22. PR and Merge Strategy

Default:

``` text
One reviewable PR per INFRA Gate
```

A Gate MAY be split into sub-gates when review risk is too high.

Recommended likely splits:

``` text
INFRA-04A PostgreSQL
INFRA-04B Redis/Valkey
INFRA-04C RabbitMQ
INFRA-04D APISIX/etcd

INFRA-08A Backup/Restore
INFRA-08B HA/DR

INFRA-10A Security/Compliance
INFRA-10B FinOps/Lifecycle
```

Every PR SHALL:

``` text
1. cite affected ADRs;
2. describe current state;
3. list tasks implemented;
4. identify deliberate non-changes;
5. include tests;
6. include security/negative tests where relevant;
7. update documentation/runbooks;
8. produce verification evidence;
9. pass CI;
10. be merged only after required checks/review pass.
```

------------------------------------------------------------------------

# 23. Gate Status Model

Each task and gate SHALL use:

``` text
NOT_STARTED
IN_PROGRESS
BLOCKED
PASS
FAIL
DEFERRED_BY_ACCEPTED_DECISION
```

`DEFERRED_BY_ACCEPTED_DECISION` is valid only when an ADR explicitly
defers the capability---for example Kubernetes/EKS adoption.

"Not implemented" is not equivalent to "deferred."

------------------------------------------------------------------------

# 24. Evidence Model

Every gate should produce an evidence bundle:

``` text
docs/evidence/infra-XX/
├── implementation-summary.md
├── adr-conformance.md
├── test-results.md
├── security-negative-tests.md
├── operational-verification.md
├── screenshots-or-machine-output/   # only where useful
├── runbook-links.md
└── gate-result.md
```

Exact path may change, but evidence SHALL be durable and reviewable.

------------------------------------------------------------------------

# 25. Definition of Gate PASS

A Gate is PASS only when:

``` text
implementation exists
AND
automated checks pass
AND
negative tests pass where applicable
AND
integration behaviour is verified
AND
documentation is current
AND
operational runbook exists where needed
AND
ADR conformance is recorded
AND
no unresolved P0/P1 defect remains
```

A merged PR does not automatically mean the Gate passes.

------------------------------------------------------------------------

# 26. Priority Classification

Discovered gaps SHALL be classified:

``` text
P0 — security / tenant isolation / data corruption
P1 — canonical resolution / identity / deployment correctness
P2 — production resilience / recovery / operability
P3 — maintainability / documentation / cost hygiene
P4 — future enhancement
```

P0/P1 block later production qualification.

P4 SHALL not distract from ZuriBeans go-live.

------------------------------------------------------------------------

# 27. Explicit Non-Goals During This Programme

Do not introduce merely because infrastructure work is underway:

-   EKS/Kubernetes/Helm without a superseding decision;
-   a VPC per tenant by default;
-   an AWS account per tenant by default;
-   separate infrastructure merely for cost allocation;
-   standalone future Trade engines that existing Medusa modules already
    provide;
-   direct infrastructure-owned tenant business logic;
-   shared application databases;
-   distributed 2PC;
-   mutable Production image tags;
-   Production Terraform apply from pull requests;
-   long-lived AWS deployment keys;
-   active-active multi-region by default;
-   Redis/RabbitMQ as authoritative business state;
-   infrastructure-owned customs, tax, pricing, ERP or commerce
    semantics.

------------------------------------------------------------------------

# 28. Final Programme Completion Criteria

The infrastructure ADR programme is complete only when:

``` text
ADR-Infra-0001 ... ADR-Infra-0024
             │
             ▼
every normative requirement
             │
             ▼
implemented OR explicitly deferred by accepted decision
             │
             ▼
verified by evidence
             │
             ▼
cross-repository integration proven
             │
             ▼
ZuriBeans staging vertical slice PASS
             │
             ▼
ZuriBeans production qualification PASS
```

Final deliverables SHALL include:

1.  current-state infrastructure audit;
2.  ADR requirement register;
3.  Gate/task ledger;
4.  Terraform architecture;
5.  AWS environment architecture;
6.  network/trust-zone evidence;
7.  stateful-service recovery evidence;
8.  workload identity/secret/isolation evidence;
9.  observability/SLO evidence;
10. backup/restore/DR evidence;
11. CI/CD/release/rollback evidence;
12. security/compliance evidence;
13. cost/tag/lifecycle evidence;
14. ZuriBeans staging conformance report;
15. ZuriBeans Production Readiness Report;
16. final ADR → implementation → test → evidence matrix.

------------------------------------------------------------------------

# 29. Governing Statement

> **The infrastructure ADRs define how Baobab is safely hosted,
> deployed, observed, recovered, secured and governed.**

> **The ZuriBeans Go-Live Implementation Masterplan defines what
> ZuriBeans must prove as a production B2B digital estate.**

> **Neither replaces the other. The infrastructure programme supplies
> the governed production substrate; ZuriBeans becomes the first
> end-to-end proof that the substrate and Baobab platform architecture
> work together.**

> **No Gate may silently reinterpret an accepted ADR, and no ADR is
> considered implemented until its required behaviour is evidenced in
> the running system.**
