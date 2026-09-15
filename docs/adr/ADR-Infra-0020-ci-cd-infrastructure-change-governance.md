# ADR-Infra-0020 --- CI/CD and Infrastructure Change Governance

-   **Status:** Accepted
-   **Date:** 2026-09-15
-   **Decision Owners:** Nabhold / Baobab Platform Architecture
-   **Repository:** `nabhold/infrastructure`
-   **Supersedes:** None
-   **Related:**
    -   ADR-Infra-0001 --- Environment Provisioner Boundary
    -   ADR-Infra-0003 --- Terraform Architecture and Module Strategy
    -   ADR-Infra-0004 --- Terraform State, Locking and Bootstrap
    -   ADR-Infra-0007 --- Container Registry and Immutable Artifact
        Strategy
    -   ADR-Infra-0013 --- Infrastructure IAM and Workload Identity
    -   ADR-Infra-0014 --- Secrets, Keys and Certificate Management
    -   ADR-Infra-0016 --- Observability and Telemetry Architecture
    -   ADR-Infra-0017 --- SLOs, Health, Capacity and Operational
        Monitoring
    -   ADR-Infra-0018 --- Backup, Restore and Data Retention
    -   ADR-Infra-0019 --- Availability, Disaster Recovery and Business
        Continuity
-   **Platform Dependencies:** `nabhold/shared` reusable workflows and
    infrastructure contracts
-   **Follow-on:** ADR-Infra-0021 --- Application Deployment, Promotion
    and Release Manifests

------------------------------------------------------------------------

## 1. Context

`nabhold/infrastructure` is the authoritative repository for declarative
environment provisioning and infrastructure deployment automation.

Infrastructure changes can affect:

-   public ingress;
-   networking;
-   IAM;
-   KMS;
-   secrets;
-   compute;
-   PostgreSQL;
-   RabbitMQ;
-   Redis/Valkey;
-   APISIX and etcd;
-   observability;
-   backups;
-   Production availability.

A defective application release may affect one workload. A defective
infrastructure change can affect the entire platform.

Infrastructure delivery therefore requires stronger controls than
"workflow passed."

The repository already establishes important foundations:

-   GitHub Actions;
-   reusable workflows from `nabhold/shared`;
-   pinned workflow references;
-   Codespaces/devcontainer verification;
-   pull-request validation;
-   Production trust-boundary principles.

This ADR formalizes the complete Production change-governance model.

------------------------------------------------------------------------

## 2. Decision

Infrastructure changes SHALL use a **pull-request-driven,
policy-enforced, least-privilege, auditable delivery process**.

The normal lifecycle SHALL be:

``` text
Change
  │
  ▼
Pull Request
  │
  ▼
Static Validation
  │
  ▼
Security / Policy Checks
  │
  ▼
Terraform Plan
  │
  ▼
Human Review
  │
  ▼
Merge
  │
  ▼
Protected Environment
  │
  ▼
OIDC Role Assumption
  │
  ▼
Apply / Deploy
  │
  ▼
Verification
  │
  ▼
Evidence
```

Untrusted pull requests SHALL NOT mutate Production.

------------------------------------------------------------------------

## 3. Source Control Is the Change Authority

Normal infrastructure change SHALL originate from version-controlled
declarations.

Direct Production console changes are prohibited except approved
emergency/break-glass operations.

Any emergency manual change SHALL subsequently be:

-   documented;
-   audited;
-   reconciled into Terraform/configuration;
-   reviewed for drift.

------------------------------------------------------------------------

## 4. Branch Governance

`main` SHALL represent the accepted infrastructure source of truth.

Production-affecting changes SHALL reach `main` through reviewed pull
requests.

Direct pushes to protected `main` SHALL be disabled for normal
contributors.

Branch protection/rulesets SHOULD require:

-   required checks;
-   review;
-   up-to-date or merge-queue-compatible state where appropriate;
-   conversation resolution;
-   protected-file ownership where applicable.

------------------------------------------------------------------------

## 5. CODEOWNERS

Infrastructure-sensitive paths SHALL use CODEOWNERS or equivalent review
governance.

Examples include:

``` text
terraform/
.github/workflows/
docs/adr/
deploy/
observability/
backup/
```

Ownership SHALL reflect actual operational responsibility.

CODEOWNERS is a review-routing control, not a substitute for
least-privilege AWS authorization.

------------------------------------------------------------------------

## 6. Pull Request Pipeline

A Production-capable Terraform pull request SHOULD execute:

``` text
terraform fmt -check
       │
       ▼
terraform validate
       │
       ▼
lint
       │
       ▼
security scanning
       │
       ▼
policy-as-code
       │
       ▼
terraform plan
       │
       ▼
plan summary / review
```

Additional contract and repository checks SHALL run where applicable.

------------------------------------------------------------------------

## 7. Formatting

Terraform formatting SHALL be deterministic.

CI SHALL reject unformatted Terraform rather than silently rewrite
Production infrastructure during apply.

Generated formatting changes SHOULD be committed before review.

------------------------------------------------------------------------

## 8. Validation

Every affected Terraform root SHALL run `terraform validate` against
initialized providers/modules as appropriate.

Validation SHALL occur before an apply can be authorised.

Validation success does not imply architectural correctness; review
remains required.

------------------------------------------------------------------------

## 9. Linting

Terraform linting SHOULD detect:

-   deprecated syntax;
-   provider-specific problems;
-   suspicious patterns;
-   maintainability issues.

TFLint or an approved equivalent MAY be used.

Lint rules SHALL be version-controlled.

------------------------------------------------------------------------

## 10. Security Scanning

Infrastructure-as-code SHALL undergo automated security scanning.

Scanning SHOULD detect classes such as:

-   public databases;
-   unrestricted security groups;
-   unencrypted storage;
-   insecure IAM;
-   public management endpoints;
-   missing logging;
-   unsafe network exposure.

Scanner suppression SHALL require documented justification.

------------------------------------------------------------------------

## 11. Policy as Code

Policy-as-code SHALL enforce machine-checkable architectural invariants.

Examples:

``` text
Production RDS must not be public
Production data storage must be encrypted
APISIX Admin must not be public
Production resources require mandatory tags
Untrusted PR cannot apply
Production workload must not use mutable image tag
```

Policy SHALL implement accepted ADRs; it SHALL NOT silently redefine
them.

------------------------------------------------------------------------

## 12. Contract Verification

Infrastructure declarations SHALL continue to conform to released
contracts in `nabhold/shared`.

Contract verification SHOULD execute through the approved reusable
verification mechanism.

Changes that require a shared contract update SHALL update the contract
through its owning repository rather than duplicating a local schema.

------------------------------------------------------------------------

## 13. Terraform Plan

Every Terraform change SHALL produce a plan before apply.

The plan SHALL be generated against the intended environment/state with
appropriate read-only or narrowly scoped permissions.

The plan SHOULD expose:

-   additions;
-   changes;
-   deletions;
-   replacements;
-   sensitive/high-risk resources.

------------------------------------------------------------------------

## 14. Plan Is Review Evidence

Reviewers SHALL examine the plan, not merely the source diff.

Particular attention SHALL be given to:

-   resource destruction;
-   forced replacement;
-   IAM expansion;
-   security-group changes;
-   KMS/key changes;
-   stateful resources;
-   DNS;
-   certificates;
-   backup policy;
-   Production data services.

------------------------------------------------------------------------

## 15. Plan Freshness

An approved plan SHALL not be assumed valid indefinitely.

If relevant code, state, variables, provider versions or dependencies
change, the plan SHALL be regenerated.

Apply SHALL use a plan corresponding to the approved
revision/environment or produce equivalent controlled verification
immediately before execution.

------------------------------------------------------------------------

## 16. Pull Request Credentials

Pull-request workflows SHALL use minimal permissions.

Untrusted or fork-originated PRs SHALL NOT receive:

-   Production AWS credentials;
-   Production secret values;
-   Production Terraform write access;
-   KMS administrative access;
-   Production database credentials;
-   APISIX administrative credentials.

Validation SHOULD run without privileged secrets wherever possible.

------------------------------------------------------------------------

## 17. GitHub Actions OIDC

GitHub Actions SHALL authenticate to AWS through OpenID Connect as
defined by ADR-Infra-0013.

Long-lived AWS access keys SHALL NOT be the normal CI/CD mechanism.

``` text
GitHub Workflow
      │
      ▼
OIDC Token
      │
      ▼
AWS STS
      │
      ▼
Scoped Role
```

Trust policies SHALL restrict approved repositories,
branches/environments and audiences as appropriate.

------------------------------------------------------------------------

## 18. Plan and Apply Roles

Terraform plan and Terraform apply SHOULD use distinct permissions.

Conceptually:

``` text
Plan Role
 ├── read state
 ├── read infrastructure
 └── calculate proposed change

Apply Role
 ├── approved mutations
 └── only protected deployment path
```

A universal steady-state administrator role is rejected.

------------------------------------------------------------------------

## 19. Environment Separation

Development, Staging and Production SHALL have distinct:

-   state;
-   deployment roles;
-   protected environments;
-   secrets/configuration;
-   approvals;
-   concurrency controls.

A successful Development deployment SHALL not itself authorize
Production.

------------------------------------------------------------------------

## 20. Promotion

Infrastructure changes SHOULD progress:

``` text
Development
     │
     ▼
Staging
     │
     ▼
Production
```

For high-risk changes, successful lower-environment execution and
verification SHOULD be required before Production.

Emergency exceptions SHALL be documented.

------------------------------------------------------------------------

## 21. Production Environment Protection

Production apply SHALL use a protected GitHub Environment or equivalent
governance mechanism.

Production protection SHOULD include:

-   restricted deployment branches;
-   required reviewers where supported;
-   environment-scoped authorization;
-   deployment history;
-   concurrency protection.

Production credentials SHALL only become available after the protected
deployment gate.

------------------------------------------------------------------------

## 22. Human Approval

Production infrastructure mutation SHALL normally require explicit
approval after the proposed change is reviewable.

Approval SHALL occur close enough to execution that reviewers understand
what will be applied.

Approval of source code does not automatically imply approval of a
materially different later plan.

------------------------------------------------------------------------

## 23. Apply Trigger

Normal Production apply SHALL occur after merge to the accepted
branch/revision.

A pull request SHALL NOT directly apply Production infrastructure.

Preferred flow:

``` text
PR → plan → review → merge
                 │
                 ▼
       protected Production workflow
                 │
                 ▼
              apply
```

------------------------------------------------------------------------

## 24. Apply Concurrency

Only one conflicting Terraform apply SHALL mutate a given
state/environment at a time.

Terraform state locking SHALL be combined with GitHub workflow
concurrency.

Concurrency keys SHOULD be scoped to the affected environment/stack.

This prevents parallel approved workflows from racing unnecessarily.

------------------------------------------------------------------------

## 25. State Locking

State locking from ADR-Infra-0004 remains mandatory.

Workflow concurrency is additional protection, not a replacement for
Terraform locking.

A stuck lock SHALL be investigated before force-unlock.

Force-unlock SHALL not be routine automation.

------------------------------------------------------------------------

## 26. Destructive Changes

Plans containing destructive changes to critical Production resources
SHALL receive heightened scrutiny.

Examples:

-   RDS replacement/deletion;
-   KMS key deletion;
-   VPC replacement;
-   etcd data destruction;
-   backup-vault changes;
-   DNS removal;
-   IAM trust expansion;
-   state backend changes.

Automated policy SHOULD block clearly prohibited destruction.

------------------------------------------------------------------------

## 27. Stateful Resource Protection

Critical stateful resources SHOULD use appropriate lifecycle and
platform protections such as:

-   deletion protection;
-   backup/snapshot requirements;
-   lifecycle guards where appropriate;
-   explicit decommission procedures.

Terraform SHALL not make irreversible Production data deletion easy.

------------------------------------------------------------------------

## 28. Database Migration Boundary

Terraform SHALL provision database infrastructure but SHALL NOT casually
execute application schema migrations as opaque infrastructure side
effects.

Application schema evolution belongs to the owning service release
process.

Infrastructure and application changes SHALL coordinate when a change
requires both.

------------------------------------------------------------------------

## 29. Reusable Workflows

Common governance logic SHOULD live in versioned reusable workflows in
`nabhold/shared` where that repository is the accepted owner.

Examples:

-   environment contract verification;
-   Terraform validation;
-   security checks;
-   policy checks;
-   artifact verification.

`nabhold/infrastructure` SHALL not fork shared governance logic without
architectural reason.

------------------------------------------------------------------------

## 30. Workflow Pinning

Third-party GitHub Actions SHALL be pinned to immutable commit SHAs for
security-sensitive workflows where practical.

Version comments MAY accompany SHA pins for maintainability.

Mutable major tags alone SHOULD NOT be trusted for Production
infrastructure workflows.

------------------------------------------------------------------------

## 31. Reusable Workflow Pinning

Cross-repository reusable workflows SHALL be pinned to an approved
immutable revision or governed release reference.

Automated dependency tooling MAY propose updates.

Updates SHALL pass the same review/check process as other infrastructure
changes.

------------------------------------------------------------------------

## 32. Dependabot and Dependency Updates

Dependabot or equivalent automation SHOULD maintain:

-   GitHub Actions;
-   Terraform providers;
-   Terraform modules where appropriate;
-   development tooling.

Automated update PRs SHALL NOT bypass review or Production protections.

------------------------------------------------------------------------

## 33. Terraform Version Pinning

Terraform CLI and provider versions SHALL be constrained deliberately.

Production workflows SHALL not silently upgrade Terraform/provider
versions during unrelated changes.

Version upgrades SHALL be explicit, tested changes.

------------------------------------------------------------------------

## 34. Module Versioning

External Terraform modules SHALL use immutable or otherwise governed
version references.

Internal modules in the same repository MAY evolve atomically with
environment compositions.

Cross-repository modules, if introduced, SHALL use explicit version
governance.

------------------------------------------------------------------------

## 35. Secrets in CI

CI logs SHALL not expose secrets.

Workflows SHALL avoid:

-   printing environment variables;
-   echoing credentials;
-   dumping Terraform sensitive values;
-   uploading secret-bearing plans as public artifacts;
-   enabling indiscriminate shell tracing.

Secret handling SHALL conform to ADR-Infra-0014.

------------------------------------------------------------------------

## 36. Terraform Plan Sensitivity

Terraform plan files can contain sensitive information.

Saved binary plans SHALL be treated as sensitive CI artifacts.

If persisted:

-   access SHALL be restricted;
-   retention SHALL be bounded;
-   logs/summaries SHALL redact sensitive values.

Plan files SHALL not be committed to Git.

------------------------------------------------------------------------

## 37. CI Artifact Retention

CI artifacts SHALL use explicit retention.

Long-term audit evidence SHOULD preserve:

-   revision;
-   plan summary;
-   approvals;
-   deployment result;
-   verification result.

Sensitive transient artifacts SHALL not be retained longer than
necessary.

------------------------------------------------------------------------

## 38. Supply-Chain Security

Infrastructure CI SHALL consider software supply-chain risks.

Controls SHOULD include:

-   pinned actions;
-   least workflow permissions;
-   dependency review;
-   artifact provenance where applicable;
-   SBOMs for application artifacts;
-   secret scanning;
-   protected environments;
-   immutable deployment digests.

------------------------------------------------------------------------

## 39. Workflow Permissions

GitHub Actions SHALL declare the minimum `permissions:` required.

Broad write permissions SHALL not be inherited by default.

`contents: read` SHOULD be the baseline unless a job demonstrably needs
more.

OIDC jobs SHALL request `id-token: write` only where role assumption is
required.

------------------------------------------------------------------------

## 40. Shell Safety

Deployment scripts SHOULD use safe shell practices, including failure on
command errors and unset variables where compatible.

Scripts SHALL:

-   validate required inputs;
-   quote variables;
-   avoid hidden destructive defaults;
-   produce useful failure messages.

Complex operational logic SHOULD be tested rather than embedded as
unreviewable inline shell.

------------------------------------------------------------------------

## 41. Environment Inputs

Production workflows SHALL validate environment and stack inputs.

User-controlled workflow inputs SHALL not permit arbitrary:

-   AWS account selection;
-   role ARN injection;
-   Terraform state key;
-   secret path;
-   region;
-   destructive command.

Allowed values SHOULD be constrained.

------------------------------------------------------------------------

## 42. Manual Dispatch

`workflow_dispatch` MAY be used for controlled operational execution.

Manual dispatch SHALL NOT bypass:

-   protected environments;
-   IAM scoping;
-   plan/apply controls;
-   audit;
-   concurrency.

"Manual" does not mean "uncontrolled."

------------------------------------------------------------------------

## 43. Scheduled Workflows

Scheduled workflows MAY perform:

-   drift detection;
-   dependency checks;
-   policy validation;
-   backup verification;
-   security scanning.

Scheduled workflows SHALL not make unreviewed destructive Production
changes.

------------------------------------------------------------------------

## 44. Drift Detection

Production Terraform stacks SHALL undergo periodic drift detection.

Conceptually:

``` text
Terraform Source + State
          │
          ▼
       Plan
          │
          ▼
No Change? ── Yes ──► Healthy
    │
    No
    ▼
Drift Report
    │
    ▼
Investigate / Reconcile
```

Drift SHALL be treated as a defect unless it corresponds to an approved
external controller or documented exception.

------------------------------------------------------------------------

## 45. Drift Remediation

Drift SHALL NOT be automatically "fixed" by blind Production apply.

The operator SHALL determine whether:

-   Terraform source is correct;
-   manual change must be reverted;
-   source must be updated;
-   another controller owns the resource.

Automated remediation MAY be introduced only for proven safe cases.

------------------------------------------------------------------------

## 46. Control Plane Boundary

`baobab-cp` MAY reconcile approved tenant-level desired state through
scoped provisioning mechanisms.

It SHALL NOT bypass infrastructure governance by receiving unrestricted
Terraform or AWS administrator access.

Dynamic tenant/application configuration and physical infrastructure
changes SHALL remain distinguishable.

------------------------------------------------------------------------

## 47. APISIX Dynamic Configuration

Routine tenant/application gateway configuration MAY be reconciled
dynamically through the approved APISIX management boundary.

Terraform SHALL manage:

-   APISIX infrastructure;
-   baseline security;
-   network;
-   management access;
-   foundational configuration.

Terraform need not own every routine dynamic route.

------------------------------------------------------------------------

## 48. Infrastructure Change Classes

Changes SHOULD be classified by risk.

  -----------------------------------------------------------------------
  Class                               Example
  ----------------------------------- -----------------------------------
  **Low**                             documentation, non-functional
                                      metadata

  **Moderate**                        bounded stateless resource/config
                                      change

  **High**                            network/IAM/gateway/compute
                                      topology

  **Critical**                        stateful replacement, KMS, state
                                      backend, Production data path
  -----------------------------------------------------------------------

Higher-risk changes SHOULD require stronger validation and approval.

------------------------------------------------------------------------

## 49. Change Windows

High-risk Production changes MAY use controlled change windows where
operational coverage is available.

A change window SHALL not justify skipping automated validation.

Routine safe changes SHOULD not require artificial bureaucracy merely
because they touch infrastructure.

------------------------------------------------------------------------

## 50. Pre-Change Checklist

Critical changes SHOULD confirm:

-   accepted ADR alignment;
-   plan reviewed;
-   backups/recovery point where appropriate;
-   rollback path;
-   monitoring active;
-   owner available;
-   dependency impact understood;
-   customer/business timing considered.

------------------------------------------------------------------------

## 51. Post-Apply Verification

A successful `terraform apply` is not the end of deployment.

Post-apply verification SHALL check relevant outcomes:

``` text
Infrastructure Created
        │
        ▼
Health Checks
        │
        ▼
Security / Network Verification
        │
        ▼
Service/Synthetic Verification
        │
        ▼
Operational Evidence
```

The exact checks depend on the changed stack.

------------------------------------------------------------------------

## 52. Failed Apply

A failed Terraform apply SHALL trigger controlled diagnosis.

Operators SHALL:

1.  stop conflicting applies;
2.  inspect state and partial changes;
3.  determine whether retry is safe;
4.  avoid manual state edits unless necessary and reviewed;
5.  recover/rollback according to resource semantics;
6.  document the incident where material.

Repeatedly rerunning apply without understanding partial state is
prohibited.

------------------------------------------------------------------------

## 53. Rollback

Infrastructure rollback is not always equivalent to reverting Git.

Some resources cannot safely be "rolled back" automatically.

Rollback planning SHALL distinguish:

-   reversible configuration;
-   replaceable stateless resources;
-   stateful migrations;
-   destructive changes;
-   irreversible external effects.

ADR-Infra-0022 defines detailed rollback/database-change safety.

------------------------------------------------------------------------

## 54. Emergency Change

Emergency Production changes MAY bypass normal timing, but SHALL NOT
bypass accountability.

An emergency change SHALL require:

-   declared incident/emergency;
-   authorised operator;
-   least-privilege/break-glass access;
-   audit trail;
-   immediate verification;
-   follow-up PR/reconciliation;
-   post-incident review where material.

------------------------------------------------------------------------

## 55. Break-Glass

Break-glass access SHALL follow ADR-Infra-0013.

It SHALL be:

-   exceptional;
-   MFA/federation protected where applicable;
-   time-bounded where possible;
-   logged;
-   reviewed after use.

Break-glass credentials SHALL not become normal CI credentials.

------------------------------------------------------------------------

## 56. Audit Evidence

For material Production changes, the platform SHOULD be able to
reconstruct:

``` text
Who proposed?
What changed?
What plan was reviewed?
Who approved?
What identity applied?
When?
What revision?
What resources changed?
Did verification pass?
```

GitHub, CloudTrail, Terraform and deployment telemetry SHALL
collectively provide this evidence.

------------------------------------------------------------------------

## 57. Change Traceability

Infrastructure changes SHOULD correlate:

``` text
Git Commit / PR
      │
      ▼
Workflow Run
      │
      ▼
Terraform Plan
      │
      ▼
AWS Role Session
      │
      ▼
CloudTrail Changes
```

This traceability is part of Production governance.

------------------------------------------------------------------------

## 58. Production Freeze

A temporary Production change freeze MAY be declared during:

-   major incident;
-   unstable error budget;
-   critical business period;
-   recovery operation;
-   major security event.

Emergency corrective changes remain possible through authorised
procedure.

------------------------------------------------------------------------

## 59. Repository Documentation

Every new infrastructure stack/module SHOULD include sufficient
documentation for:

-   purpose;
-   inputs;
-   outputs;
-   ownership;
-   environment usage;
-   security implications;
-   recovery implications.

Code alone SHALL not be considered adequate operational documentation
for critical infrastructure.

------------------------------------------------------------------------

## 60. ADR Compliance

Implementation SHALL consult accepted ADRs before introducing
infrastructure behaviour.

Where an implementation requires a material architectural departure:

``` text
Accepted ADR
     │
     ▼
Conflict Identified
     │
     ▼
New/Superseding ADR
     │
     ▼
Implementation
```

Code SHALL NOT silently override accepted architecture.

------------------------------------------------------------------------

## 61. ZuriBeans Go-Live

ZuriBeans SHALL validate the complete infrastructure change-governance
path before Production.

At minimum:

-   infrastructure PR checks pass;
-   Terraform plan is reviewable;
-   Production apply uses OIDC;
-   Production environment is protected;
-   no long-lived AWS keys are required;
-   immutable application digests are used;
-   post-deployment verification runs;
-   deployment is traceable to PR/commit;
-   emergency/rollback procedures exist.

------------------------------------------------------------------------

## 62. Production Verification

Before Production readiness, verify:

-   `main` is protected;
-   required checks are enforced;
-   CODEOWNERS covers sensitive paths;
-   Terraform fmt/validate run;
-   linting is present;
-   IaC security scanning is present;
-   policy-as-code enforces critical ADR invariants;
-   contract verification runs;
-   plans are generated and reviewable;
-   PR workflows cannot mutate Production;
-   GitHub Actions uses OIDC;
-   plan/apply permissions are appropriately separated;
-   Production uses protected environment approval;
-   workflow permissions are minimal;
-   actions/workflows are pinned;
-   Terraform/providers are version-constrained;
-   state locking and workflow concurrency work;
-   drift detection runs;
-   destructive changes receive protection;
-   CI does not expose secrets;
-   post-apply verification exists;
-   audit evidence is recoverable;
-   emergency change procedure is documented.

------------------------------------------------------------------------

## 63. Rejected Alternatives

  -------------------------------------------------------------------------
  Alternative             Decision                Reason
  ----------------------- ----------------------- -------------------------
  Production apply from   Rejected                Privilege/supply-chain
  untrusted PR                                    risk

  Long-lived AWS CI keys  Rejected                OIDC provides safer
                                                  temporary identity

  Direct push to          Rejected                Bypasses review
  Production branch                               

  Console changes as      Rejected                Creates
  normal workflow                                 drift/non-repeatability

  Terraform apply without Rejected                Removes reviewable change
  plan                                            intent

  Review source but       Rejected                Actual resource effects
  ignore plan                                     may differ

  One universal admin CI  Rejected                Excessive privilege
  role                                            

  Unpinned third-party    Rejected                Supply-chain risk
  Actions                                         

  Mutable provider/tool   Rejected                Non-deterministic changes
  versions                                        

  Automatic blind drift   Rejected                Could destroy intentional
  remediation                                     state

  Secret-bearing plan in  Rejected                Data exposure
  public artifact                                 

  Terraform manages       Rejected                Ownership/safety boundary
  application schema                              
  implicitly                                      

  Emergency change        Rejected                Permanent drift
  without reconciliation                          

  Apply success =         Rejected                Requires operational
  deployment success                              verification

  Code silently overrides Rejected                Governance failure
  accepted ADR                                    
  -------------------------------------------------------------------------

------------------------------------------------------------------------

## 64. Consequences

### Positive

-   Production infrastructure changes become reviewable and auditable.
-   Untrusted PRs cannot mutate Production.
-   OIDC removes routine long-lived AWS keys.
-   Plans become first-class review evidence.
-   Drift becomes detectable.
-   Shared workflows reduce governance duplication.
-   Supply-chain controls improve.
-   Emergency changes remain possible without becoming normal practice.
-   ZuriBeans go-live uses the same disciplined deployment path future
    tenants will use.

### Costs

-   CI becomes more sophisticated.
-   Plans/security scans/policy checks increase workflow duration.
-   Protected Production deployment requires explicit operational
    ownership.
-   False-positive security/policy rules require maintenance.
-   Drift detection and audit evidence add operational work.
-   High-risk changes require more deliberate review.

These costs are accepted.

------------------------------------------------------------------------

## 65. Decision Rules

> **Infrastructure changes SHALL normally originate from reviewed,
> version-controlled pull requests.**

> **Untrusted pull requests SHALL NOT mutate Production or receive
> Production secrets/credentials.**

> **Terraform changes SHALL be formatted, validated, security-scanned,
> policy-checked and planned before Production apply.**

> **Reviewers SHALL examine the Terraform plan for material Production
> changes.**

> **Production apply SHALL occur through a protected post-merge
> deployment path.**

> **GitHub Actions SHALL use OIDC and temporary AWS roles rather than
> normal long-lived AWS access keys.**

> **Plan and apply permissions SHOULD be separated.**

> **Production workflows SHALL use least GitHub and AWS privilege.**

> **Third-party Actions and security-sensitive reusable workflows SHOULD
> use immutable governed references.**

> **Terraform state locking and workflow concurrency SHALL both protect
> apply execution.**

> **Production drift SHALL be detected and investigated rather than
> blindly remediated.**

> **A successful Terraform apply SHALL be followed by operational
> verification.**

> **Emergency changes SHALL remain authorised, auditable and reconciled
> back into source control.**

> **Accepted ADRs SHALL remain the architectural source of truth;
> implementation SHALL NOT silently contradict them.**

------------------------------------------------------------------------

## 66. Implementation Implications

The repository SHALL evolve toward a pipeline resembling:

``` text
Pull Request
│
├── repository/contract checks
├── terraform fmt
├── terraform validate
├── lint
├── security scan
├── policy-as-code
└── terraform plan
        │
        ▼
     Review
        │
        ▼
      Merge
        │
        ▼
Protected Environment
        │
        ▼
    GitHub OIDC
        │
        ▼
    Terraform Apply
        │
        ▼
Post-Apply Verification
        │
        ▼
Audit / Deployment Evidence
```

Likely repository additions include:

``` text
.github/workflows/
├── terraform-pr.yml
├── terraform-deploy.yml
├── terraform-drift.yml
└── security-policy.yml

deploy/
├── policies/
├── verification/
└── scripts/

docs/runbooks/
├── failed-apply.md
├── drift-response.md
├── emergency-change.md
└── production-deployment.md
```

Exact filenames are implementation details and MAY differ.

------------------------------------------------------------------------

## 67. Follow-on Decision

The next ADR SHALL be:

**ADR-Infra-0021 --- Application Deployment, Promotion and Release
Manifests**

It shall define:

-   the contract between application repositories and infrastructure;
-   immutable image digest deployment;
-   release manifests;
-   environment promotion;
-   artifact verification;
-   configuration references;
-   database migration coordination;
-   ECS task-definition rendering;
-   deployment provenance;
-   ZuriBeans release composition;
-   multi-repository release coordination;
-   and how infrastructure deploys approved artifacts without rebuilding
    application source.
