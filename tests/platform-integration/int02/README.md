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

The real issuer's readiness is its master-realm OIDC discovery document, fetched over verified TLS through
the edge, not the nonexistent `kc.sh health` command. An ACTIVE synthetic
capability-binding row is **not** live provider health/certification; CP-02
remains BLOCKED until a real provider and current evidence are demonstrated.
Receipts record the candidate harness Git SHA as distinct from dependency pins.

### Audit note (15 October 2026, EA v2.2 conformance)

- **Startup:** a literal `\n` inside a YAML comment had swallowed `KC_DB_PASSWORD`, so Keycloak started without
  database credentials and exited (live job: `keycloak=exited`). The static test now parses the keycloak environment
  structurally and rejects literal `\n`.
- **L4-CP-01** is PASS only with its positive and every matrix negative from the same run. The negatives are:
  - a swapped Organisation;
  - a fabricated tenant;
  - an unmapped principal: a valid workload token, before the harness links its Keycloak subject, with no tenant
    authority. CP auto-provisions workload principals on first context resolution (ADR-0004 §13, ADR-0007 §46), so
    the harness reuses that link rather than duplicating it, and records `cp_workload_principal_auto_provisioned`;
  - a revoked identity, using a token issued before the revocation.

  A denial means HTTP 401/403 only; a 404, a 5xx or a transport error is never counted.
- **L4-CP-03** covers only the sibling case here; the parent, independently governed subsidiary and external cases are
  not exercised. A sibling denial is recorded in `checks`, but CP-03 stays BLOCKED. Revocation no longer promotes it.
- **Receipt (EA v2.2 §4.4)** now records:
  - the built image IDs and runtime pins;
  - the executing profile and its resource requirements;
  - real versus simulated components and the provider classification;
  - named positive and negative checks;
  - the transport;
  - an evidence digest.
- **Transport:** the matrix requires INT-02 "over verified local TLS". Every hop that crosses the Compose network now
  reaches Keycloak and CP through a digest-pinned nginx TLS 1.3 edge (`edge.conf`), as `iam.int02.test` and
  `cp.int02.test`:
  - `materialise` generates a one-day throwaway CA and edge certificate for that run only. The CA key is destroyed as
    soon as the edge certificate is signed, so no container can read it.
  - The issuer is `https://iam.int02.test/realms/baobab`. CP at the pin refuses any non-loopback HTTP issuer, which is
    why the plain-HTTP profile's CP exited at startup. CP trusts only the run CA (`SSL_CERT_FILE`).
  - The probe verifies against the run CA with hostname checking and TLS 1.3 minimum.
  - Acceptance requires three checks, all observed in the same run: IAM over verified TLS, CP over verified TLS, and
    the same endpoint refused without the run CA.
  - Keycloak's in-container kcadm administration stays on loopback HTTP, and the edge-to-upstream hop is HTTP on the
    internal network. The receipt records both.

### Codespaces and CI parity, and testing a CP or IAM change without staging

ADR-SHARED-036 §6.3 requires one harness and identical entrypoints on Codespaces and Actions; §6.8 and §6.10
require a CP or IAM pull request to run the affected L4 profile against its own head. This profile does both.

- **One executor.** The Actions live job runs `run-in-devcontainer.sh` inside
  `.devcontainer/platform-integration` through `devcontainers/ci` (pinned by commit). A developer runs the same script,
  or the same six commands, in the integration Codespace. Both use one image, one toolchain and one teardown.
- **docker-outside-of-docker.** In that devcontainer the Docker daemon runs on the host and resolves bind-mount
  sources against the host filesystem, where the workspace lives at another path. The devcontainer passes
  `LOCAL_WORKSPACE_FOLDER` and `CONTAINER_WORKSPACE_FOLDER` through `remoteEnv`, and `host_path()` translates only the
  four mount sources (runtime, TLS, probe source, edge config); build contexts stay container paths. `up` proves the
  daemon can read a per-run sentinel through a real bind mount before starting anything, and otherwise fails closed
  with the reason. On a plain runner neither variable is set and nothing is translated.
- **Machine size.** `hostRequirements` asks Codespaces for 4 CPUs and 16 GB, at least the lock's minimum, so preflight
  is not starved on the default machine.
- **A CP or IAM pull request.** Call the reusable workflow, pinned to an Infrastructure commit, and pass the
  candidate head. Exactly one of `baobab-cp` or `baobab-iam` may be replaced, only by a full commit SHA. Inputs are
  validated and reach scripts only through the environment. The receipt records the materialised pins, the lock
  pins and the candidate. No secret is passed; every credential is generated per run and destroyed.

  ```yaml
  jobs:
    int02:
      uses: baobab-platform/infrastructure/.github/workflows/platform-int02.yml@<infrastructure-sha>
      with:
        harness_sha: <the same infrastructure-sha>
        candidate_repository: baobab-cp
        candidate_sha: ${{ github.event.pull_request.head.sha }}
  ```

This is real-component evidence on synthetic data. It never substitutes for protected staging, and a BLOCKED
scenario is never a pass.
