#!/usr/bin/env bash
# L3-07: engine-template must expose the hooks new engines need for L2/L3.
# Resolves template root as:
#   1) ENGINE_TEMPLATE_DIR if set
#   2) sibling ../engine-template relative to this infrastructure repo
#   3) if neither exists and REQUIRE_ENGINE_TEMPLATE is unset → skip (exit 0)
#   4) if REQUIRE_ENGINE_TEMPLATE=1 and missing → fail
set -euo pipefail

repository_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
template_dir="${ENGINE_TEMPLATE_DIR:-}"

if [ -z "$template_dir" ]; then
  sibling="$repository_root/../engine-template"
  if [ -d "$sibling" ]; then
    template_dir=$(CDPATH='' cd -- "$sibling" && pwd)
  fi
fi

if [ -z "$template_dir" ] || [ ! -d "$template_dir" ]; then
  if [ "${REQUIRE_ENGINE_TEMPLATE:-}" = "1" ]; then
    echo "FAIL: engine-template not found (set ENGINE_TEMPLATE_DIR or clone as sibling ../engine-template)"
    exit 1
  fi
  echo "SKIP: engine-template not present (set ENGINE_TEMPLATE_DIR to enforce)"
  exit 0
fi

echo "Checking engine-template at $template_dir"

missing=0
require_path() {
  local rel=$1
  if [ -e "$template_dir/$rel" ]; then
    echo "  present: $rel"
  else
    echo "  MISSING: $rel"
    missing=$((missing + 1))
  fi
}

# Scaffold identity (Foundation)
require_path "README.md"
require_path "TEMPLATE-USAGE.md"
require_path ".baobab/repository.yaml.example"
require_path ".baobab/environment.yaml.example"
require_path "contracts/README.md"

# Contract consumption guidance (Phase B)
require_path "contracts"

# New engines must learn L2/L3 wiring; these may be examples until activated.
# Prefer explicit testing docs once added to the template.
if [ -f "$template_dir/docs/testing/platform-l2-l3.md" ] || \
   [ -f "$template_dir/docs/testing/README.md" ] || \
   [ -f "$template_dir/Makefile.example" ] || \
   [ -f "$template_dir/Makefile" ]; then
  echo "  present: testing/Makefile guidance"
else
  echo "  MISSING: docs/testing/platform-l2-l3.md (or Makefile / Makefile.example)"
  missing=$((missing + 1))
fi

# Consumer lock is required once lifecycle=active; template may only document it.
if [ -f "$template_dir/contracts.lock.yaml.example" ] || \
   [ -f "$template_dir/contracts.lock.yaml" ] || \
   grep -q "contracts.lock" "$template_dir/contracts/README.md" 2>/dev/null || \
   grep -qi "contract" "$template_dir/TEMPLATE-USAGE.md" 2>/dev/null; then
  echo "  present: contract lock guidance"
else
  echo "  MISSING: contracts.lock.yaml.example or lock guidance in TEMPLATE-USAGE / contracts README"
  missing=$((missing + 1))
fi

if [ "$missing" -gt 0 ]; then
  echo "FAIL: engine-template missing $missing required L2/L3 hook(s)"
  exit 1
fi

echo "PASS: engine-template L2/L3 hooks present"
exit 0
