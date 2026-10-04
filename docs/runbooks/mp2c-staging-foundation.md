# MP2-C AWS staging foundation runbook

## Purpose

Provision the minimum production-shaped AWS boundary required for live
ADR-IAM-0033 MP2-C evidence. Local Docker Compose remains development/L3 test
infrastructure and must not be cited as staging acceptance.

## Preconditions

1. Use the dedicated Baobab staging AWS account/boundary in `af-south-1`.
2. Configure separate GitHub OIDC roles for Terraform plan and apply.
3. Configure encrypted remote state and locking for staging.
4. Protect the GitHub `staging` environment before enabling apply.
5. Do not place AWS access keys, database passwords, Keycloak bootstrap secrets,
   authority bearer tokens or private keys in GitHub source or Terraform input
   values.

## Network contract

```text
Internet
   |
   v
public ALB (later)
   |
   v
private APISIX
   |
   +------> CP
   +------> IAM/browser endpoints
   +------> Keycloak federation endpoints

IAM ---- private authenticated TLS ----> CP authority
IAM ---- private authenticated TLS ----> Keycloak/provider management

Operator -- AWS IAM/MFA --> ECS Exec --> private task

CP / IAM / Keycloak ---- explicit SG rules ----> private data services
```

The public and management planes must not be collapsed. The APISIX Admin API,
Keycloak administration and `/internal/federation/v1/*` authority operations
remain private.

## ECS Exec boundary

ECS Exec is for controlled diagnosis and break-glass operations, not routine
deployment or configuration. Operators need explicit IAM permission and the
session is auditable through AWS control-plane records. No inbound SSH rule or
bastion is created.

The cluster requests ECS Exec session encryption with a dedicated KMS key and
CloudWatch transcript logging. Runtime images still need the utilities required
by ECS Exec for full transcript capture; absence of such utilities does not
justify adding a broad shell/toolchain to hardened runtime images.

## IAM ledger durability

The #66 bbolt approval/replay stores cannot live on Fargate ephemeral storage.
Staging mounts the encrypted EFS access point at the IAM ledger path and runs one
writer. This provides task-replacement durability for staging evidence but does
not constitute the multi-replica fencing and restore proof required for
production.

## Verification

Before layering workloads:

- `terraform fmt -check -recursive terraform/environments/staging`;
- `terraform init -backend=false` and `terraform validate`;
- verify no application/data subnet assigns public IPs;
- verify data subnets have no default Internet route;
- verify the public ALB SG is the only SG with Internet ingress;
- verify EFS accepts NFS only from the IAM SG;
- verify Cloud Map is a private DNS namespace;
- verify ECS Exec is enabled with bounded operational logging;
- preserve the Terraform plan and workflow/commit identity as staging evidence.

A successful Terraform apply alone is not an MP2-C acceptance result.
