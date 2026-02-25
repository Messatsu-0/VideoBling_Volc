#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

docker compose up -d --build

echo "VideoBling containers started:"
echo "- Web: http://localhost:5173"
echo "- API: http://localhost:18000/api/health"
