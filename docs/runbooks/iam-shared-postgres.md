# Preparing IAM shared federation storage

The staging root accepts `iam_shared_postgres = true` as an explicit reviewed
release input. It adds a separate IAM PostgreSQL 17 database named `federation`,
with private data subnets, forced TLS, an IAM-only SG pair, Multi-AZ storage,
encryption, managed bootstrap credentials, seven-day backups and deletion
protection. It inherits the approved release's engine version and instance class.
The default remains false; foundation-only operation still creates no database.

Enabling the database does not import bbolt files, change IAM's storage backend,
raise the task count or establish operational acceptance. Account for one extra
RDS instance and its backup/storage cost in the reviewed plan. CP and Keycloak
credentials/databases must not be reused for IAM state.

After provisioning, a separate migration administrator applies IAM's shared
storage schema, provisions a namespace/recovery epoch and creates the restricted
runtime database role. Application task roles do not receive the managed master
secret. Deliver the runtime DSN through IAM's version-pinned protected file
bundle, for example `database-dsn.txt`, and include the verified RDS CA file in
that reviewed bundle. Use `sslmode=verify-full` and the exact database endpoint.

Set IAM service `Storage` to the protected `DSNFile`, `Namespace` and externally
pinned `RecoveryEpoch`. Follow baobab-iam's
`docs/operations/federation-shared-storage.md` for grants, backup/recovery and
revocation reconciliation. Make an explicit reconciled cutover; do not activate
local files and PostgreSQL independently for the same live binding. Retain the
single-replica staging deployment until shared-state behavior, failure recovery
and dependency readiness are exercised in the real account.

Terraform mocked plans prove the optional database shape and IAM-only network
edge. They do not prove migrations, TLS negotiation, credentials, replication
loss bounds, failover, backup encryption/immutability or live recovery.
