# Native Keycloak development adapter. Import the exact IAM-owned realm;
# no product workload activation or Ory/federation qualification is claimed.
FROM quay.io/keycloak/keycloak:26.7.5@sha256:37dbaf6f0722c9ec246335f36e1ef8b2e6cb960f7c27e0d8c615121a3d475a85
COPY config/realm/baobab-realm.json /opt/keycloak/data/import/baobab-realm.json
USER 1000
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
