# Engine-template hooks for L2 / L3

New engines created from `baobab-platform/engine-template` must leave the
scaffold with enough structure that platform integrated testing can attach.

This is enforced loosely by **L3-07** (`tests/platform/check-engine-template.sh`)
against a sibling clone or `ENGINE_TEMPLATE_DIR`.

## Required in the template (scaffold stage)

| Artifact | Purpose |
| --- | --- |
| `README.md` | Role / ownership / contract dependencies placeholders |
| `TEMPLATE-USAGE.md` | Activation checklist |
| `.baobab/repository.yaml.example` | Foundation trait `engine` |
| `.baobab/environment.yaml.example` | baobab-dev profile |
| `contracts/README.md` | How to pin Shared contracts |

## Required before first production capability (activation)

| Artifact | Purpose |
| --- | --- |
| `contracts.lock.yaml` | EA-01 consumer pin to Shared |
| `make test` | L0 unit |
| `make test-integration` (or documented equivalent) | L2 against infrastructure Compose |
| Optional health/ready URL | L3-04 style probe via `PLATFORM_*_URL` |

## Recommended template additions (follow-up on engine-template repo)

1. `docs/testing/platform-l2-l3.md` — copy the CP pattern:
   - `INFRASTRUCTURE_DIR=../infrastructure`
   - `make dev-up-infra` style targets once language stack is chosen
   - `contract_lock.py check` against sibling `shared`
2. `contracts.lock.yaml.example` — empty or minimal lock pointing at Shared main tip
3. `Makefile.example` with `test` and `test-integration` stubs

Until those land on `engine-template` itself, L3-07 accepts either the testing
doc **or** a Makefile / Makefile.example, and contract guidance via README text.

## Running the check

```bash
# From infrastructure (stacked branch)
make platform-l3-engine-template

# Or full L3 (includes L3-07)
ENGINE_TEMPLATE_DIR=/path/to/engine-template make platform-l3

# CI / strict: fail if template missing
REQUIRE_ENGINE_TEMPLATE=1 ENGINE_TEMPLATE_DIR=../engine-template ./tests/platform/check-engine-template.sh
```
