#!/usr/bin/env bash
# Fixture-only IAM administration. Executes against a genuine Keycloak realm
# assembled by baobab-iam's committed bootstrap.sh. None of these clients or
# people exist outside this isolated CI/Codespaces Docker network.
set -euo pipefail
set +x
umask 077
KCADM=/opt/keycloak/bin/kcadm.sh
CONFIG=$(mktemp)
trap 'rm -f "$CONFIG"' EXIT
"$KCADM" config credentials --server http://localhost:8080 --realm master \
  --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" --config "$CONFIG" >/dev/null
if ! "$KCADM" get clients -r baobab --config "$CONFIG" -q clientId=l4-int02-admin |
     grep -q '"clientId" : "l4-int02-admin"'; then
  "$KCADM" create clients -r baobab -f /run/l4/test-client.json --config "$CONFIG" >/dev/null
fi
if ! "$KCADM" get clients -r baobab --config "$CONFIG" -q clientId=l4-int02-other-audience |
     grep -q '"clientId" : "l4-int02-other-audience"'; then
  "$KCADM" create clients -r baobab -f /run/l4/other-client.json --config "$CONFIG" >/dev/null
fi
if ! "$KCADM" get users -r baobab --config "$CONFIG" -q username=l4-int02-human |
     grep -q '"username" : "l4-int02-human"'; then
  "$KCADM" create users -r baobab -f /run/l4/test-user.json --config "$CONFIG" >/dev/null
fi
"$KCADM" set-password -r baobab --username l4-int02-human \
  --new-password "$L4_TEST_USER_PASSWORD" --config "$CONFIG" >/dev/null
# The synthetic role is used only to probe CP routing and must not confer
# business grants or tenant membership on its own.
"$KCADM" add-roles -r baobab --uusername l4-int02-human \
  --rolename cp:platform-admin --config "$CONFIG" >/dev/null
echo 'Synthetic IAM test-only client and user provisioned (no credentials emitted).'
