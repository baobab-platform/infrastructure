# Nabhold Infrastructure

`nabhold/infrastructure` is the environment provisioner for the Nabhold
platform. It owns declarative infrastructure and deployment automation; it does
not own tenant-management business logic or canonical cross-repository
contracts.

## Accepted ADR-SHARED-036 / EA v2.2 integration

The Infrastructure-owned INT-01 [Codespaces/Actions L4 runbook](tests/platform-integration/README.md)
defines an isolated Compose foundation, immutable image/source lock, no-public-port
service topology and identical Python lifecycle commands for Codespaces and CI.
No source-only run qualifies IAM/CP integration, protected staging or production.

The [Nabhold v2.0 critical-path audit and implementation queue](docs/testing/nabhold-go-live-audit-2026-10-16.md)
tracks the current INT-02 blocker, cross-repository PR dependencies and exact
merge conditions. [INT-02's workload proof](tests/platform-integration/int02/README.md)
now isolates same-client audience denial and client issuance revocation;
remaining mandatory live scenarios still gate PR #35.

## Foundation status

Foundation 0 established the architecture and trust boundaries. Foundation 1
adds the local Docker Compose topology under `compose/`; it remains development
infrastructure and is not a production deployment template.

Start with the [local platform runbook](docs/runbooks/local-platform.md).

Integrated testing strategy and engine→dependency topology live under
[docs/testing/](docs/testing/).

## Ownership

This repository will contain:

- Docker Compose for local platform dependencies;
- Terraform modules and environment compositions for AWS;
- APISIX platform configuration and bootstrap policy;
- RabbitMQ, PostgreSQL, and Redis deployment configuration;
- Kubernetes/Helm definitions when their adoption is approved;
- observability and backup configuration;
- environment deployment workflows and runbooks;
- platform-level dependency smoke and (later) critical-path harness docs/jobs.

It must not contain:

- Baobab control-plane API or worker code;
- digital-estate application code;
- canonical API, event, or domain schemas;
- plaintext secrets or tenant credentials;
- deployment logic copied into application repositories.

## Contract dependencies

Environment declarations conform to
`baobab-platform/shared/contracts/infrastructure/v1/environment-topology.schema.json`.
The control-plane runtime in `nabhold/baobab-cp` interacts with provisioned
services through narrowly scoped APIs and workload identities.

## Planned layout

```text
compose/                 Local development topology
terraform/
  modules/               Reusable infrastructure modules
  environments/          Reviewed environment compositions
apisix/                  Gateway bootstrap and platform policy
observability/           OpenTelemetry and metrics configuration
deploy/                  Deployment workflows and scripts
docs/adr/                Infrastructure decisions
docs/architecture/       Environment topology
docs/runbooks/           Operational procedures
docs/testing/            Integrated testing strategy and topology
```

## Initial platform services

<!-- markdownlint-disable MD013 -->

| Service | Purpose | Source of truth |
| --- | --- | --- |
| Apache APISIX | Ingress, routing, and gateway policy | APISIX configuration reconciled by `baobab-cp` |
| PostgreSQL 17 | Control-plane metadata and approved tenant database boundaries | PostgreSQL desired state in `baobab-cp` |
| RabbitMQ | Commands and lifecycle events with DLQs | Versioned AsyncAPI contracts in `shared` |
| Redis 7 | Rebuildable route and status projections | PostgreSQL remains authoritative |
| OpenTelemetry Collector | Vendor-neutral telemetry pipeline | Environment configuration in this repository |

<!-- markdownlint-enable MD013 -->

Production is targeted at AWS Cape Town (`af-south-1`) through Terraform.
Kubernetes, Helm, and Temporal are deliberately deferred until operational need
justifies their additional machinery.

## Local commands

```bash
make local-env      # copy compose/.env.example → compose/.env
make local-up       # start dependency stack
make local-verify   # config + up + smoke (APISIX, RabbitMQ, OTEL)
make local-down     # stop containers (volumes retained)
```

CI uses the same smoke path with deterministic placeholders via the
Infrastructure CI workflow.

## Foundation 4

Codespaces uses `ghcr.io/baobab-platform/baobab-dev:1.4.4-infra` -- the lean
`infra` profile (Terraform + AWS CLI only, no Python/Node/Flutter/Java),
not the `full` profile this repo carried before. The SHA-pinned
`foundation` workflow validates the development contract and reproducibility,
then scans dependencies, configuration, secrets, and applicable containers.
Protect `main` with pull requests, CODEOWNER review, and required CI checks.

### INT-02 closure candidate — 16 October 2026

[The closure register](docs/testing/int02-closure-2026-10-16.md) tracks the
real browser/code/S256/MFA ceremony, governed PRIMARY runtime guard,
four-principal isolation and exact workload-registry enforcement. The dependency pins include CP #407/#408 and Shared #322; the current IAM pin tests the unmerged #118 browser-hierarchy repair on top of merged #117.
no protected acceptance follows from those source merges. Provider qualification remains
independently mandatory and the complete profile stays blocked until proven.
