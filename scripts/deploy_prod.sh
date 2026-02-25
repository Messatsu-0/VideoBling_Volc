#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yml"
ENV_FILE="$ROOT_DIR/.env.prod"
ENV_EXAMPLE="$ROOT_DIR/.env.prod.example"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: command not found: $cmd"
    exit 1
  fi
}

require_cmd docker
require_cmd git

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Error: missing compose file: $COMPOSE_FILE"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ -f "$ENV_EXAMPLE" ]]; then
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "Created $ENV_FILE from template. Edit it before deployment."
  else
    echo "Error: missing $ENV_FILE"
  fi
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

RUNTIME_DIR="${RUNTIME_DIR:-$ROOT_DIR/runtime}"
BASIC_AUTH_FILE="${BASIC_AUTH_FILE:-$ROOT_DIR/deploy/gateway/.htpasswd}"

mkdir -p "$RUNTIME_DIR/jobs"
mkdir -p "$(dirname "$BASIC_AUTH_FILE")"

if [[ ! -f "$BASIC_AUTH_FILE" ]]; then
  cp "$ROOT_DIR/deploy/gateway/.htpasswd.example" "$BASIC_AUTH_FILE"
  echo "Generated default auth file: $BASIC_AUTH_FILE"
  echo "Please replace it with your own username/password before exposing to internet."
fi

echo "Deploying VideoBling production stack..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build

echo
echo "Containers:"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
echo
echo "Deployment done."
if [[ -x "$ROOT_DIR/scripts/print_access_url.sh" ]]; then
  "$ROOT_DIR/scripts/print_access_url.sh" || true
elif [[ -n "$HOST_IP" ]]; then
  echo "Access URL: http://$HOST_IP"
else
  echo "Access URL: http://<EIP>"
fi
