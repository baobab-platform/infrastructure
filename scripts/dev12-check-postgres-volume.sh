#!/bin/sh
# DEV-12: refusal-only physical PostgreSQL major-version check.
# No DB startup, write, delete, mount upgrade, restore or migration action.
set -eu

root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$root/compose/compose.yaml"
env_file="$root/compose/.env"

for tool in docker python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "DEV12_DENIED: required tool unavailable: $tool" >&2
    exit 2
  fi
done
if ! docker compose version >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "DEV12_DENIED: Docker Compose or daemon unavailable" >&2
  exit 2
fi
if [ ! -f "$env_file" ]; then
  echo "DEV12_DENIED: compose/.env is missing" >&2
  exit 2
fi

# Derive both the image and volume from the ACTUAL resolved Compose model.
# Never guess a volume name or permit an environment override to redirect
# the probe to an unrelated database volume.
if ! model=$(docker compose --env-file "$env_file" -f "$compose_file" config --format json); then
  echo "DEV12_DENIED: invalid resolved Compose configuration" >&2
  exit 2
fi
if ! plan=$(printf '%s' "$model" | python3 -c '
import json, re, sys
try:
    obj=json.load(sys.stdin)
    service=obj["services"]["postgresql"]
    image=service["image"]
    if not re.fullmatch(r"postgres:17(?:\.[0-9]+)?(?:-[A-Za-z0-9._-]+)?", image):
        raise ValueError("only the governed PostgreSQL 17 image is accepted")
    mounts=[v for v in service["volumes"] if v["type"]=="volume"
            and v["target"]=="/var/lib/postgresql/data"]
    if len(mounts)!=1:
        raise ValueError("PostgreSQL must have exactly one governed data volume")
    source=mounts[0]["source"]
    volumes=obj["volumes"]
    volume=volumes[source]["name"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}", volume):
        raise ValueError("invalid resolved volume name")
    print(image)
    print(volume)
except (KeyError, TypeError, ValueError, IndexError) as error:
    sys.stderr.write("DEV12_DENIED: resolved PostgreSQL model cannot be verified: "+str(error)+"\n")
    sys.exit(2)
'); then
  echo "DEV12_DENIED: cannot establish authoritative PostgreSQL image/volume identity" >&2
  exit 2
fi

image=$(printf '%s\n' "$plan" | sed -n '1p')
volume=$(printf '%s\n' "$plan" | sed -n '2p')
if [ -z "$volume" ] || [ -z "$image" ]; then
  echo "DEV12_DENIED: empty volume or image identity" >&2
  exit 2
fi

# A Docker permission/API error is NOT the same as absence of a volume.
if inspection=$(docker volume inspect "$volume" 2>&1); then
  :
else
  case "$inspection" in
    *"no such volume"*|*"No such volume"*)
      echo "DEV12_POSTGRES_VOLUME_ABSENT: safe to initialise a new PostgreSQL 17 local volume"
      exit 0 ;;
    *)
      echo "DEV12_DENIED: cannot inspect existing database volume" >&2
      exit 2 ;;
  esac
fi

# Read-only + offline: PostgreSQL itself is NOT started, so the guard
# cannot perform initdb, pg_upgrade or implicitly write to an old volume.
# Any nonempty volume without PG_VERSION is treated as corrupt/ambiguous.
if actual=$(docker run --rm --network none --read-only \
  --security-opt no-new-privileges:true \
  --mount "type=volume,source=$volume,target=/pgdata,readonly" \
  --entrypoint sh "$image" -eu -c '
    if [ -f /pgdata/PG_VERSION ]; then
      version=$(cat /pgdata/PG_VERSION)
      if [ "$version" = 17 ]; then
        echo DEV12_POSTGRES_VOLUME_MAJOR_17
      else
        echo "DEV12_DENIED: existing PostgreSQL data major is $version; use a separately verified DEV-12 backup/migration/restore" >&2
        exit 42
      fi
    elif [ -z "$(ls -A /pgdata)" ]; then
      echo DEV12_POSTGRES_VOLUME_EMPTY
    else
      echo "DEV12_DENIED: nonempty PostgreSQL volume without PG_VERSION" >&2
      exit 43
    fi
  '); then
  printf '%s\n' "$actual"
  exit 0
fi

echo "DEV12_DENIED: physical volume major cannot be safely admitted to PostgreSQL 17" >&2
exit 2
