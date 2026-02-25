#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.prod"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

PUBLIC_IP="${PUBLIC_EIP:-}"

if [[ -z "$PUBLIC_IP" ]]; then
  PUBLIC_IP="$(curl -4 -s --max-time 3 https://api.ipify.org || true)"
fi

if [[ -z "$PUBLIC_IP" ]]; then
  PUBLIC_IP="$(curl -4 -s --max-time 3 https://ifconfig.me || true)"
fi

echo
if [[ -n "$PUBLIC_IP" ]]; then
  echo "Public URL: http://${PUBLIC_IP}"
else
  echo "Public URL: http://<EIP>"
  echo "Tip: set PUBLIC_EIP in .env.prod for stable output."
fi

echo "Gateway check (local):"
if curl -s -o /dev/null -I -w "%{http_code}\n" "http://127.0.0.1:${GATEWAY_PORT:-80}" >/tmp/videobling_gateway_status.txt 2>/dev/null; then
  cat /tmp/videobling_gateway_status.txt
else
  echo "unreachable"
fi
