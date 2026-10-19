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
product=$("$KCADM" get clients -r baobab --config "$CONFIG" -q clientId=nabhold-executive)
jq -e 'length == 1 and .[0].enabled == false' <<< "$product" >/dev/null
printf '%s\n' "$uid"
