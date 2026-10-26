# Connected DEV-14/15 engine profiles

The generic facade uses Shared's closed profile, registered IAM ceilings and the
owner's real declaration/Dockerfile/adapter. Run inside the existing platform
integration Dev Container (the same definition used by Actions):

```sh
BAOBAB_ENVIRONMENT=development python3 -B tests/platform-integration/l4.py doctor engines --profile pulse-intelligence --static
BAOBAB_ENVIRONMENT=development python3 -B tests/platform-integration/l4.py run engines --profile pulse-intelligence
BAOBAB_ENVIRONMENT=development python3 -B tests/platform-integration/l4.py run engines --profile payments-sandbox
python3 -B tests/platform-integration/l4.py recover engines
```

`doctor`, `plan`, `prepare`, `up`, `test`, `evidence`, `down` and recovery share
one leased lifecycle. Source/image locks bind exact revisions. Component-mode
descriptors remain source-valid but are refused by this L4 executor. A source
plan or a successful build cannot accept a runtime case.

The trusted controller owns genuine issuer provisioning/read-back, guarded CP
bootstrap, normal registration/release/maker-checker activation, Trial composition
and bindings. Engine adapters receive only their own clients, context and native
stores. They run without root, Docker access, CP credentials or issuer admin
access. A separate private network and a narrow TLS gateway isolate native
services from issuer administration and platform databases; native code receives
only the public CA certificate. A probe from the actual owner namespace checks
that the private planes are unreachable.

Every declared ENG-ONB/domain case is retained. Native operations must increase
CP's matching recorded resolutions; Pulse's durable resource/mutation audits are
independently joined to CP records. Failure/recovery stops real CP, issuer and
owned store processes. Guarded negative fixtures may withdraw development-owned
principal/provider state but cannot reactivate them or confer protected
permissions. Provider activation uses normal two-human governance; rebinding uses
the normal repository path. Original INT-03C/NAB-03/DEV-06 inventories stay intact.

Receipt publication requires both issuer-client deletion/inactive-token read-back
and independent host absence after cleanup. Only sanitized final JSON/hash files
are uploaded. Source, native invocation and certification remain separate per
capability. No protected acceptance or real financial settlement is inferred.

The qualifier returns nonzero while any case is BLOCKED. The connected evidence
workflow separately verifies Payments' exact legal-actor/mandate and event-relay
gaps as BLOCKED rather than waiving or accepting them. A green evidence-custody
job therefore does not accept DEV-15 as a package. The known blocked cells must
be resolved and re-executed before package closure or returning to DEV-07.
