#!/usr/bin/env bash
# School Data Desk job service launcher.
#
# Runs the authenticated report job service on the Oracle VPS. The Vercel app
# calls this service; the service invokes the existing read-only runners.
#
# Required env:
#   JOB_SERVER_TOKEN   shared secret the Vercel app presents as a bearer token
#
# Optional env:
#   JOB_SERVER_HOST    default 127.0.0.1
#   JOB_SERVER_PORT    default 8787
#   JOB_SERVER_TIMEOUT default 900 (seconds per runner)

set -euo pipefail

REPO="${HOME}/projects/eshikshakosh-automation"
PY="${REPO}/.venv/bin/python"
APP="${REPO}/shared/jobserver/server.py"

if [[ -z "${JOB_SERVER_TOKEN:-}" ]]; then
  echo "ERROR: JOB_SERVER_TOKEN is not set" >&2
  exit 2
fi

if [[ ! -f "$APP" ]]; then
  echo "ERROR: job service missing: $APP" >&2
  exit 2
fi

cd "$REPO"
exec "$PY" "$APP"
