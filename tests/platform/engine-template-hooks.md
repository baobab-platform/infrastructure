# Engine-template hooks for L2 / L3

New engines created from `baobab-platform/engine-template` must leave the
scaffold with enough structure that platform integrated testing can attach.

Enforced by **L3-06** (`tests/platform/check-engine-template.sh`) against a
sibling clone or `ENGINE_TEMPLATE_DIR`.

## Required in the template (scaffold stage)

| Artifact | Purpose |
| --- | --- |
| `README.md` | Role / ownership / contract dependencies placeholders |
| `TEMPLATE-USAGE.md` | Activation checklist |
| `.baobab/repository.yaml.example` | Foundation trait `engine` |
| `.baobab/environment.yaml.example` | baobab-dev profile |
| `contracts/README.md` | How to pin Shared contracts |
| `docs/testing/platform-l2-l3.md` **or** `Makefile` / `Makefile.example` | L2/L3 wiring guidance |
| `contracts.lock` mentioned in docs **or** `contracts.lock.yaml.example` | EA-01 consumer lock guidance |

## Required before first production capability (activation)

| Artifact | Purpose |
| --- | --- |
| `contracts.lock.yaml` | EA-01 consumer pin to Shared |
| `make test` | L0 unit |
| `make test-integration` (or documented equivalent) | L2 against infrastructure Compose |
| Optional health/ready URL | L3-04 style probe via `PLATFORM_*_URL` |

## Running the check

```bash
make platform-l3-engine-template

ENGINE_TEMPLATE_DIR=/path/to/engine-template make platform-l3

REQUIRE_ENGINE_TEMPLATE=1 ENGINE_TEMPLATE_DIR=../engine-template ./tests/platform/check-engine-template.sh
```

Exit codes from `check-engine-template.sh`: **0** pass or skip (stdout begins with `SKIP:` when skipped), **1** fail.
