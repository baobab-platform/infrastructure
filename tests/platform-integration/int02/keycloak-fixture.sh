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
  # The fixture documents are injected over Compose stdin into a private
  # directory owned by Keycloak's non-root UID; never chmod host files.
  if [ -n "${L4_FIXTURE_DIR:-}" ]; then rm -rf -- "$L4_FIXTURE_DIR"; fi
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

# Keep client-provisioning error responses private; emit a fixed HTTP
# classification for diagnostics only. No server response or client secret is
# sent to the workflow log.
create_client() {
  local file="$1" response="" code=OTHER
  if response=$("$KCADM" create clients -r baobab -f "$file" --config "$CONFIG" 2>&1); then
    return 0
  fi
  case "$response" in
    *"400 Bad Request"*) code=HTTP_400 ;;
    *"401 Unauthorized"*) code=HTTP_401 ;;
    *"403 Forbidden"*) code=HTTP_403 ;;
    *"409 Conflict"*) code=HTTP_409 ;;
    *"500 Internal Server Error"*) code=HTTP_500 ;;
  esac
  printf 'INT02_FIXTURE_HTTP_CLASS=%s\n' "$code"
  return 1
}

# Shared already registers canonical:read for CP. Product IAM has no
# browser client using it yet; allocate it ONLY inside this disposable realm
# for the record-isolation read. authority:self independently supplies CP aud.
STAGE=human-read-scope-create
if exists client-scopes name=canonical:read name canonical:read; then
  :
else
  code=$?
  [ "$code" -eq 1 ] || exit "$code"
  "$KCADM" create client-scopes -r baobab --config "$CONFIG" \
    -s name=canonical:read -s protocol=openid-connect \
    -s 'attributes={"include.in.token.scope":"true","display.on.consent.screen":"false"}' >/dev/null
fi

# Human governance scopes are already canonical Shared vocabulary; expose
# them only on the disposable browser fixture, whose privileged MFA is real.
for scope in topology:read topology:write provider:certify changeset:read changeset:write changeset:approve engine-release:approve provider:approve; do
  STAGE=human-governance-scope
  if exists client-scopes "name=$scope" name "$scope"; then
    :
  else
    code=$?
    [ "$code" -eq 1 ] || exit "$code"
    "$KCADM" create client-scopes -r baobab --config "$CONFIG" \
      -s "name=$scope" -s protocol=openid-connect \
      -s 'attributes={"include.in.token.scope":"true","display.on.consent.screen":"false"}' >/dev/null
  fi
done

STAGE=admin-client-lookup
if exists clients clientId=l4-int02-admin clientId l4-int02-admin; then
  :
else
  code=$?
  [ "$code" -eq 1 ] || exit "$code"
  STAGE=admin-client-create
  create_client "$L4_FIXTURE_DIR/test-client.json"
fi
STAGE=audience-client-lookup
if exists clients clientId=l4-int02-other-audience clientId l4-int02-other-audience; then
  :
else
  code=$?
  [ "$code" -eq 1 ] || exit "$code"
  STAGE=audience-client-create
  create_client "$L4_FIXTURE_DIR/other-client.json"
fi
# This approved named caller is deliberately absent from product bootstrap.
STAGE=pulse-client-create
create_client "$L4_FIXTURE_DIR/pulse-client.json"
STAGE=human-user-lookup
if exists users username=l4-int02-human username l4-int02-human; then
  :
else
  code=$?
  [ "$code" -eq 1 ] || exit "$code"
  STAGE=human-user-create
  "$KCADM" create users -r baobab -f "$L4_FIXTURE_DIR/test-user.json" --config "$CONFIG" >/dev/null
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

# Four distinct humans: group/account membership never supplies CP grants.
# The actual browser completes code/S256 for each; no password grant is used.
for label in parent subsidiary sibling external replay; do
  STAGE=human-user-create
  "$KCADM" create users -r baobab --config "$CONFIG" \
    -s "username=l4-int02-$label" -s enabled=true -s emailVerified=true \
    -s firstName=Synthetic -s "lastName=$label" -s "email=l4-int02-$label@example.invalid" >/dev/null
  STAGE=human-password-set
  "$KCADM" set-password -r baobab --username "l4-int02-$label" \
    --new-password "$L4_TEST_USER_PASSWORD" --config "$CONFIG" >/dev/null
  STAGE=human-role-add
  "$KCADM" add-roles -r baobab --uusername "l4-int02-$label" \
    --rolename cp:platform-admin --config "$CONFIG" >/dev/null
done
