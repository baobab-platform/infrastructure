# DEV-04: original seven-case native IAM ↔ CP qualification

This is the current ordinary **synthetic development** path under
ADR-SHARED-043 and the Accepted EA-DEV plan. It builds on DEV-01/02/03 rather
than changing the seven INT-03C meanings. The historical
`../int03/int03c-lock.json` and Infrastructure #49 independent-human approval
packet remain protected/optional workflow references; they are not the lock or
approval prerequisite for this path. No CMS, estate BFF, engine provider,
legal-source verification or protected environment is qualified here.

## Run and inspect

Use the dedicated integration devcontainer (the same one Actions uses), with
Docker available, at a clean, reviewed Infrastructure commit:

```sh
export BAOBAB_ENVIRONMENT=development
python3 -B tests/platform-integration/l4.py preflight development --static
python3 -B -m unittest discover -s tests/platform-integration/development -p 'test_*.py'
python3 -B tests/platform-integration/l4.py run-int03c development
```

Static preflight and source tests never qualify a run. `run-int03c` performs
prepare → up → test → qualify-int03c → down, with teardown in `finally`.
A successful in-service qualifier is still **teardown pending**. Only the final
completed receipt can assert `int03c_qualified: true`. Check both the command
exit code and that receipt; seeing a progress message is insufficient.

For diagnosis without repeating destructive assertions:

```sh
python3 -B tests/platform-integration/l4.py prepare development
# Use the returned nonce as RUN_ID; do not substitute another operator's run.
python3 -B tests/platform-integration/l4.py up development --run-id "$RUN_ID"
python3 -B tests/platform-integration/l4.py test development --run-id "$RUN_ID"
python3 -B tests/platform-integration/l4.py qualify-int03c development --run-id "$RUN_ID"
python3 -B tests/platform-integration/l4.py down development --run-id "$RUN_ID"
python3 -B tests/platform-integration/l4.py evidence development --run-id "$RUN_ID"
```

Always call `down`, including after a failed qualifier. DEV-03 `qualify` and
DEV-04 `qualify-int03c` each disable their target: use **separate fresh runs**.
The start marker refuses reuse. A failed retry clears former success before
probing; a stale report is unlinked before launching a new attempt. Do not edit
markers, private state, canonical databases or evidence to make a run green.

## Responsibilities and actual observations

| Original case | Actual service assertions and control |
| --- | --- |
| `issuer-issuance-and-readback` | Hydra creates only fresh run-marked owner/verifier proof clients at their exact development audience, `context:resolve` scope, client-credentials method and 60-second configured lifetime. Owner obtains a genuine signed token. Named verifier authenticates independently at the exact private TLS introspection path and reads matching issuer, subject, client, audience, scope, expiry and active status. Owner credentials and wrong verifier secret cannot introspect. CP accepts the owner before mutation. |
| `current-cp-principal-and-link` | CP's guarded bootstrap owns canonical IDs and mappings. Distinct actual Kratos humans use Hydra code/S256 PKCE. Checker reads exact ACTIVE Principal; maker proposes exact issuer/subject/run/source provenance, self-approval returns 409, distinct checker approves the immutable bootstrap evidence digest. CP validates the current canonical external link in its transaction. Own tenant/Organisation/ZA context succeeds. No SQL is inserted by the driver. |
| `wrong-audience-denial` | Temporarily narrow the run-owned issuer client to ERP audience, obtain a genuine same-subject token, restore config in `finally`, independently introspect it as active and correctly bound, and observe CP 401 while unexpired. Fresh valid-audience control succeeds. No JWT editing. |
| `wrong-tenant-denial` | The same unexpired owner bearer receives 403 for a sibling and unrelated external tenant. Own-context control succeeds. |
| `issuer-revocation-before-expiry` | Positive CP control and named-verifier active readback precede native issuer revocation. The distinct verifier reads inactive, the **same** bearer receives CP 401, and expiry remains future after the response. Fresh issuance succeeds. Natural expiry and unrelated 403 cannot pass. |
| `cp-principal-deactivation` | Positive control precedes maker's digest-bound CP request. Same Principal and wrong digest receive 409; distinct checker completes. Checker reads exact Principal DISABLED. Same bearer receives CP 403 before expiry while the independent issuer verifier still reads active. This distinguishes canonical CP authority from issuer revocation. |
| `complete-teardown` | Revoke remaining owner tokens, DELETE both proof clients and GET 404, deny subsequent issuance, independently read original tokens inactive, DELETE/GET404 both Kratos identities and read CP Principal terminal. Host then removes and independently inventories all run-labelled containers, volumes, networks and built images, including the accepting CP/database, and deletes private run state before completing the case. |

The verifier is `baobab-int03c-issuer-verifier`, distinct from owner and from
CP's request-time status credential `baobab-dev-introspection`. Only these two
introspection readers are configured in the isolated TLS edge's private Basic
credential file. The verifier secret is fresh per run and matches its native
client registration. This is a narrow Infrastructure transport overlay over
Hydra's admin introspection, not a production IAM provider permission claim.
Deleting its native client prevents issuance; final host teardown removes the
edge credential/configuration as well. No other Hydra admin path is published.

The fixture token hook supplies identity normalization only. CP still verifies
the signature/current status and owns Principals, context, grants and provenance.
`INDEPENDENTLY_APPROVED_UNATTESTED` is development provenance, not provider or
legal certification. No invented ACTIVE provider/engine bindings are needed.
One operator/CI may drive distinct real synthetic maker/checker Principals;
independent people and custody requirements for staging remain separate.

## Evidence, custody and interpretation

`int03c_contract.py` is the closed evidence vocabulary; `int03c_probe.py` owns
real HTTP observations. The report checkpoints after each assertion in the
private run. First assertion failure becomes FAIL, a transport failure becomes
FAIL/SERVICE_UNAVAILABLE and unexecuted dependent cases stay BLOCKED. Reports
contain only case IDs, fixed reasons and booleans, never provider response text.
The host validates exact fields/cases/assertions; malformed or incomplete results
cannot promote qualification. A survivor prevents a successful teardown receipt.

The final `evidence/dev01-<nonce>/completed/receipt.json` includes all seven
cases, actual harness SHA, dependency source pins, built image IDs, immutable
runtime image references, lock SHA-256, native configuration SHA-256 anchors and
hashes of the three Shared contracts checked byte-for-byte against CP's embedded
copies. It retains `nab03_qualified`, `canonical_provider_qualified`, protected
and production flags false (the provider flag is inside the INT-03C report).
The receipt sidecar hashes its original JSON bytes. Hashes are integrity anchors,
not independent signatures or external certification.

Actions runs `ci.py` for DEV-01/02/03, then `ci_int03c.py` in a **fresh run**.
The latter observes stopped-CP health rejection, restoration and retest before
the seven-case proof, then deliberately loses Compose state before cleanup.
It independently checks the completed receipt/hash and publishes
`dev04-int03c-suite.json` plus its digest. Failed-run completed receipts are
also uploaded by the always-run artifact step; a missing suite is not PASS.
Private state, credentials, JWTs, native sessions, callback codes, raw bootstrap
and provider bodies must never enter an artifact or PR.

Before adopting the result in Shared, review the exact head, require all
applicable CI green, download the original archive, verify GitHub's archive
digest and each retained receipt hash, inspect all seven results and teardown,
and record the artifact/run/actual executed harness identity separately from
reviewed and merged commits. Preserve earlier receipts and dated assessments.
An Actions run does not imply an observed interactive Codespaces run or owner
provider conformance. Broad findings close only within this evidenced scope.

## Failure recovery and maintenance

| Symptom | Required action |
| --- | --- |
| Missing Docker, source/image/contract drift or nondevelopment environment | Refuse execution. Restore reviewed exact pins/configuration; never replace a digest with a floating tag or bypass the guard. |
| Provider startup/transport failure | Retain only closed diagnostic codes. Recover the owned run, inspect private state locally if needed and retry with fresh resources. Do not print provider logs or secrets into CI. |
| Failed assertion or CP 503 | Preserve FAIL/BLOCKED outcomes. A dependency outage is not an authentication denial. Fix source/configuration and rerun fresh; do not relabel a result. |
| Lost Compose/envfile or interrupted creator | `down development --run-id "$RUN_ID"` uses independent ownership labels, not Compose or live DB credentials. After process/host recovery use `recover development --all` for this checkout/user namespace. |
| Surviving owned resource or Docker unavailable | Receipt cannot claim qualification. Keep the durable recovery handle, restore Docker and retry cleanup. Do not delete the run ledger to conceal survivors. |
| Lease expired | Watchdog reaps owned resources; normal recovery reconciles leftovers. Token TTL is not a substitute for runtime/client teardown. |
| Secret scanner flags a configuration digest | Verify the exact original bytes are a file digest, then use a reviewed fingerprint-only false-positive exception. Never suppress an entire evidence path/rule or alter producer receipt bytes. |

After IAM/CP/Shared changes, update `development/lock.json` only to reviewed
immutable commits and rerun source + actual native proof. A provider version
change also needs new digest pins and verification of API/status semantics.
When changing a case, update its original meaning, closed assertion vocabulary,
failure tests and this table together; do not translate DEV-03's sixteen-case
booleans into seven-case PASS. When changing cleanup, preserve the ordering:
provider readbacks → host resource removal/empty inventory → private-state
removal → completed receipt. Roll back by recovering owned runs and restoring
previous reviewed pins; never edit old evidence or enable protected bootstrap.
