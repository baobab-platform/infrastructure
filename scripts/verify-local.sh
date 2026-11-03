#!/bin/sh
set -eu

repository_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/compose/compose.yaml"
environment_file="$repository_root/compose/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to verify the local platform." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required to verify the local platform." >&2
  exit 1
fi

if [ ! -f "$environment_file" ]; then
  echo "Missing compose/.env. Run 'make local-env' and replace its values." >&2
  exit 1
fi

require_secret() {
  secret_name=$1
  secret_value=$(sed -n "s/^$secret_name=//p" "$environment_file" | tail -n 1)

  case $secret_value in
    "" | replace-with-*)
      echo "$secret_name must be replaced in compose/.env." >&2
      exit 1
      ;;
  esac

  if [ "${#secret_value}" -lt 24 ]; then
    echo "$secret_name must contain at least 24 characters." >&2
    exit 1
  fi
}

require_secret APISIX_ADMIN_KEY
require_secret POSTGRES_PASSWORD
require_secret RABBITMQ_DEFAULT_PASS
require_secret REDIS_PASSWORD

compose() {
  docker compose --env-file "$environment_file" -f "$compose_file" "$@"
}

compose config --quiet
"$repository_root/scripts/dev12-check-postgres-volume.sh"
compose up -d --wait etcd postgresql rabbitmq redis otel-collector apisix
compose --profile verify run --rm smoke
compose ps
