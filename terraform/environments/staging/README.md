# AWS Staging — MP2-C foundation

This root module is the first production-shaped Baobab Staging slice in
`af-south-1`. It implements the infrastructure boundary needed to move IAM
ADR-IAM-0033 MP2-C from fixture/runtime-plumbing proof to deployed authority
integration.

## Scope

The foundation creates:

- a staging-only VPC with separate ingress, application and data subnets in two
  availability zones;
- one controlled NAT egress path for federation/provider traffic;
- private AWS API endpoints used by ECS, Secrets Manager, ECR, KMS and SSM;
- source-identity security groups for APISIX, Control Plane, IAM and retained
  Keycloak;
- an ECS/Fargate cluster with ECS Exec enabled;
- private AWS Cloud Map DNS;
- an encrypted, access-point-scoped EFS filesystem for IAM approval/replay
  ledgers.

The EFS ledger is deliberately a **single-writer staging proof boundary**. It
does not satisfy ADR-IAM-0033's later multi-replica fencing/restore requirement.

## State

The backend is intentionally empty in source. Initialise with reviewed,
environment-specific backend arguments; do not commit account IDs, state bucket
names or credentials.

Example:

```sh
terraform init \
  -backend-config="bucket=<staging-state-bucket>" \
  -backend-config="key=baobab/staging/foundation.tfstate" \
  -backend-config="region=af-south-1" \
  -backend-config="dynamodb_table=<staging-lock-table>" \
  -backend-config="encrypt=true"
```

GitHub Actions must assume the staging plan/apply roles through OIDC. Long-lived
AWS access keys are not an accepted deployment path.

## Deliberate exclusions

This foundation does not yet create public DNS/certificates, ALBs, APISIX/etcd,
RDS, CP/IAM/Keycloak ECS services or dynamic gateway routes. Those depend on
immutable application image digests and certificate/secret references and are
layered in the MP2-C workload release increment.

No resource in this stack grants public access to CP, IAM, Keycloak
administration, EFS or a database.
