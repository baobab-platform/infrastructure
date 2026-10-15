# INT-01 / L4-00 — Codespaces and GitHub Actions integration foundation

Authority: Accepted ADR-SHARED-036 and EA Plan v2.2. Infrastructure owns this
temporary, disposable real-component test environment. The L4-00 profile
starts PostgreSQL, RabbitMQ and Redis, not IAM/CP/Nabhold/CMS. It does not
prove protected staging, G17 or live customer/legal/financial authorisation.

Select the dedicated integration Codespace configuration (not the default
Infrastructure devcontainer). Execute exactly the same sequence on an
Actions runner:

    python3 tests/platform-integration/l4.py preflight foundation
    python3 tests/platform-integration/l4.py up foundation
    python3 tests/platform-integration/l4.py test foundation
    python3 tests/platform-integration/l4.py evidence
    python3 tests/platform-integration/l4.py down

The CLI generates a unique Compose project, short-lived random database/broker
credentials, no exposed host ports, and isolated internal volumes/networks.
Sensitive runtime files in .runtime and sanitized JSON in evidence are ignored.
The down command deletes the project, volumes and generated credentials;
run it in an unconditional CI cleanup step.

Preflight --static is an offline SOURCE-ONLY check and cannot satisfy L4.
The manifest now records verified OCI digests for the three container images,
obtained from GitHub Actions immutable reference discovery on 15 October 2026.
Changing a tag requires an explicit reviewed digest re-lock. Runtime preflight
refuses unresolved or mutable images; source SHA pins remain independently
governed dependency baselines, not a claim that their services run in L4-00.

Minimum resources: Docker with Compose v2, Python 3.12+, >=2 CPU and >=4 GiB
RAM. Do not supply AWS production secrets, live IAM principals, CIPC/SARS
identities, actual PSP credentials or tenant data. No management ports are
ever forwarded; Codespaces forwarded-port policy is private/disabled.

INT-02 adds actual IAM and CP executables with synthetic principals; INT-03
adds the Nabhold confidential BFF and CMS. These are deliberately NOT
reported as implemented by INT-01.
