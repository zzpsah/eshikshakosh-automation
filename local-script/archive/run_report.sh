#!/usr/bin/env bash
set -euo pipefail

REPO="${HOME}/projects/eshikshakosh-automation"
PY="${REPO}/.venv/bin/python"
APP="${REPO}/local-script/esk_otr_api.py"
EXPORT_MODE="${ESHIKSHAKOSH_EXPORT_MODE:-full}"

CLASS_FILTER="${ESHIKSHAKOSH_CLASS:-}"
SECTION_FILTER="${ESHIKSHAKOSH_SECTION:-}"
STREAM_FILTER="${ESHIKSHAKOSH_STREAM:-}"
SPLIT_SHEETS="${ESHIKSHAKOSH_SPLIT_SHEETS:-0}"

extra_args=()
[[ -n "$CLASS_FILTER" ]] && extra_args+=(--class "$CLASS_FILTER")
[[ -n "$SECTION_FILTER" ]] && extra_args+=(--section "$SECTION_FILTER")
[[ -n "$STREAM_FILTER" ]] && extra_args+=(--stream "$STREAM_FILTER")
[[ "$SPLIT_SHEETS" == "1" ]] && extra_args+=(--split-sheets)
if [[ "$EXPORT_MODE" != "full" && "$EXPORT_MODE" != "masked" ]]; then
  echo "ERROR: ESHIKSHAKOSH_EXPORT_MODE must be full or masked" >&2
  exit 2
fi

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

find "$REPO" -maxdepth 1 -type f -name 'Student_Details_*.xlsx' -printf '%f\n' | sort > "$before"

"$PY" "$APP" \
  --udise "$ESHIKSHAKOSH_USERNAME" \
  --password "$ESHIKSHAKOSH_PASSWORD" \
  --year "$YEAR" \
  --export-mode "$EXPORT_MODE" \
  "${extra_args[@]}"

find "$REPO" -maxdepth 1 -type f -name 'Student_Details_*.xlsx' -printf '%f\n' | sort > "$after"

report="$(comm -13 "$before" "$after" | tail -n 1)"

if [[ -z "$report" ]]; then
  report="$(find "$REPO" -maxdepth 1 -type f -name 'Student_Details_*.xlsx' -printf '%T@ %f\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
fi

if [[ -z "$report" || ! -f "$REPO/$report" ]]; then
  echo "ERROR: report file was not found after successful script execution" >&2
  exit 4
fi

printf 'EXPORT_MODE=%s\n' "${EXPORT_MODE^^}"
printf 'REPORT_READY=%s\n' "$REPO/$report"
