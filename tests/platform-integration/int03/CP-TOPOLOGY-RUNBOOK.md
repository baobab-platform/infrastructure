# INT-03 CMS — CP-governed synthetic topology and independent certification

**Scope:** prepare the disposable development-only CP topology without granting
CMS fixture identity authority. **Classification:** source-level operator
orchestration and verification; actual CP runtime topology and certification
**not yet proven**. Shared #354 remains HELD, and the 14 connected NAB-03
acceptance cases remain BLOCKED.

## Authority and mutation route map

| Resource | Only authoritative path | Evidence and separation |
|---|---|---|
| Synthetic Tenant | `POST /v1/tenant-onboarding-requests` (CP AdmissionDecision), separate authorisation and `POST /v1/tenants` | Requires **actual APPROVED AdmissionDecision** and AUTHORISED TenantOnboardingRequest. CP mints ID and returns async Operation. A successful HTTP 202 does not make a Tenant ACTIVE. `GET /v1/tenants/{id}` confirms CP result. No bootstrap migration shortcuts. |
| Organisation and LegalEntity | CP verification-case workflow and `POST /v1/tenants/{tenantID}/organisation-admission` | Must name actual APPROVED AdmissionDecision and independently VERIFIED organisation-purpose legal-identity case. CP owns canonical Organisation and legal identity. Claims are not self-certified. Verify `GET /v1/organisations/{id}/overview`. |
| Principal | CP's canonical issuer/subject linking and existing admin/BFF identity registration boundary | Never mint Principal UUID locally, map by email, or insert through SQL. Admin Principal must already be ACTIVE in CP to own administrative changes; workload Principal must be verified through actual IAM/CP identity registration and token before use. Buyer-only `register-buyer` must **not** be repurposed for a CMS workload. |
| Principal administrative grant | `POST /v1/admin/grants` then `GET /v1/admin/grants/{id}` | Use real existing CP Principal and catalogue permission; a new grant may be PENDING. ACTIVE is required to count as proved. This is **administrative authority**, not a substitute for CP capability grants. |
| Market | `POST /v1/markets`, distinct reviewer `POST /v1/markets/{id}/activate` | CP mints `mkt_` ID, validates its config, and maker must differ from checker. Reviewer uses CP revision If-Match; GET must show ACTIVE, exact `activated_by` and correct owner Tenant. |
| EngineRelease | `POST /v1/engine-releases`, governed changeset approval | CP mints `erl_` ID. Initial CANDIDATE cannot be called APPROVED by the recording actor. Exact source digest, artefact digests, declared provider support and capability contract majors required. |
| ProviderCapabilityCertification | Reviewer `POST /v1/provider-capability-certifications` | Distinct registered CP Principal from release recorder, real retained sha256 evidence URIs. Independent `GET` confirms `CERTIFIED` and exact provider, release and capability. Certification **never** creates binding or health. |
| CapabilityBinding and capability grant | CP `/v1/tenants/{tenantID}/provisioning` plan/approve/apply under ADR-SHARED-015, then workload `POST /v1/capabilities/resolve` | CP TenantProvisioning plans `CREATE_CAPABILITY_BINDING` and `CREATE_CAPABILITY_GRANT` from the actual AUTHORISED, FULFILLED onboarding desired state. Separate Principal approves the exact digest; asynchronous apply and readiness must be observed. CP `/v1/admin/changesets` does **not** support a `CAPABILITY_BINDING` kind. The current workload-owned context must resolve the intended grant, binding, provider and instance; local metadata cannot substitute. |

These routes are verified against existing CP `api/router.go`,
`market_handler.go`, `tenant_registration_handler.go`,
`organisation_admission_handler.go`,
`grant_admin_handler.go`, `engine_release_handler.go`,
`provider_certification_handler.go`,
`capability_resolve_handler.go` and associated Shared schema snapshots.
CP's interface is authoritative; Infrastructure cannot write CP storage or
mint IDs, advance legal verification, provision privileges, or bypass SoD.

## Implementation and guardrails

`cms_cp_governance.py` supplies an authenticated, CA-pinned,
non-redirecting **real HTTP** CP gateway; exact reviewed operation methods
for Tenant registration, Organisation admission, grant request, market,
release and independent provider certification; and independent read-back.
`verify_resolved_provider` takes a separately authenticated workload-only
CP capability resolver (not one of the two platform administrators) and
rejects mismatched or revoked provider certification, context, engine
instance, grant or binding. It only returns `qualified=false`.

`cms_cp_fixture_run.py` is the operator entrypoint. It accepts an
individually reviewed, development-only, JSON document with precisely
`schema`, `run_id`, `environment`, `step`, `document` and
`idempotency_key`. `inspect` is source-only/no-network. `apply`
requires **two pre-existing ACTIVE CP human Principals**, their own
distinct short-lived token files (owner-only), the private CP CA, and an
out-of-repo private receipt directory. One explicit step per invocation,
so no scripted auto-approval or silent leap from a CP 202 to an ACTIVE
Tenant, Organisation, Principal, release or provider binding. Use a single
idempotency key for a single immutable request.

The operator does not issue, simulate or request CMS workload credentials,
change the canonical Shared #354 registry, use SQL, or claim CP governance
sign-off itself. Caller-defined status, `approved`, `certified`,
`client_secret` or tokens are refused. Read-back is mandatory and all
receipts explicitly state no full INT-03 acceptance.

### Example source-only preflight

```bash
python3 -B tests/platform-integration/int03/cms_cp_fixture_run.py inspect \
  --plan /private/reviewed-int03-cp-step.json
```

A separate, registered administrator may then explicitly apply **one**
reviewed step using `--cp-origin https://cp.int03.test`,
`--ca`, distinct `--maker-principal` and
`--checker-principal`, distinct owner-private `--maker-token-file` and
`--checker-token-file`, and a new `--receipt` in a private directory.
The CP-only runner does **not** use the IAM CMS identity exception to
authenticate administrators. Do not create test-only administrator JWTs
or provision new administrators from this tool.

### Retained gaps (must remain explicit)

1. Live private CP deployment with actual pre-existing human reviewers and
   real approved AdmissionDecision/VerificationCase inputs is still required.
   No such tokens, human approvals or CP URLs are bundled here.
2. The CP issuer/subject Principal linkage for the disposable CMS workload
   must be qualified via actual IAM ↔ CP integration. Human buyer Principal
   self-registration is not the CMS workload authority path.
3. Engine capability-provider registration, instance health and current
   CP TenantProvisioning binding/grant plan approval and apply must be independently accepted.
   These cannot be inferred from a provider certification or CP admin grant.
4. The reviewer must cite retained **actual** CMS/PG17 and security
   acceptance artefacts and a distinct CP Principal. A fake test response,
   source digest or historical component receipt is not qualification.
5. All 14 connected NAB-03 cases, independent resource-server teardown,
   Shared registry activation, staging and production remain separately held.

**CP binding implementation correction:** The generic changeset catalogue
contains `PROVIDER_ACTIVATION` and `ENGINE_RELEASE_APPROVAL`, but **not**
`CAPABILITY_BINDING`. Binding/grant materialisation belongs to
`TenantProvisioning` under ADR-SHARED-015. `Fixture.request_provisioning()`
requests the CP-desired-state plan for one registered tenant and fulfilled
onboarding request; `Fixture.verify_provisioning_binding()` separately GETs
the CP state and generated plan, requires READY/ACTIVE, different maker and
checker, exact APPROVED non-stale plan digest, and a matching
`CREATE_CAPABILITY_BINDING` step. It never writes the binding itself.
The final independent workload resolution must still show the binding and
grant live. A generic changeset cannot be used to bypass this lifecycle.
