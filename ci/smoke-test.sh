#!/usr/bin/env bash
# Smoke-tests the runtime image (Dockerfile target `app`). Used by CI and the release
# workflow; runs locally too (needs Docker and curl):
#
#   ci/smoke-test.sh <image-ref> [platform] [expected-version]
#
# Checks that the CLI starts and reports the version, that the worker's settings load, and
# that the API starts and serves the dashboard: the SPA with its client-side-routing
# fallback, and JSON for /api. Neither needs a database for that (the API connects lazily),
# so placeholder settings are enough; /healthz, which pings the database, must report 503.
set -euo pipefail

ref=${1:?image reference}
platform=${2:-}
expected=${3:-}

platform_args=()
[[ -n "$platform" ]] && platform_args=(--platform "$platform")

fail() {
  echo "::error::$ref${platform:+ ($platform)}: $*" >&2
  exit 1
}

check() { # path expected-status expected-content-type-prefix
  local result
  result=$(curl -s -o /dev/null -w '%{http_code} %{content_type}' "$base$1")
  [[ "$result" == "$2 $3"* ]] || fail "GET $1 returned '$result', expected '$2 $3...'"
  echo "GET $1 -> $result"
}

docker run --rm "${platform_args[@]}" "$ref" copilot-metrics --help >/dev/null
reported=$(docker run --rm "${platform_args[@]}" "$ref" copilot-metrics --version)
if [[ -n "$expected" && "$reported" != "copilot-metrics $expected" ]]; then
  fail "reports '$reported', expected 'copilot-metrics $expected'"
fi

# The worker gets only its own settings (as in deploy/compose.yaml); nothing baked into the
# image may make them fail validation (e.g. an image-wide API_* variable).
docker run --rm "${platform_args[@]}" \
  -e GITHUB_ORG=smoke-test \
  -e WORKER_DATABASE_URL=postgresql://smoke:smoke@db.invalid:5432/smoke \
  "$ref" python -c 'from copilot_metrics.settings import get_settings; get_settings().require_worker()' \
  || fail "worker settings do not load"
echo "worker settings -> OK"

name="smoke-$$"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" "${platform_args[@]}" -p 127.0.0.1::8000 \
  -e GITHUB_ORG=smoke-test \
  -e GITHUB_APP_CLIENT_ID=smoke-test \
  -e GITHUB_APP_CLIENT_SECRET=smoke-test \
  -e API_DATABASE_URL=postgresql://smoke:smoke@db.invalid:5432/smoke \
  -e API_STATIC_DIR=/app/static \
  -e SESSION_SECRET=0123456789abcdef0123456789abcdef \
  "$ref" >/dev/null
port=$(docker port "$name" 8000/tcp | head -n1 | sed 's/.*://')
base="http://127.0.0.1:$port"
# Up = serving; /healthz can't be the signal, there is no database here.
for _ in $(seq 90); do # slow under QEMU
  curl -fs "$base/api/config" >/dev/null && break
  sleep 1
done
curl -fs "$base/api/config" >/dev/null || { docker logs "$name" >&2; fail "API not up after 90 s"; }

check /healthz 503 text/plain # the database is unreachable, and the health check says so
check / 200 text/html
check /admin/members 200 text/html # client-side route -> index.html
check /api/config 200 application/json
check /api/no-such-endpoint 404 application/json

echo "OK: $reported"
