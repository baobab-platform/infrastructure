#!/usr/bin/env bash
# One complete INT-02 run, exactly as a developer runs it in the integration
# Codespace (ADR-SHARED-036 s6.3: the same entrypoints on Codespaces and
# Actions). CI invokes this inside .devcontainer/platform-integration through
# devcontainers/ci, so both executors share one image, one toolchain and the
# same docker-outside-of-docker path translation.
#
# Teardown always runs. A failed teardown fails the run even when every
# earlier stage passed, so cleanup failures are never hidden.
set -euo pipefail
cd "$(dirname "$0")/../../.."
L4=tests/platform-integration/l4.py

cleanup() {
  rc=$?
  if ! python3 "$L4" down iam-cp; then
    echo "INT-02 teardown failed" >&2
    [ "$rc" -ne 0 ] || rc=3
  fi
  exit "$rc"
}
trap cleanup EXIT

python3 "$L4" materialise iam-cp
python3 "$L4" up iam-cp
python3 "$L4" test iam-cp
python3 "$L4" evidence iam-cp >/dev/null
