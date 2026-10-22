# INT-03C governed real IAM + CP qualification acceptance gate

**Status: engineering preparation. The normative seven-case run has not been executed or accepted.**  
**Authority:** Accepted Shared `docs/architecture/int03c-governed-proof-bootstrap-decision.md`, Shared #366 merged at `74dd98d47e678fc479bb4bfc4138d601fb53319e`, IAM #137, CP #427 and Infrastructure #47.

## Normative evidence — seven required actual service observations

1. Fresh private Hydra issuance and *independent* active introspection of exact owner client, token lifetime within the Accepted Shared 60–900-second ceiling and the independently approved run window, CP audience and `context:resolve` only. A narrower approved native client profile remains binding.
2. Independently read back the same CP-generated ACTIVE canonical workload Principal *and* its approved exact external (issuer,subject) mapping. A human administrator effective-authority GET alone does not prove workload registration.
3. Separately IAM-issued wrong-audience token rejected by CP, with exact denial code and before expiry.
4. Own-Tenant real CP positive, followed by neighbour Tenant denial; the neighbour must be a separately admitted ACTIVE Tenant and the maker/checker must not self-provision it.
5. Revocation of a *previously CP-accepted* token followed by issuer ACTIVE→INACTIVE independent introspection **before natural expiry** and denial of that **same** bearer by CP.
6. Governed CP deactivation of the exact CP Principal with distinct ACTIVE human maker and checker, digest-bound reviewed plan, atomic status/external-link change; independently read back DISABLED and a new otherwise-active issuer token denied by CP. An issuer-side token revocation is not CP deactivation.
7. Complete teardown of both native issuer clients, credentials, issuer trust, authorised CP synthetic resources, contexts, accepting runtimes, built images, containers, volumes and network; independently read back no survivors and rehash externally retained original creation receipts.

For each, independently retained actual HTTP request/response *sanitized facts* with current issuer/CP source SHAs, contracts, image digests, run nonce, correlation, status, authority and original-byte SHA-256 must exist. No token/secret headers in evidence. Run must close before its absolute 90-minute deadline; all tokens must expire by then and independent reviewer must ensure no effective credential remains.

## Current verified foundations vs blockers

- Shared #366 named exactly `baobab-int03c-issuer-owner` and `baobab-int03c-issuer-verifier`, both ACTIVE **development proof-bootstrap only** with CP audience and `context:resolve` only. No CMS consumer/validator identity activation.
- IAM #137 is merged at `ca5eb723c7845ed9a60e19fd0ef1a1e900d7b97a`. It implements the native two-client bridge, distinct live deadline watchdog lease and crash-recovery requirements. Actual independent runtime shutdown remains unexecuted under Infrastructure #49.
- CP #427 is merged at `bcea71bd9909be3672dfcb7ce78d04d6feb0e748`, including immutable two-human provenance, transactional deactivation and disposable PostgreSQL regression CI. Actual approved topology, current canonical workload linkage and live context denial remain unexecuted.
- `int03c-lock.json` separately pins merged Shared #366, IAM #137, CP #427 and the recorded CMS/Nabhold sources. Both CP and issuer observers use `connected_identity_sources.py`; `cms-lock.json` is unchanged. The exact Infrastructure execution SHA must be a clean descendant of merged #48 (`9ba30c410ffcc6a46f5d912bf03853532f7adf0c`). Source-lock conformance grants no runtime approval.
- `connected_identity_cp_lifecycle.py` uses only the CP guarded maker/checker HTTP route and independent read-back, with no SQL shortcuts. Its source unit tests cannot certify actual human Principal grants, issuer linkage or CP status changes.
- The seven-case custody and teardown readers deliberately return `qualified=false`. A complete locally hashed ledger remains **OBSERVED_UNATTESTED** until external immutability and independent checker signoff.

## Stop/go gate

**BLOCKED** until all six conditions hold: (i) IAM and CP mandatory CI green, review security satisfied, exact-head merge reconciled; (ii) private source-built actual IAM and CP runtime; (iii) two current approved CP human Principal operators plus separately governed synthetic Principal and Tenant/Organisation/market provider grants; (iv) real seven complete current cases with strict positive and negative codes and original-byte external custody; (v) independent teardown including token/JWT verifier shutdown; (vi) final reviewer reproduction of exact hashes and live disappearance. No bypass via SQL, fake JWT, mock transport, manual STATUS=PASS, or old CMS lock.

INT-03D has **no independently accepted written acceptance contract found in Shared, Infrastructure, Nabhold, IAM or CP at this review**. Its gate/scope must be authored and approved separately; do not begin a guessed INT-03D execution, or treat INT-03C code completion as a qualified run.

Shared #354 remains HELD and all 14 NAB-03 cases remain BLOCKED.


## Separate source preparation and approval package

Infrastructure #49 is an **approval request, not approval**. The source lock
contains no host, credentials, approver signature, generated topology ID or
acceptance observation. None may be invented to make a plan executable.

Before any live observer or issuer action, independent operators must review
the exact Infrastructure execution SHA and every dependency in `int03c-lock.json`,
then approve host/network, image digests, external deadline supervisor, two CP
administrators, governed admission inputs and external immutable evidence custody.
Use a full clean checkout containing the Infrastructure baseline history; missing
ancestry fails closed. Supply those exact six source revisions in each private
operator plan. The new lock does not itself provision or build a runtime.

The CP observer remains an incomplete diagnostic: its human administrative read
is not proof of the workload's canonical issuer/subject linkage. Separate real
workload provenance, issuer mutation, CP status/link read-back and seven-case
originals remain mandatory. No source test performs those live actions.
