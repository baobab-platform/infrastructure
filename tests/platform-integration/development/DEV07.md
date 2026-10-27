# DEV-07 live buyer IAM/CP component qualifier

This opt-in development profile reuses the ordinary guarded DEV-01 lifecycle,
actual native Kratos/Hydra and CP, and a separate actual Trade/Medusa/PostgreSQL
source tool. It does not claim the shipped production Trade image, a deployed
BFF, full INT-05, provider certification, protected staging or production.
Shared #405, CP #446, IAM #139 and Trade #176 are the companion source changes.

Run from the clean integration laboratory with Docker available:

```sh
BAOBAB_ENVIRONMENT=development python3 -B tests/platform-integration/development/buyer_identity.py
```

The base lock pins Shared/CP/IAM and immutable native images. The owner lock pins
Trade. These currently reference companion candidates: source pins must follow
reviewed accepted commits before programme adoption. No floating branch, test
response or CI skip can supply missing authority. The default development
profiles retain their existing pins and feature switches.

The runtime creates actual native clients from IAM's closed builder, then uses
CP's guarded owner command to establish the leased exact canonical validator
Principal/tenant and BFF estate binding. CP alone writes that state. Trade's own
PostgreSQL database has a separate private credential. The source tool sees its
native database, TLS trust and bounded issuer/client evidence; it receives no
CP DSN, issuer administration endpoint credential or Docker socket.

Real Kratos login/WhoAmI and Hydra authorization code/S256 PKCE produce one
Trade-only buyer code and a separate CP-client wrong-audience code for the same
synthetic human. The BFF's approved human profile is not expanded. A private
0600 code packet reaches Trade through a read-only file mount after migrations,
so database setup cannot age it unnecessarily. Only actual Hydra issues tokens;
identity normalization derives actor type from both client and native grant,
and human assurance from the actual accepted native session.

Trade runs its maintained buyer handler over the actual native store and real
issuer/CP transports. It retains all eight component results with closed reasons.
A missing scope, source mismatch or unavailable dependency refuses qualification.
The host hash-checks and validates the exact sanitized receipt. It then establishes
a current CP estate-binding positive control, revokes the binding through CP's
owner command, and observes CP refusal while the same independently active,
unexpired issuer credentials remain valid. This distinguishes CP authority from
issuer expiry. Native client DELETE/GET404 and inactive credential readback
precede independent inventory/removal of run-labelled containers, stores,
networks and built images. Every cleanup is attempted on failure.

Only completed sanitized receipts under evidence/dev01-<run>/completed and the
closed dev07-buyer-suite JSON/hash pair are uploaded. Credentials, code packets,
provider bodies and pending/private state are never artifacts. Stale suite output
is removed before each new attempt. A failed assertion, owner cleanup or surviving
host resource cannot produce qualification. An interrupted/lost runner uses the
same `l4.py recover development --all` recovery path as existing profiles.

The component qualifier keeps the original 16 PASS / 9 BLOCKED receipt and all
original scenario meanings unchanged. New live evidence must be downloaded,
hash-checked and reviewed against the exact tested pins before updating the
Shared programme register. The source tests use explicit mocks and cannot stand
in for a live runtime. Restore reviewed pins to roll back; never widen registry
ceilings, forge CP attestation or enable a buyer commitment fence as a shortcut.
