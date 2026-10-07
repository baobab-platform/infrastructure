# Reviewed staging release declarations

Add an account-specific `*.tfvars.json` only after immutable app/helper artifacts,
protected bundles, database bootstrap and private PKI are prepared. The manual
release workflow reads declarations from this directory on main.

The synthetic fixture in `terraform/environments/staging/tests/` exercises plans.
It is not a deployable release: its account, digests, certificates and commands
are deliberately test values.

A declaration has `workload_release`, `activate_workloads` (false first), and
`etcd_security_group_id`. The typed Terraform variable is the executable local
input contract; it is not a new canonical Shared release schema. Canonical
provider identity and runtime profile contracts remain owned by Shared/CP.

Coordinated P-CAP-08 cuts include Pulse as a required component and runtime service. Its release entry pins the promoted Pulse image/source revision; certification, EngineRelease approval, provider activation, bindings and grants remain Control Plane governance rather than Terraform state.

## First reviewed selection

`v0.1.0-staging.coordination.json` now selects all five published components.
Receipts, SBOMs and a dated verification snapshot are retained under
`evidence/v0.1.0-staging/`. There is no deployable account manifest or created
Infrastructure tag for this candidate. See
[the P-CAP-08 closure runbook](../../../docs/runbooks/p-cap-08-first-coordinated-release.md)
for verification, missing inputs and the governed execution sequence.
