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
checks_tmp=$(mktemp)
trap 'rm -f "$checks_tmp"' EXIT

PASS=0
FAIL=0
SKIP=0

record() {
  local id=$1 status=$2 detail=$3
  case $status in
    pass)
      echo "  PASS: $id — $detail"
      PASS=$((PASS + 1))
      ;;
    skip)
      echo "  SKIP: $id — $detail"
      SKIP=$((SKIP + 1))
      ;;
    *)
      echo "  FAIL: $id — $detail"
      FAIL=$((FAIL + 1))
      status=fail
      ;;
  esac
  detail_json=$(printf '%s' "$detail" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
  printf '%s\n' "{\"id\":\"$id\",\"status\":\"$status\",\"detail\":$detail_json}" >>"$checks_tmp"
}

write_evidence() {
  mkdir -p "$evidence_dir"
  local checks_json
  checks_json=$(python3 -c '
import sys
lines = [ln.strip() for ln in sys.stdin if ln.strip()]
print(",".join(lines))
' <"$checks_tmp")
  cat >"$evidence_file" <<EOF
{
  "harness": "platform-l3",
  "version": "0.3.0",
  "timestamp": "$timestamp",
  "pass": $PASS,
  "fail": $FAIL,
  "skip": $SKIP,
  "checks": [${checks_json}]
}
EOF
}

if [ ! -f "$environment_file" ]; then
  echo "Missing compose/.env. Run 'make local-env' or 'make ci-env' first." >&2
  exit 1
fi

set -a
# shellcheck source=/dev/null
. "$environment_file"
set +a

compose() {
  docker compose --env-file "$environment_file" -f "$compose_file" "$@"
}

rmq_api() {
  local path=$1
  shift
  curl --fail --silent --show-error \
    -u "${RABBITMQ_DEFAULT_USER}:${RABBITMQ_DEFAULT_PASS}" \
    "http://127.0.0.1:${RABBITMQ_MANAGEMENT_PORT:-15672}${path}" \
    "$@"
}

vhost_enc=$(python3 -c "import urllib.parse,os; print(urllib.parse.quote(os.environ.get('RABBITMQ_DEFAULT_VHOST','nabhold'), safe=''))")

echo "== L3-01 infrastructure smoke (verify-local) =="
if "$repository_root/scripts/verify-local.sh"; then
  record "L3-01" pass "verify-local smoke passed"
else
  record "L3-01" fail "verify-local smoke failed"
fi

echo "== L3-02 RabbitMQ vhost readiness =="
if rmq_api "/api/health/checks/ready-to-serve-clients" >/dev/null; then
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
  record "L3-04" skip "PLATFORM_CP_URL unset"
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
  record "L3-05" skip "PLATFORM_IAM_URL unset"
fi

echo "== L3-06 engine-template L2/L3 hooks =="
check_script="$repository_root/tests/platform/check-engine-template.sh"
chmod +x "$check_script" 2>/dev/null || true
template_out=$("$check_script" 2>&1) || template_rc=$?
template_rc=${template_rc:-0}
printf '%s\n' "$template_out"
if [ "$template_rc" -ne 0 ]; then
  record "L3-06" fail "engine-template hooks check failed"
elif printf '%s' "$template_out" | grep -q '^SKIP:'; then
  record "L3-06" skip "engine-template not present"
else
  record "L3-06" pass "engine-template L2/L3 hooks present"
fi

echo "== L3-08 RabbitMQ publish/get fixture =="
# Infra-only bus proof: declare queue, publish via default exchange, get and ack.
qname="l3.platform.fixture.${timestamp}"
if rmq_api "/api/queues/${vhost_enc}/${qname}" \
  -H 'content-type: application/json' \
  -X PUT \
  -d '{"durable":false,"auto_delete":true,"arguments":{}}' >/dev/null 2>&1; then
  payload=$(printf '{"harness":"platform-l3","ts":"%s"}' "$timestamp" | python3 -c 'import json,sys,base64; print(json.dumps({"properties":{},"routing_key":"%s","payload":sys.stdin.read(),"payload_encoding":"string"} % "'"$qname"'"))')
  # Fix routing_key properly
  payload=$(python3 -c "
import json
q = '''${qname}'''
ts = '''${timestamp}'''
body = json.dumps({'harness': 'platform-l3', 'ts': ts})
print(json.dumps({
  'properties': {},
  'routing_key': q,
  'payload': body,
  'payload_encoding': 'string',
}))
")
  if rmq_api "/api/exchanges/${vhost_enc}/amq.default/publish" \
    -H 'content-type: application/json' \
    -X POST \
    -d "$payload" | grep -q '"routed":true'; then
    got=$(rmq_api "/api/queues/${vhost_enc}/${qname}/get" \
      -H 'content-type: application/json' \
      -X POST \
      -d '{"count":1,"ackmode":"ack_requeue_false","encoding":"auto"}' || true)
    if printf '%s' "$got" | grep -q 'platform-l3'; then
      record "L3-08" pass "published and consumed fixture message on ${qname}"
    else
      record "L3-08" fail "publish succeeded but get did not return fixture payload"
    fi
  else
    record "L3-08" fail "publish to amq.default did not route to ${qname}"
  fi
  # Best-effort cleanup
  rmq_api "/api/queues/${vhost_enc}/${qname}" -X DELETE >/dev/null 2>&1 || true
else
  record "L3-08" fail "could not declare fixture queue ${qname}"
fi

echo "== L3-09 optional Regulations probe =="
if [ -n "${PLATFORM_REGULATIONS_URL:-}" ]; then
  if curl --fail --silent --show-error --max-time 15 "${PLATFORM_REGULATIONS_URL}" >/dev/null; then
    record "L3-09" pass "Regulations reachable at PLATFORM_REGULATIONS_URL"
  else
    record "L3-09" fail "Regulations not reachable at PLATFORM_REGULATIONS_URL"
  fi
else
  record "L3-09" skip "PLATFORM_REGULATIONS_URL unset"
fi

echo "== L3-10 APISIX admin probe =="
if [ -n "${APISIX_ADMIN_KEY:-}" ]; then
  if curl --fail --silent --show-error --max-time 15 \
    -H "X-API-KEY: ${APISIX_ADMIN_KEY}" \
    "http://127.0.0.1:${APISIX_ADMIN_PORT:-9180}/apisix/admin/routes" >/dev/null; then
    record "L3-10" pass "APISIX admin routes reachable"
  else
    record "L3-10" fail "APISIX admin routes probe failed"
  fi
else
  record "L3-10" fail "APISIX_ADMIN_KEY unset"
fi

echo "== L3-11 evidence pack =="
write_evidence
record "L3-11" pass "wrote $evidence_file"
write_evidence

echo ""
echo "Platform L3 summary: $PASS passed, $FAIL failed, $SKIP skipped"
echo "Evidence: $evidence_file"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
