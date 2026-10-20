# Invoked only with privately streamed documents in this disposable realm.
set -euo pipefail
set +x
umask 077
KCADM=/opt/keycloak/bin/kcadm.sh
CONFIG=$(mktemp)
trap 'rm -f "$CONFIG"; rm -rf "$INT03_FIXTURE_DIR"' EXIT
"$KCADM" config credentials --server http://localhost:8080 --realm master \
 --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD" --config "$CONFIG" >/dev/null
"$KCADM" create clients -r baobab --config "$CONFIG" -f "$INT03_FIXTURE_DIR/client.json" >/dev/null
"$KCADM" create users -r baobab --config "$CONFIG" -f "$INT03_FIXTURE_DIR/user.json" >/dev/null
# Observe the actual record, rather than assuming Keycloak used an input UUID.
users=$("$KCADM" get users -r baobab --config "$CONFIG" -q username=l4-int03-human -q exact=true)
uid=$(jq -er 'if length == 1 and .[0].username == "l4-int03-human" and .[0].enabled == true then .[0].id else error("fixture") end' <<< "$users")
roles=$("$KCADM" get "users/$uid/role-mappings/realm" -r baobab --config "$CONFIG")
jq -e 'all(.[]; (.name | startswith("cp:")) | not)' <<< "$roles" >/dev/null
clients=$("$KCADM" get clients -r baobab --config "$CONFIG" -q clientId=nabhold-int03)
cid=$(jq -er 'if length == 1 and .[0].enabled == true and .[0].serviceAccountsEnabled == false and .[0].directAccessGrantsEnabled == false and .[0].fullScopeAllowed == false then .[0].id else error("fixture") end' <<< "$clients")
scopes=$("$KCADM" get "clients/$cid/default-client-scopes" -r baobab --config "$CONFIG")
jq -e '[.[].name] | sort == ["actor-type-human","authority:self","basic"]' <<< "$scopes" >/dev/null
# Keycloak 26.7 checks that the confidential INTROSPECTING client itself
# is in the access token audience. CP's existing authority:self scope supplies
# baobab-control-plane; this mapper adds ONLY this same synthetic BFF as an
# additional intended token recipient. It does not add a grant, an optional
# scope, a role, a service account, or change the dormant product client.
# Scoped disposable compatibility fixture: not protected IAM onboarding.
cat > "$INT03_FIXTURE_DIR/self-audience.json" <<'INT03_SELF_AUDIENCE'
{
  "name": "int03-confidential-self-audience",
  "protocol": "openid-connect",
  "protocolMapper": "oidc-audience-mapper",
  "consentRequired": false,
  "config": {
    "included.custom.audience": "nabhold-int03",
    "id.token.claim": "false",
    "access.token.claim": "true",
    "introspection.token.claim": "true"
  }
}
INT03_SELF_AUDIENCE
"$KCADM" create "clients/$cid/protocol-mappers/models" -r baobab --config "$CONFIG" -f "$INT03_FIXTURE_DIR/self-audience.json" >/dev/null
# Assert the actual Keycloak representation rather than trusting the input.
mappers=$("$KCADM" get "clients/$cid/protocol-mappers/models" -r baobab --config "$CONFIG")
jq -e '
  length == 1 and .[0].name == "int03-confidential-self-audience" and
  .[0].protocol == "openid-connect" and
  .[0].protocolMapper == "oidc-audience-mapper" and
  .[0].config["included.custom.audience"] == "nabhold-int03" and
  .[0].config["access.token.claim"] == "true" and
  .[0].config["id.token.claim"] == "false" and
  .[0].config["introspection.token.claim"] == "true"
' <<< "$mappers" >/dev/null
product=$("$KCADM" get clients -r baobab --config "$CONFIG" -q clientId=nabhold-executive)
jq -e 'length == 1 and .[0].enabled == false' <<< "$product" >/dev/null
printf '%s\n' "$uid"
