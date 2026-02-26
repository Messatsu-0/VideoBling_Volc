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

# Allow running deployment scripts under service users (e.g. GitHub self-hosted runner)
# even when repository ownership differs from the process user.
git config --global --add safe.directory "$ROOT_DIR" >/dev/null 2>&1 || true

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Error: missing $ENV_FILE"
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

TARGET_REF="${1:-${DEPLOY_BRANCH:-main}}"

echo "Fetching latest code..."
git fetch --all --tags --prune

if git show-ref --verify --quiet "refs/remotes/origin/$TARGET_REF"; then
  if git show-ref --verify --quiet "refs/heads/$TARGET_REF"; then
    git checkout "$TARGET_REF"
    git pull --ff-only origin "$TARGET_REF"
  else
    git checkout -B "$TARGET_REF" "origin/$TARGET_REF"
  fi
elif git rev-parse -q --verify "$TARGET_REF^{commit}" >/dev/null; then
  git checkout --detach "$TARGET_REF"
else
  echo "Error: target ref not found: $TARGET_REF"
  exit 1
fi

echo "Rebuilding and restarting containers..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build

echo
echo "Current version:"
git log -1 --oneline
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

if [[ -x "$ROOT_DIR/scripts/print_access_url.sh" ]]; then
  "$ROOT_DIR/scripts/print_access_url.sh" || true
fi
