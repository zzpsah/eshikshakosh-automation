#!/usr/bin/env bash
# School Data Desk — private report gateway launcher.
#
# Runs the FastAPI gateway that the Vercel app calls. The gateway owns the job
# service bearer token and the portal credentials; the browser only ever sees
# signed, single-use download links.
#
#   Default bind is 127.0.0.1:8788 — reachable only from this machine, and from
#   the tailnet through `tailscale serve` (see docs/WEB-DEPLOYMENT.md). Serving
#   student data publicly needs an explicit `allow_public=true` in config.json
#   plus a real tunnel; the launcher refuses otherwise.
#
# Required env:   none (config.json holds the tokens)
# Optional env:   GATEWAY_HOST (default 127.0.0.1), GATEWAY_PORT (default 8788)

set -euo pipefail

REPO="${HOME}/projects/eshikshakosh-automation"
PY="${REPO}/.venv/bin/python"
APP="${REPO}/shared/gateway/server.py"
CONFIG="${REPO}/shared/gateway/config.json"

[[ -x "$PY" ]] || { echo "ERROR: virtualenv python missing: $PY" >&2; exit 2; }
[[ -f "$APP" ]] || { echo "ERROR: gateway missing: $APP" >&2; exit 2; }

cd "$REPO"

if [[ ! -f "$CONFIG" ]]; then
  echo "INFO: no config yet — writing a starter ${CONFIG}"
  "$PY" "$APP" --init
  echo "INFO: edit it and set job_token to the real job service token."
fi

HOST="${GATEWAY_HOST:-127.0.0.1}"
PORT="${GATEWAY_PORT:-8788}"

exec "$PY" "$APP" --host "$HOST" --port "$PORT"
