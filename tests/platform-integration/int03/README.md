# INT-03A — private Nabhold identity-smoke handoff

**State: INT-03A is merged source preparation. The INT-03B connected identity
runner is a new source increment pending actual CI/review. No connected PASS
or full INT-03 acceptance is claimed by this document.**
Authority: Accepted ADR-SHARED-036, EA v2.3 P0-A (retaining the v2.2 L4 matrix), Nabhold Go-Live
v2.0 P0-04/P0-06/P0-07, ADR-NAB-0004/0014 and IAM ADR-IAM-0033.

INT-02's merged Keycloak/CP/Pulse proof is recorded in Shared's
[qualification register](https://github.com/baobab-platform/shared/blob/main/docs/architecture/int02-pulse-qualification-register.md).
It does not establish the separate C4-03 protected Kratos/Hydra→CP journey,
C4-04B/C activation/consumption, Nabhold identity smoke, CMS or staging.

`handoff.py` prepares inputs for Nabhold's existing
`keycloak-identity-smoke` consumer. It generates a distinct random confidential
client secret, Redis password, AES key and recovery epoch for each bundle.
It never connects to IAM/CP, provisions a Principal, verifies a supplied UUID,
grants tenant access, activates a product client, starts services or emits a
PASS receipt. Expected Principal/source values are **unverified declarations**.
Its manifest explicitly withholds identity verification, runtime attestation,
protected staging and production authorisation.

## Prepare a bundle

Use a clean, reviewed IAM checkout including the Nabhold `basic` subject-scope
repair ([IAM #127](https://github.com/baobab-platform/baobab-iam/pull/127)). The
helper rejects the older template rather than silently fixing the owning
repository's profile. The product `nabhold-executive` client remains disabled.
The separate generated `nabhold-int03` fixture has no role mapper, optional
scope, service account, password grant or authentication-flow override. It
has only code/S256, the exact lab callback and CP human self-read defaults.

Create an **owner-private 0700 parent directory**, then a 0600 JSON input with
exactly these keys (placeholders intentionally cannot pass):

```json
{
  "synthetic": true,
  "sources": {
    "infrastructure": "ACTUAL_FULL_COMMIT",
    "baobab-iam": "ACTUAL_FULL_COMMIT",
    "baobab-cp": "ACTUAL_FULL_COMMIT",
    "shared": "ACTUAL_FULL_COMMIT",
    "nabhold": "ACTUAL_FULL_COMMIT"
  },
  "principal_id": "EXISTING_MAPPED_SYNTHETIC_CP_UUID",
  "username": "l4-int03-human",
  "password": "PRIVATE_DISPOSABLE_HUMAN_PASSWORD",
  "ca_file": "/absolute/path/to/disposable-lab-ca-bundle.pem"
}
```

The disposable non-admin human must be registered in the real issuer and
independently mapped to an ACTIVE CP human Principal. No real director, client,
enterprise records, production credentials or protected-staging identity may
be used. Protect all input/template/output parent paths from concurrent edits.
The CA bundle must contain only the disposable lab's public CA certificates;
never a signing key. Its PEM envelope is checked here; Nabhold additionally
checks X.509 CA extensions before launch. Only the real connection establishes
trust in the actual issuer, CP and Redis certificates.

```bash
python3 tests/platform-integration/int03/handoff.py \
  --inputs /absolute/private/int03-input.json \
  --iam-template /absolute/reviewed/iam/config/clients/nabhold-executive.json \
  --output /absolute/private/new-int03-run
```

Each new output contains one atomically published `prepared` directory:

| File | Use |
|---|---|
| `integration.env` | Nabhold's existing private dotenv handoff; do **not** shell source |
| `client.json` | Input for authorised provisioning of the disposable confidential client |
| `users.acl` | Hashed-password Redis ACL limited to this run's exact session epoch |
| `ca.pem` | Public disposable CA bundle copied into its final absolute location |
| `manifest.json` | Explicit `PREPARED_NOT_PROVISIONED` metadata, never an acceptance record |

All files are 0600 inside 0700 directories. Existing destinations, symlinks,
hard-linked inputs, FIFOs, insecure modes, oversized/duplicate JSON, extra
template privileges and floating source refs are refused. Partial generation
is removed. No credentials, URLs, identities or paths are printed on failure.
Never upload these files to Actions artifacts or commit them. Keep generated
bundles under ignored `.runtime` if inside this repository. The preparer owns
no active services; its cleanup never tears down an external environment.

## Remaining connected execution — INT-03B

The generated bundle is **not runnable by itself**. Infrastructure still owns:

1. An actual pinned private lab and independently observed source/image
   identities. Keep the existing qualified INT-02 lock/evidence unchanged.
   Requalify affected base assertions for changed engine pins.
2. Dedicated `nabhold.int03.test` HTTPS routing, the existing verified
   `iam.int02.test` and `cp.int02.test` origins, and actual TLS Redis at
   `redis.int03.test:6379`. No management or database host ports. The new edge
   and Redis certificates must be issued by the supplied disposable CA bundle.
   Install the CA in Chromium's NSS trust store too; no TLS bypass flags.
3. Authorised fixture provisioning, current CP external-identity mapping and
   isolated non-admin human credentials. No `cp:platform-admin` role is needed
   for `authority:self`. The client profile is not a business entitlement.
4. Redis TLS-only transport and the generated `users.acl`. Mount secret files
   privately under the service UID. Disable the default Redis user; never use
   a wildcard namespace or `+@all`. BFF ciphertext/session storage is distinct
   from an engine database. The helper's ACL grants only SET/GET/GETDEL/DEL and
   the documented node-redis handshake, not administration or scripting.
5. Run Nabhold from a clean actual checkout using the existing launcher. Keep
   the exact absolute bundle paths valid in every process that reads them:

   ```bash
   export NABHOLD_INTEGRATION_ENV_FILE=/absolute/private/new-int03-run/prepared/integration.env
   pnpm integration:check
   pnpm dev:integration
   # In another terminal on the same private network:
   pnpm test:e2e:integration
   ```

6. Verify and retain only the **sanitized observation receipts**, bind their
   declared dependencies to actual runtime sources/images, and prove teardown
   of all disposable services, identities and private files. A configuration
   check, a prepared manifest or local checksum does not supply that proof.

The recently merged Nabhold/ZuriBeans/Thamani/Shared/CP Codespaces settings
solve their image/package bootstrap lane; they do not attach five independent
Codespaces to this private network or provide IAM/CP registrations. Reuse the
Nabhold Node 24/pnpm 11.24.0 baseline and approved package-read permissions;
never bake registry tokens into images or put them in the BFF environment.

The Keycloak compatibility smoke does not close native Ory qualification. Full
INT-03 additionally needs IAM revocation/CP deactivation negatives and real CMS
published/preview, binding/context and publish/unpublish assertions. ERP F1,
Subscriptions production billing, legal evidence and protected staging retain
their own authority and acceptance gates. Nabhold remains non-trading.

## Source verification

```bash
python3 -m unittest discover -s tests/platform-integration/int03 -p test_handoff.py -v
```

Twelve source/security tests exercise private-file refusal, atomic publication,
fresh secrets/ACL epochs, exact dormant-template cloning, source pin checks,
secret-free errors and actual Node dotenv/CA/key interoperability. They run in
the existing mandatory INT-02 source job. The existing live job still proves
only its original IAM/CP/Pulse profile. Rollback: revert this preparer, stop any
separately provisioned disposable lab under its owning lifecycle, and destroy
unneeded private bundles; retain sanitized evidence under its original scope.


## INT-03B connected identity runner

`run.py` now owns an actual disposable lifecycle, unlike `handoff.py`. It loads
its separate `lock.json` and `prerequisite-lock.json`, imports the unchanged INT-02 implementation in an
isolated module/session, and overlays `compose.yaml`/`edge.conf`. The frozen
INT-02 lock is never edited. Selected current IAM/CP/Shared pins are requalified
through the complete existing IAM/CP/Pulse suite before Nabhold is tested.
That requalification is a new run, not inheritance of prior acceptance.
The qualifier hashes its own prerequisite file so that the recorded source
pins and manifest digest agree, rather than hashing the old frozen lock.
The integration devcontainer feature lock is now committed (Docker-outside-of-
Docker 1.10.1, resolved OCI digest from the pinned CLI's actual registry query);
CI uses `--frozen-lockfile`. Earlier attempts stopped because the CLI generated
an untracked lockfile. The clean-source requirement remains strict.

The profile builds the exact Nabhold checkout on its approved immutable Node
24/pnpm 11.24.0 browser image. Git metadata is retained so the existing consumer
independently checks its clean source revision. Package-read authentication
arrives through private stdin, is consumed by a BuildKit secret/tmpfs npmrc,
and is blanked before services start. Temporary GHCR Docker authentication is
removed after build. No registry credential becomes a runtime environment
variable, application mount, image layer or artifact. A package ACL/registry
failure blocks the run; it never substitutes local Shared packages or mocks.

A new non-admin synthetic `l4-int03-human` and `nabhold-int03` client are created
through real Keycloak administration. The product client stays disabled. The
issuer-generated subject is explicitly mapped to a new ACTIVE CP human in this
throwaway DB; no administrative/business grant or Tenant membership is added.
This SQL is a synthetic fixture boundary, never a protected registration recipe.

The edge and TLS-only Redis have distinct per-run leaf keys under one temporary
CA; the signer is destroyed before launch. Nabhold mounts only its prepared
handoff, Redis only its leaf material and namespace ACL. Chromium gets NSS trust
and Node gets the verified CA file; no certificate-ignore settings are used.
Actual running image configuration IDs are checked against built images and
recorded explicitly as **config IDs, not OCI manifest digests**. Source checkouts,
the running estate Git revision and consumer-declared pins are checked separately.

Run the same entrypoint inside the integration devcontainer or an equivalent
Docker-capable local runner, from a clean reviewed Infrastructure checkout:

```bash
python3 -B tests/platform-integration/int03/run.py preflight
printf '%s\n' "$BAOBAB_PACKAGES_READ_TOKEN" | \
  INT03_REGISTRY_USERNAME="$GITHUB_USER" \
  python3 -B tests/platform-integration/int03/run.py run --package-token-stdin
# Retry an interrupted cleanup without supplying a registry token:
python3 -B tests/platform-integration/int03/run.py down
```

Use the existing approved read-only package token/user; do not create a broader
credential. The Actions workflow uses its repository token with contents/package
read only, private stdin and the existing integration devcontainer. Repository
package/image access still needs to be granted by the owning GitHub package;
a 403 is a blocker, not authority to broaden permissions automatically.

`*-int03-identity/completed/receipt.json` and its paired digest contain only fixed scenario outcomes,
source/image identities, an original consumer-receipt hash and a fixed failure
stage/class, finite prerequisite browser failure facts, and fixed HTTP route/method/status
observations. Query strings, headers, cookies, bodies and raw URLs are excluded.
No raw Docker/Keycloak/Next/Playwright logs or fixture files are
uploaded. A smoke PASS requires all four NAB-ID cases, observed runtime pins and
successful resource/image/private-file cleanup. A failed teardown preserves
recovery handles and cannot leave `passed=true`. Interrupted runs require the
independent cleanup step, with label-scoped host recovery if the devcontainer
is unavailable; host recovery never grants qualification. Missing evidence
cannot establish a pass.
When browser execution fails, its actual nonzero exit and closed per-case
PASS/FAIL/BLOCKED projection are retained; raw browser errors remain suppressed.

This smaller identity profile does **not** accept NAB-01–04/full INT-03. CMS
qualification/binding, published/preview and mutation/denial tests, the remaining
revocation/Principal-deactivation/session-negative cases, protected native C4,
legal onboarding, staging and production retain their own gates. Nabhold remains
non-trading; human `authority:self` is never promoted into executive authority.

The connected handoff enables Nabhold's explicit trusted-proxy setting. Its
private TLS edge overwrites Host, X-Forwarded-Host and X-Forwarded-Proto; Nabhold
has no published host port. The app validates both authorities and exact HTTPS
against its configured public origin before reconstructing the callback URL,
including removal of the private listen port. This is an ingress transport
contract, not permission to trust arbitrary forwarded headers or bypass Origin,
PKCE, IAM introspection, CP identity or session custody checks.
