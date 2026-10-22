# INT-03 retained runtime evidence, teardown witness and L3 private probes

**Authority:** Accepted Shared #354, EA v2.3, Nabhold Go-Live v2.0,
ADR-Infra-0009 (APISIX) and ADR-Infra-0012 (RabbitMQ).

**State:** engineering verification is implementable; the canonical Shared
registry is still **HELD**. No synthetic CMS identity, governed CP approval,
provider certification, or live NAB-03 case is created by this change.
Historical component PASS is not full cross-engine qualification.

## L3 regression root cause and repair

The 22 October 2026 main L3 run
[39745270790](https://github.com/baobab-platform/infrastructure/actions/runs/39745270790)
reported three failures:

| Check | Observed cause | Correction |
|---|---|---|
| L3-02 RabbitMQ health | Host `127.0.0.1:15672` connection refused immediately after passing internal `verify-local` smoke | Reuse authenticated `smoke` container on the private `data` network with `rabbitmq:15672`; no external management dependency |
| L3-08 RabbitMQ publish/get | Host-side management queue declaration could not connect | Issue POST/GET/DELETE through authenticated private `smoke` network; still require routed/consumed fixture and cleanup |
| L3-10 APISIX Admin | Host-loopback Admin API returned **403**, while internal `verify-local` Admin call succeeded | Use internal `apisix:9180` from `smoke`, which is on the governed `control` network permitted by APISIX's `allow_admin` CIDR; preserve full Admin key and HTTP failure checks |

**Important:** Do not widen `allow_admin` to host NAT/public CIDRs,
expose more management ports, disable Admin authentication, or make
RabbitMQ management endpoints publicly accessible to turn the test green.

The unset `PLATFORM_CP_URL`, `PLATFORM_IAM_URL` and
`PLATFORM_REGULATIONS_URL` yielded **SKIP**, not FAIL. They are optional
L3 extension probes; invented addresses or nonexistent local services
would turn a valid optional SKIP into misleading failures. Real CP/IAM
integration is tested separately by the INT-02 and INT-03 workflows.
The L3 workflow now also runs on scoped PRs touching its configuration,
not only main and weekly schedule.

## Two independent evidence classes

### 1. CMS component-only evidence, executable now under HELD

`cms_provider.py run` builds the actual committed CMS image, runs
PostgreSQL 17 migrations and fixtures, probes the CMS HTTP service, and
tries owned cleanup. Its receipt remains `component_outcome=PASS` or
`FAIL`, with all 14 NAB-03 cases `BLOCKED`.

**After** its own cleanup, the separate `cms_component_custody.py capture`
process:

1. Independently re-hashes the original `receipt.json` against the source
   writer's original SHA-256.
2. Queries the actual Docker daemon for any project-labelled containers,
   networks and volumes **and** the two run-tagged CMS images.
3. Requires the CMS component recovery handle and per-run private directory
   absent; source code returning cleanup success is insufficient.
4. Writes a second sanitized component-only teardown observation and seals
   both observations with `cms_evidence.py` into an exclusive 0600
   content-hashed evidence inventory. A second `verify` process re-reads
   every original file and both independent SHA-256 manifests.
5. Uploads both receipts and the sealed inventory in a per-run GitHub Actions
   artifact with overwrite disabled and an explicit retention period.
   Capture the returned Actions artifact **ID and uploaded digest** for
   independent later download/re-hash.

If any read-back fails, the witness fails and no component teardown PASS
can be accepted. This **does not** mean IAM, CP, or the Nabhold BFF have
been cleaned in a full connected run. The receipt explicitly records
`iam_teardown=NOT_EXERCISED`, `cp_teardown=NOT_EXERCISED` and
`qualified=false`.

A local manifest hash proves byte integrity relative to the manifest,
**not WORM immutability, external storage retention or independent
acceptance**. Qualification requires upload custody, independent
download/hash verification, provenance, maker/checker review and a
separate accepted attestation. Never assert external immutability from a
local `.sha256` file alone.

### 2. Full IAM/CP/CMS independent teardown (activation gated)

`cms_teardown_witness.py` is read-only and is meant to run **after** the
connected executor's cleanup using a separate operator. It never calls
the cleanup API or relies on a local success flag. It needs an
owner-private descriptor with exact committed Shared and IAM revisions,
random run/project identity, exact permitted two IAM clients,
prior issuer/CP/runtime creation-evidence digests, and the list of
synthetic CP resources. Live read-backs must establish:

- No owned Docker containers, networks, volumes or built images.
- Both named development-only Hydra clients return 404 on a private,
  CA-validated administrative TLS endpoint (not merely disabled grants).
- A distinct authorised CP checker uses a private credential to
  independently read each approved synthetic CP resource as absent or
  in a known, explicitly inactive/revoked terminal state. Active or
  unreachable CP authority fails.
- No private secret, native compiled bridge, journal, session or other
  per-run private file survives the disposal.

**All** fences must succeed. The output still says
`OBSERVED_UNATTESTED`, `qualified=false`, because the independent
gate reviewer must separately verify the original prior-creation proofs,
context/token denial, exact runtime/image pins, all 14 NAB-03 results,
and final evidence custody. A failure retains recovery responsibility.
A synthetic unit-test stub is never a live teardown attestation.

At present there are no approved CP maker/checker credentials or
connected fixture activation. Do **not** fabricate approvals, seed CP SQL,
borrow another product workload, or run the private witness against
production infrastructure.

## Acceptance gates

The complete connected NAB-03 run may start **only after** Shared's real
canonical registry becomes OPEN with the two exact development-only
identities, independently approved synthetic CP Tenant/Organisation/
Principal/grants/market/release/certification/bindings are available,
the real IAM/CP/CMS services run on a disposable private network,
and all source/image/trust pins and cleanup controls are independently
validated. All 14 scenarios must return actual service observations,
followed by a complete independent teardown and reviewer attestation.
Until then every normative case is BLOCKED.
