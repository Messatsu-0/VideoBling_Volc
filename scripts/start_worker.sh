#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

source .venv/bin/activate
export PYTHONPATH="$ROOT_DIR/backend"
python -m huey.bin.huey_consumer app.workers.queue.huey -w 1
