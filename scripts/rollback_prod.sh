#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yml"
ENV_FILE="$ROOT_DIR/.env.prod"

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: command not found: $cmd"
    exit 1
  fi
}

require_cmd docker
require_cmd git

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <git-ref-or-tag>"
  exit 1
fi

TARGET_REF="$1"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: missing $ENV_FILE"
  exit 1
fi

echo "Fetching refs..."
git fetch --all --tags --prune

if ! git rev-parse -q --verify "$TARGET_REF^{commit}" >/dev/null; then
  echo "Error: ref not found: $TARGET_REF"
  exit 1
fi

git checkout --detach "$TARGET_REF"

echo "Rebuilding and restarting containers from $TARGET_REF..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build

echo
echo "Rollback complete:"
git log -1 --oneline
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

if [[ -x "$ROOT_DIR/scripts/print_access_url.sh" ]]; then
  "$ROOT_DIR/scripts/print_access_url.sh" || true
fi
