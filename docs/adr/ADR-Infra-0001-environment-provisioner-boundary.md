# ADR-Infra-0001: Establish a separate environment provisioner

- **Status:** Accepted
- **Date:** 2026-08-31
- **Decision owners:** Nabhold platform architecture

## Context

The original Baobab scaffold embedded Compose, AWS, Terraform, Kubernetes, and
monitoring placeholders beside application code. That arrangement makes
application releases responsible for underlying environment orchestration and
weakens permission boundaries.

## Decision

`nabhold/infrastructure` is the sole repository for declarative environment
provisioning and deployment automation. `nabhold/baobab-cp` expresses and
reconciles approved tenant-level desired state through scoped service APIs; it
does not own Terraform, clusters, networks, or server deployment.

Local development begins with Docker Compose. AWS Cape Town (`af-south-1`) is
the first production region and Terraform is the production IaC tool.
Kubernetes/Helm is deferred. Infrastructure declarations conform to released
contracts from `nabhold/shared`.

## Consequences

- Infrastructure changes receive independent review and deployment authority.
- Application repositories can be tested without cloud credentials.
- Environment promotion is explicit and auditable.
- Existing embedded infrastructure placeholders in `baobab-cp` require a
  controlled disposition change.
- Cross-repository releases require versioned contracts rather than copied
  configuration.
