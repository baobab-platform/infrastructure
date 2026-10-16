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
- **L4-CP-01** is PASS only with its positive and every matrix negative from the same run (`CP01_REQUIRED`). The
  positive is a Principal / PRIMARY Organisation / Tenant / **market** context read: tenant A participates in one
  synthetic ACTIVE market (registry entry activated by a checker other than its maker, projected market row, ACTIVE
  assignment), and the context must carry its country and market. Without a market CP denies capability resolution
  with `RESIDENCY_POLICY_MISMATCH`, as it should. The negatives are:
  - a missing Organisation: a real tenant with no PRIMARY Organisation mapping. **Unresolved conflict:** the matrix
    says "denied", but Shared `control-plane/v1` makes the Organisation optional on `POST /platform-context/resolve`
    ("optionally attests an organisation the caller names"; an empty body is valid), and CP at the pin issues an
    Organisation-less RUNTIME context. The harness records the outcome (`DENIED`, `ISSUED_WITHOUT_ORGANISATION` or
    `FABRICATED`): an invented Organisation is FAIL, and CP-01 is PASS only when this is `DENIED`. Until the matrix and
    the contract agree, CP-01 stays BLOCKED;
  - a fabricated Organisation under the real tenant;
  - a swapped Organisation (tenant B's PRIMARY Organisation under tenant A) and a fabricated tenant;
  - an unmapped principal: a validly signed **human** token before its subject is linked, on the admin route. CP
    auto-provisions *workload* principals on first context resolution by design (ADR-0004 §13, ADR-0007 §46), so a
    workload cannot be unmapped there; its status is recorded as an observation, not counted;
  - a revoked grant: CP must refuse the same entitled context with `GRANT_REVOKED`;
  - a revoked identity, using a token issued before the revocation.

  A denial means HTTP 401/403 or the named CP decision only; a 404, a 5xx or a transport error is never counted.
- **L4-CP-02** is never PASS here: the provider is synthetic, never a current certified one. If CP resolves it, or
  refuses it as `UNAVAILABLE` for a health or provider reason (failing closed), the result is BLOCKED pending a live
  certified provider. A grant, binding, capability or contract fault is FAIL. The sibling's `GRANT_NOT_FOUND` is the
  matrix's "missing grant" negative.
- **Observations.** CP's fixed-vocabulary decisions, reason codes and HTTP statuses behind each check are recorded in
  the receipt and printed in the job log with the scenario states and checks.
- **L4-CP-03** covers only the sibling case here, and counts it only as a real differential (tenant A entitled,
  sibling B refused for `GRANT_NOT_FOUND`); the parent, independently governed subsidiary and external cases are
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

- **One executor.** The Actions live job builds `.devcontainer/platform-integration` and runs
  `run-in-devcontainer.sh` inside it with the Dev Containers CLI, the engine Codespaces uses. The CLI is installed from
  `devcontainer-cli/package-lock.json` (sha512 integrity, `npm ci --ignore-scripts`), not a third-party action, because
  the organisation baseline admits only trusted action owners. A developer runs the same script, or the same six
  commands, in the integration Codespace: one image, one toolchain, one teardown.
- **Image.** The devcontainer builds a digest-pinned Dockerfile that removes the base image's Yarn apt source. Its
  signing key is unavailable (`NO_PUBKEY 62D54FD4003F6525`), which made `apt-get update`, and so the
  docker-outside-of-docker feature, fail; the integration Codespace could not build either.
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

### 16 October 2026 — workload proof takeover

`workload-proof` isolates **L4-IAM-02** using the existing registered
`baobab-cms-workload` client. It observes a successful actual CP context read,
then temporarily changes only the disposable realm's `context:resolve`
audience mapper. The second real token must have the same issuer, subject,
client, actor and scope set, remain live according to IAM introspection, and
receive HTTP 401 from CP. An unavailable endpoint, expired token or changed
subject/scope is not accepted as audience evidence.

The probe restores the mapper in `finally`, independently disables that same
client and requires an OAuth denial of fresh token issuance, then restores the
client and observes successful issuance/CP resolution again. This proves
**client admission revocation**, not immediate invalidation of previously
issued self-contained JWTs. The existing canonical CP external-identity
revocation test separately exercises an already-issued token. All five named
workload checks must be actual booleans `true` from the same run; missing or
string-valued checks fail. No other scenario is promoted by this slice.

The mutations affect the throwaway integration realm only. The product IAM
repository, accepted registry, protected identities and source pins are
unchanged. A failed restoration aborts the run; teardown still destroys the
realm and credentials. HTTP responses, JWTs, secrets and Admin REST bodies are
never included in receipts. Regression tests use scripted responses and are
source evidence only; the real Actions job is required for acceptance.

References checked for this implementation:

- [Keycloak Admin REST API](https://www.keycloak.org/docs-api/latest/rest-api/index.html):
  client updates and client-scope protocol mapper updates (204 responses).
- [Keycloak OIDC endpoints](https://www.keycloak.org/securing-apps/oidc-layers):
  confidential-client token introspection.
- Pinned IAM `config/scopes/context-resolve.json` and
  `config/clients/baobab-cms-workload.json`; IAM's existing human audience
  differential validator; CP's current platform-context workload boundary.

**Merge remains blocked** until all mandatory real scenarios pass. Human
code/PKCE, the missing-Organisation matrix/contract discrepancy, live provider
health and the complete parent/subsidiary/sibling/external isolation matrix
remain independently required. See the [programme audit and ordered closure
plan](../../../docs/testing/nabhold-go-live-audit-2026-10-16.md).

The first real takeover run exposed Keycloak 26.7 introspection audience
validation: a confidential client cannot inspect a token that does not include
it in `aud`. The negative mapper therefore targets the existing disposable
`l4-int02-admin` audience and uses that client's credential for introspection.
The issuing workload/client, subject and scopes remain unchanged. No audience
check is disabled, no compatibility bypass is configured, and no new product
IAM audience is registered. Named safe boolean diagnostics distinguish claim
isolation, active introspection and subject matching if this proof fails again.
See [Keycloak's documented introspection audience validation](https://www.keycloak.org/docs/26.7.0/server_admin/index.html#_audience).

## Human code/S256 closure candidate (16 October 2026)

The `human/` component is an actual confidential relying party plus Chromium,
not an issuer or simulated callback. It runs on `human.int02.test` through the
same verified run CA. The disposable client disables direct/password grants,
requires S256 and registers exactly `/callback`. Chromium trusts the run CA
through its private NSS database; Node trusts it through `NODE_EXTRA_CA_CERTS`.
No `ignoreHTTPSErrors`, token-signing fixture or TLS bypass is used.

The browser completes real Keycloak login. The maintained `openid-client` and
`jose` libraries verify signatures and the retained nonce/state/verifier tuple.
The callback atomically consumes browser-bound state before exchange. Tests
repeat the same code, repeat the consumed browser state, and independently
exercise wrong verifier/nonce/state, unregistered callback, wrong signature,
issuer/audience expectations and expiry against real signed tokens. A positive
access token then reaches CP's independent canonical-identity/authority checks.
Only named booleans leave the private component; tokens remain in process
memory and disposable containers. No browser traces or storage snapshots are
published. Missing or failed sub-checks cannot promote L4-IAM-01.

Status: SOURCE CANDIDATE, awaiting the real final-head run. The other blocked
scenarios retain their own mandatory exits. Dependencies are npm-integrity
locked; browser revision comes from pinned Playwright. The Node base digest
was resolved from Docker Hub's OCI manifest, not inferred from a mutable tag.
