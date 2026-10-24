# DEV-01 — reusable ordinary-development lifecycle

This is the ADR-SHARED-043 development path. It does not call the optional
Infrastructure #49 packet, change historical INT-02/INT-03 locks or accept a
protected environment. Only the explicit `development` environment can prepare,
start or test it. Cleanup remains available after expiry and on host recovery.

The built-in `iam-cp-development` adapter runs six private services: native
Keycloak, its PostgreSQL, CP, its marked PostgreSQL, a TLS edge and an actual
probe. It imports the exact IAM-owned realm, creates and reads back two native
synthetic user subjects, then invokes CP's separately built development command.
CP alone migrates and creates canonical state for the five closed profiles.
Other engines remain NOT_STARTED; seeded PROVISIONING/UNKNOWN instances are not
certified providers. No CMS dependency or new DEV-14 descriptor is introduced.

## Same commands in a dedicated Codespace and Actions

Open the existing `.devcontainer/platform-integration/devcontainer.json` lab
(4 CPUs, 16 GiB memory recommended). The Actions job uses that same container,
locked Dev Containers CLI and Python entrypoint. The ordinary default Codespace
stays lightweight; no fleet-wide toolchain or pnpm upgrade is required.

```sh
python3 -B tests/platform-integration/l4.py plan development --static
python3 -B tests/platform-integration/l4.py doctor development
export BAOBAB_ENVIRONMENT=development
python3 -B tests/platform-integration/l4.py run development

# Or operate phases explicitly. The preparation output is a non-secret run ID.
RUN_ID=$(python3 -B tests/platform-integration/l4.py prepare development)
python3 -B tests/platform-integration/l4.py up development --run-id "$RUN_ID"
python3 -B tests/platform-integration/l4.py test development --run-id "$RUN_ID"
python3 -B tests/platform-integration/l4.py down development --run-id "$RUN_ID"
python3 -B tests/platform-integration/l4.py evidence development --run-id "$RUN_ID"

# Expired owned runs, or explicitly all runs owned by this checkout and UID:
python3 -B tests/platform-integration/l4.py recover development
python3 -B tests/platform-integration/l4.py recover development --all
```

Plan lists exact source/image pins and the minimal service graph. Doctor checks
Docker/Compose, Git and OpenSSL; start resolves the public source/image supply
chain and verifies CP's embedded development/identity contracts against pinned
Shared. This profile consumes no private npm packages or GHCR service image;
registry/package checks for later engine adapters belong to those adapters.
Missing tools, access, digest, contract or source freshness fail explicitly.

Run source must be a clean exact Git revision. Update `lock.json` through a
reviewed PR, not an environment override. Provider containers come from pinned
base digests; actual source-built IAM/CP image IDs are recorded and compared to
running containers. The Keycloak adapter proves native provider setup only;
it does not exercise Baobab's evidence bridge, Ory issuance or federation.

## Recovery and evidence

One private `0700` directory and durable `0600` run record precede every external
mutation. Atomic fsynced checkpoints, per-run file locks, owned Docker labels and
a separate deadline watcher bound each run to at most one hour. Shorter native
CP leases apply within that absolute deadline. No public/admin host ports are
published; all runtime networking is internal. Per-run random credentials,
source clones and TLS material are removed with the owning directory.

On ordinary failures `run` tears down in `finally`; startup failure also tears
down. A killed command leaves create-before-mutate state for retryable cleanup.
`recover` discovers labelled orphan resources even if the Compose/env file or
state was lost. It never deletes another checkout/user's resources. Surviving
resources or Docker failures retain the cleanup handle and refuse success.
The separate watcher retries cleanup on deadline; loss of the entire host or
watcher requires the next host startup's `recover` or CI's always-run host step.
This is recoverable local development, not a promise of survival across host loss.

Only sanitized receipts and hashes in `evidence/dev01-*/completed` are uploaded.
No private state, credentials, subjects, DSNs, raw subprocess logs or bootstrap
document is an artifact. The lifecycle receipt can pass only after actual probes,
bootstrap replay, image/network checks and independently queried empty teardown.
Source tests remain SOURCE. Seven-case INT-03C and fourteen-case NAB-03 acceptance
are always false here; those require DEV-03/04/05's actual auth/domain assertions.

`development/ci.py` additionally drills interrupted startup with an actual owned
volume, failed health followed by restoration/retest, loss of Compose state and
expired orphan discovery. Its real-component result is scoped to DEV-01 only.
An Actions receipt is not an independently observed interactive Codespaces run.

Rollback: recover owned runs, restore the preceding reviewed profile/source
pins and disable this adapter. Do not alter frozen receipts, borrow protected
credentials, write CP canonical SQL or restore a general human approval hold.
