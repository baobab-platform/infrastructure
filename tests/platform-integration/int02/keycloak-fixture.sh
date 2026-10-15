#!/usr/bin/env bash
# Fixture-only IAM administration. Executes against a genuine Keycloak realm
# assembled by baobab-iam's committed bootstrap.sh. None of these clients or
# people exist outside this isolated CI/Codespaces Docker network.
set -euo pipefail
set +x
umask 077
KCADM=/opt/keycloak/bin/kcadm.sh
CONFIG=$(mktemp)
# Fail closed, but emit only a fixed stage identifier on failure. The real
# kcadm errors can contain privileged server responses or secrets; their raw
# output remains suppressed by orchestrate.py. Never enable shell xtrace.
STAGE=admin-login
cleanup() {
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    printf 'INT02_FIXTURE_FAILURE_STAGE=%s\n' "$STAGE"
  fi
  rm -f -- "$CONFIG"
}
trap cleanup EXIT
"$KCADM" config credentials --server http://localhost:8080 --realm master \
  --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" --config "$CONFIG" >/dev/null
# JSON-aware existence test. Parsing the Keycloak CLI's pretty-printed
# output with grep -q is unsafe with pipefail (SIGPIPE can classify an
# existing client as missing). A failed kcadm lookup must not be confused
# with an empty result.
exists() {
  local resource="$1" filter="$2" field="$3" wanted="$4" response
  response=$("$KCADM" get "$resource" -r baobab --config "$CONFIG" -q "$filter") || return 2
  jq -e --arg field "$field" --arg wanted "$wanted" \
    'any(.[]; .[$field] == $wanted)' <<< "$response" >/dev/null
}

STAGE=admin-client-lookup
if exists clients clientId=l4-int02-admin clientId l4-int02-admin; then
  :
else
  code=$?
  [ "$code" -eq 1 ] || exit "$code"
  STAGE=admin-client-create
  "$KCADM" create clients -r baobab -f /run/l4/test-client.json --config "$CONFIG" >/dev/null
fi
STAGE=audience-client-lookup
if exists clients clientId=l4-int02-other-audience clientId l4-int02-other-audience; then
  :
else
  code=$?
  [ "$code" -eq 1 ] || exit "$code"
  STAGE=audience-client-create
  "$KCADM" create clients -r baobab -f /run/l4/other-client.json --config "$CONFIG" >/dev/null
fi
STAGE=human-user-lookup
if exists users username=l4-int02-human username l4-int02-human; then
  :
else
  code=$?
  [ "$code" -eq 1 ] || exit "$code"
  STAGE=human-user-create
  "$KCADM" create users -r baobab -f /run/l4/test-user.json --config "$CONFIG" >/dev/null
fi
STAGE=human-password-set
"$KCADM" set-password -r baobab --username l4-int02-human \
  --new-password "$L4_TEST_USER_PASSWORD" --config "$CONFIG" >/dev/null
# The synthetic role is used only to probe CP routing and must not confer
# business grants or tenant membership on its own.
STAGE=human-role-add
"$KCADM" add-roles -r baobab --uusername l4-int02-human \
  --rolename cp:platform-admin --config "$CONFIG" >/dev/null
echo 'Synthetic IAM test-only client and user provisioned (no credentials emitted).'
