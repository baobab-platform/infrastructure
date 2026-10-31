#!/usr/bin/env bash
# SOURCE-ONLY N02 ingress syntax check. Synthetic ephemeral certificate,
# no live Kratos/Hydra/BFF/CP services, no provider acceptance.
set -euo pipefail
cd "$(dirname "$0")/../../../.."
export BAOBAB_ENVIRONMENT=development
umask 077

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -m 700 -p "$tmp/render" "$tmp/private/edge"
python3 - "$tmp/profile.json" <<'PY'
import json,os,sys
doc = {
    "schema": "baobab.iam.n02.browser-qualification.v1",
    "environment": "development",
    "run_id": "a" * 32,
    "iam_source_sha": "b" * 40,
    "shared_source_sha": "c" * 40,
    "cp_source_sha": "d" * 40,
    "infrastructure_harness_sha": "e" * 40,
    "require_aal2": True,
    "bff_origin": "https://iam-n02.private.example.test",
    "kratos_origin": "https://iam-n02.private.example.test",
    "hydra_origin": "https://hydra.private.example.test",
}
fd = os.open(sys.argv[1], os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w") as file:
    json.dump(doc, file)
PY
python3 -B tests/platform-integration/development/n02_ingress.py \
  --profile "$tmp/profile.json" --output-dir "$tmp/render"

# Never mount actual private enterprise certificates in an ordinary CI job.
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -sha256 \
  -subj "/CN=iam-n02.private.example.test" \
  -addext "subjectAltName=DNS:iam-n02.private.example.test" \
  -keyout "$tmp/private/edge/private-key.pem" \
  -out "$tmp/private/edge/fullchain.pem" >/dev/null 2>&1
cp "$tmp/private/edge/fullchain.pem" "$tmp/private/upstream-roots.pem"

# The pinned image runs nonroot by default but the synthetic private fixture
# is 0600. Run the *syntax-only*, no-network, read-only test as container
# root (with ALL Linux capabilities dropped), never in a live ingress.
# N02's exact reviewed edge-image digest, never floating nginx:latest.
image="$(python3 - <<'PY'
import json
from pathlib import Path
path=Path("tests/platform-integration/development/n02-base-lock.json")
lock=json.loads(path.read_text())
assert lock["authority"]=="ADR-SHARED-043"
assert lock["synthetic_only"] is True and lock["protected_acceptance"] is False
image=lock["images"]["edge"]
assert image.startswith("nginx@sha256:") and len(image.rsplit("sha256:", 1)[-1])==64
print(image)
PY
)"
timeout 120 docker run --rm \
  --user 0:0 \
  --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  --entrypoint /usr/sbin/nginx \
  --tmpfs /var/cache/nginx:rw,noexec,nosuid,size=16m \
  --tmpfs /var/run:rw,noexec,nosuid,size=1m \
  --mount "type=bind,src=$tmp/render/nginx.conf,dst=/etc/nginx/nginx.conf,readonly" \
  --mount "type=bind,src=$tmp/private,dst=/run/n02-private,readonly" \
  "$image" -t -c /etc/nginx/nginx.conf

printf '%s\n' "N02_INGRESS_SYNTAX_CHECKED_WITH_PINNED_IMAGE_SOURCE_ONLY"
