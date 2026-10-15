# INT-02 — Real IAM and Control Plane integration candidate

**Authority:** Accepted ADR-SHARED-036 and EA Implementation Plan v2.2.

**Status:** CANDIDATE / NOT ACCEPTED. No source-only green build or isolated
token issuance is a complete L4-01 acceptance. The live suite must execute
every mandatory scenario with actual Keycloak and CP processes before merge.

The optional Codespaces integration configuration and GitHub Actions run the
same commands with `iam-cp` as profile:

```sh
python3 tests/platform-integration/l4.py preflight iam-cp --static
python3 tests/platform-integration/l4.py materialise iam-cp
python3 tests/platform-integration/l4.py up iam-cp
python3 tests/platform-integration/l4.py test iam-cp
python3 tests/platform-integration/l4.py evidence iam-cp
python3 tests/platform-integration/l4.py down iam-cp
```

Required 4 CPUs, 8 GiB memory, Docker Compose and public GitHub read-only
cloning of exact pinned source commits. Runtime source builds use real
Keycloak and CP; network is internal and database/credential volumes are
disposable. Tests are restricted to synthetic identities and companies.
Every result is compared with the Shared L4 matrix. There are no
production secrets, external legal proofs, or protected staging permissions.

**Important outstanding proof work**: same-client audience-only denial
L4-IAM-02, real human code+PKCE L4-IAM-01, CP-side immediate revocation
and complete positive current provider-binding/health proof must be
demonstrated before replacing BLOCKED statuses with PASS. A tenant-neutral
IAM workload can request the context of a second active tenant; that does
not imply a grant and must be tested through an independent CP capability
denial. A CP canonical identity revocation is distinct from IdP token
revocation; the latter may be delayed for locally verified JWTs.

Maintain cross-repo source pins explicitly as IAM/CP develop concurrently.
Nothing here should be promoted into staging or production.

### Audit note (15 October 2026)

The real issuer's readiness is probed via the private Keycloak management HTTP
endpoint, not the nonexistent `kc.sh health` command. An ACTIVE synthetic
capability-binding row is **not** live provider health/certification; CP-02
remains BLOCKED until a real provider and current evidence are demonstrated.
Receipts record the candidate harness Git SHA as distinct from dependency pins.
