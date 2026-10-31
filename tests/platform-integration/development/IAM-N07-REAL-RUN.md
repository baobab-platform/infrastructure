# IAM-N07 — Source-pinned disposable Ory/CP/Redis development run

31 October 2026 | Infrastructure PR #69; EA v2.3 / EA-DEV DEV-04/07/08/11/14.
STATUS: REAL-COMPONENT ENGINEERING, CONNECTED N07/TMS ACCEPTANCE HELD.

## Immutable source and images

The dedicated n07-base-lock.json pins exact Shared, CP, IAM, Nabhold,
ZuriBeans, Thamani and TMS revisions plus digest-specific PG17, Hydra,
Kratos, NGINX, Python and Redis images. It is separate from the accepted
DEV-01/04 lock.json and N02 first-party candidate. CP #455 embeds
Shared #421, not the newer Shared #422 PROVISIONED-only TMS proposal.
Therefore the candidate must never claim a registered ACTIVE TMS native
resource or booking authorization from this source lock.

Every candidate run checks its clean Infrastructure SHA, exact peer
checkouts, matching CP embedded Shared registry, private run nonce
and image digest. Upgrading a PR head requires an independent source
re-pin and a fresh run, not relabeling an older original.

## Real development run

The platform-development.yml N07 job uses the existing pinned devcontainer.
The same owner-operated command runs in the exact reviewed container:

    export BAOBAB_ENVIRONMENT=development
    python3 -B tests/platform-integration/development/n07_disposable.py

The dedicated development lifecycle first reserves a 3600-second bounded
run and watchdog, then creates one internal-only Docker network, fresh
CA/TLS identities and run-scoped credentials. It starts actual PG17,
Hydra, Kratos, CP, edge and Redis. No provider/Admin/Redis ports are
published. It exercises existing actual issuer/CP native health,
Principal resolution and DEV-03 authority/revocation negatives through
dev.test and dev.qualify, not synthetic HTTP response substitutes.

The N07 Python probe connects over real TLS to the Redis service inside
that SAME run network, verifies trusted CA and hostname, authenticates
the unique n07 ACL account, proves PING, a random SET/GET/GETDEL
one-use value, foreign prefix GET/SET denial, anonymous PING refusal,
wrong-password refusal and refusal of the self-signed certificate
without its reviewed trust root. Redis has a run-owned Thamani-only
ACL key prefix, password HASH in a private source-mounted file,
read-only nonroot runtime, dropped capabilities and no persistent
customer data.

A private original record is fsynced and SHA-256-bound to exactly
the owner run/source pins and Redis image. It explicitly states that
cross-worker BFF session acceptance, issuer/CP integration acceptance,
legal mandate and TMS native booking are NOT accepted. The existing
host run-label inventory independently verifies deletion of all
containers, volumes, networks, labelled images and private state.
Only then is the sanitized digest-bound receipt published.

Failure or timeout is BLOCKED: the watchdog and independent host recovery
own cleanup. Run the existing l4.py recover development --all from the
same approved workspace to retry teardown after interruption. Never
reuse a previous run ID or its evidence.

## Explicit remaining connected acceptance

A green N07 component job establishes a real, ephemeral
Hydra/Kratos/CP/Redis component observation, not full N07 acceptance.
It DOES NOT prove:
- Thamani's Next.js BFF real sign-in, browser/CP Principal membership,
  real AAL2 or post-recovery current issuer sessions;
- N06 A3/A4 cryptographic passkey/risk, global sign-out or issuer rotation;
- an ACTIVE registered Shared #422 TMS subject and validator, CP LA-05A
  SERVICE_PROVIDER_OF_RECORD, provider-specific binding/lease or native
  booking/dispatch execution;
- live Pulse/Payments, carrier, PSP, ERP or documentary consequences;
- staging or production certification or protected approval.

Thamani #44 separately adds real TLS Redis cross-worker session custody.
IAM #152 has source-pinned Chromium estate and engine consumers.
TMS #28 adds issuer/CP and LA-05A operation-specific, still
non-executable, native resource preflights. Shared #422's identities
are PROVISIONED, never self-activated. A complete same-run N07 will
require the owner to provision actual first-party Thamani TLS ingress,
registered Hydra client, CP human Principal and current market grants,
execute IAM #152 browser with original private profiles and independent
witness, and then obtain separately registered ACTIVE native TMS
binding/operation proof with original revocation and teardown.
A passing unit suite or this component receipt cannot substitute.

When Shared #422 becomes accepted, CP must independently adopt its
exact registry; update its embedded contracts and the N07 lock together.
No late CI convenience override may turn PROVISIONED into ACTIVE.
