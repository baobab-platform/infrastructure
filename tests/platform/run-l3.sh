#!/usr/bin/env bash
# Platform L3 critical-path harness (infra-owned).
# Requires compose/.env and Docker Compose v2.
set -euo pipefail

repository_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
compose_file="$repository_root/compose/compose.yaml"
environment_file="$repository_root/compose/.env"
evidence_dir="${EVIDENCE_DIR:-$repository_root/tests/platform/evidence}"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
evidence_file="$evidence_dir/l3-${timestamp}.json"

PASS=0
FAIL=0
RESULTS_JSON=""

record() {
  local id=$1 status=$2 detail=$3
  if [ "$status" = "pass" ]; then
    echo "  PASS: $id — $detail"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $id — $detail"
    FAIL=$((FAIL + 1))
  fi
  # shellcheck disable=SC2089
  RESULTS_JSON="${RESULTS_JSON}{\"id\":\"$id\",\"status\":\"$status\",\"detail\":$(printf '%s' "$detail" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')},"
}

if [ ! -f "$environment_file" ]; then
  echo "Missing compose/.env. Run 'make local-env' or 'make ci-env' first." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a
# shellcheck source=/dev/null
. "$environment_file"
set +a

compose() {
  docker compose --env-file "$environment_file" -f "$compose_file" "$@"
}

echo "== L3-01 infrastructure smoke (verify-local) =="
if "$repository_root/scripts/verify-local.sh"; then
  record "L3-01" pass "verify-local smoke passed"
else
  record "L3-01" fail "verify-local smoke failed"
fi

echo "== L3-02 RabbitMQ vhost readiness =="
if curl --fail --silent --show-error \
  -u "${RABBITMQ_DEFAULT_USER}:${RABBITMQ_DEFAULT_PASS}" \
  "http://127.0.0.1:${RABBITMQ_MANAGEMENT_PORT:-15672}/api/health/checks/ready-to-serve-clients" \
  >/dev/null; then
  record "L3-02" pass "RabbitMQ management ready-to-serve-clients"
else
  record "L3-02" fail "RabbitMQ management health check failed"
fi

echo "== L3-03 PostgreSQL connectivity =="
if command -v docker >/dev/null 2>&1; then
  if compose exec -T postgresql pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
    record "L3-03" pass "pg_isready inside postgresql service"
  else
    if command -v pg_isready >/dev/null 2>&1 && \
      pg_isready -h 127.0.0.1 -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
      record "L3-03" pass "pg_isready on host loopback"
    else
      record "L3-03" fail "PostgreSQL not ready"
    fi
  fi
else
  record "L3-03" fail "docker not available"
fi

echo "== L3-04 optional CP readiness =="
if [ -n "${PLATFORM_CP_URL:-}" ]; then
  if curl --fail --silent --show-error --max-time 15 "${PLATFORM_CP_URL}" >/dev/null; then
    record "L3-04" pass "CP reachable at PLATFORM_CP_URL"
  else
    record "L3-04" fail "CP not reachable at PLATFORM_CP_URL=${PLATFORM_CP_URL}"
  fi
else
  record "L3-04" pass "skipped (PLATFORM_CP_URL unset)"
fi

echo "== L3-05 optional IAM OIDC discovery =="
if [ -n "${PLATFORM_IAM_URL:-}" ]; then
  discovery="${PLATFORM_IAM_URL%/}/.well-known/openid-configuration"
  if curl --fail --silent --show-error --max-time 15 "$discovery" | grep -q '"issuer"'; then
    record "L3-05" pass "OIDC discovery reachable"
  else
    record "L3-05" fail "OIDC discovery failed at $discovery"
  fi
else
  record "L3-05" pass "skipped (PLATFORM_IAM_URL unset)"
fi

echo "== L3-07 engine-template L2/L3 hooks =="
chmod +x "$repository_root/tests/platform/check-engine-template.sh"
if "$repository_root/tests/platform/check-engine-template.sh"; then
  record "L3-07" pass "engine-template hooks check passed or skipped"
else
  record "L3-07" fail "engine-template hooks check failed"
fi

echo "== L3-06 evidence pack =="
mkdir -p "$evidence_dir"
RESULTS_JSON="${RESULTS_JSON%,}"
cat >"$evidence_file" <<EOF
{
  "harness": "platform-l3",
  "version": "0.2.0",
  "timestamp": "$timestamp",
  "pass": $PASS,
  "fail": $FAIL,
  "checks": [${RESULTS_JSON}]
}
EOF
record "L3-06" pass "wrote $evidence_file"

echo ""
echo "Platform L3 summary: $PASS passed, $FAIL failed"
echo "Evidence: $evidence_file"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
