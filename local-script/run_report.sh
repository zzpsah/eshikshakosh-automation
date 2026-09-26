#!/usr/bin/env bash
set -euo pipefail

REPO="${HOME}/projects/eshikshakosh-automation"
PY="${REPO}/.venv/bin/python"
APP="${REPO}/local-script/esk_otr_api.py"
if [[ -n "${ESHIKSHAKOSH_YEAR:-}" ]]; then
  YEAR="$ESHIKSHAKOSH_YEAR"
else
  current_year="$(date +%Y)"
  current_month="$(date +%m)"
  if (( 10#$current_month >= 4 )); then
    start_year="$current_year"
  else
    start_year="$((current_year - 1))"
  fi
  next_short="$(printf '%02d' $(((start_year + 1) % 100)))"
  YEAR="${start_year}-${next_short}"
fi

cd "$REPO"

if [[ ! -x "$PY" ]]; then
  echo "ERROR: virtualenv python missing: $PY" >&2
  exit 2
fi

if [[ ! -f "$APP" ]]; then
  echo "ERROR: report script missing: $APP" >&2
  exit 2
fi

if [[ -z "${ESHIKSHAKOSH_USERNAME:-}" ]]; then
  echo "ERROR: ESHIKSHAKOSH_USERNAME is missing" >&2
  exit 3
fi

if [[ -z "${ESHIKSHAKOSH_PASSWORD:-}" ]]; then
  echo "ERROR: ESHIKSHAKOSH_PASSWORD is missing" >&2
  exit 3
fi

before="$(mktemp)"
after="$(mktemp)"
trap 'rm -f "$before" "$after"' EXIT

find "$REPO" -maxdepth 1 -type f -name 'Student_OTR_Report_*.xlsx' -printf '%f\n' | sort > "$before"

"$PY" "$APP" \
  --udise "$ESHIKSHAKOSH_USERNAME" \
  --password "$ESHIKSHAKOSH_PASSWORD" \
  --year "$YEAR"

find "$REPO" -maxdepth 1 -type f -name 'Student_OTR_Report_*.xlsx' -printf '%f\n' | sort > "$after"

report="$(comm -13 "$before" "$after" | tail -n 1)"

if [[ -z "$report" ]]; then
  report="$(find "$REPO" -maxdepth 1 -type f -name 'Student_OTR_Report_*.xlsx' -printf '%T@ %f\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
fi

if [[ -z "$report" || ! -f "$REPO/$report" ]]; then
  echo "ERROR: report file was not found after successful script execution" >&2
  exit 4
fi

printf 'REPORT_READY=%s\n' "$REPO/$report"
