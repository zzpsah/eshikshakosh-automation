#!/usr/bin/env bash
# Bitwarden-backed, browser-authenticated read-only e-ShikshaKosh teacher DETAIL export.
#
# Same credential paths as run_teacher_report.sh; the difference is the extractor, which
# also pulls each teacher's registration, education, professional, other, training and
# service-history sections.
#
#   local-script/run_teacher_detail_report.sh --school Sahaspur
#   local-script/run_teacher_detail_report.sh --udise 10130106304 --username <login> --password <pw>
#   ESHIKSHAKOSH_DETAIL_LIMIT=2 local-script/run_teacher_detail_report.sh --school Sahaspur   # smoke test
#
# Secret values are never printed.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="${REPO}/.venv/bin/python"
EXTRACTOR="${REPO}/local-script/esk_teacher_detail_extract.py"
REGISTRY="${REPO}/local-script/esk_schools.py"
cd "$REPO"

[[ -x "$PY" ]] || { echo "ERROR: virtualenv python missing: $PY" >&2; exit 2; }
[[ -f "$EXTRACTOR" ]] || { echo "ERROR: extractor missing: $EXTRACTOR" >&2; exit 2; }

SCHOOL=""
LIST_ONLY=0
UDISE_ARG=""
USERNAME_ARG=""
PASSWORD_ARG=""
USER_KEY_ARG=""
PASS_KEY_ARG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --school|-s)   SCHOOL="${2:-}"; shift 2 ;;
    --udise)       UDISE_ARG="${2:-}"; shift 2 ;;
    --username|-u) USERNAME_ARG="${2:-}"; shift 2 ;;
    --password|-p) PASSWORD_ARG="${2:-}"; shift 2 ;;
    --user-key)    USER_KEY_ARG="${2:-}"; shift 2 ;;
    --pass-key)    PASS_KEY_ARG="${2:-}"; shift 2 ;;
    --list|-l)     LIST_ONLY=1; shift ;;
    -h|--help)     sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ "$LIST_ONLY" == "1" ]]; then
  [[ -f "$REGISTRY" ]] || { echo "ERROR: school registry missing: $REGISTRY" >&2; exit 2; }
  "$PY" - "$REGISTRY" <<'PYEOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("esk_schools", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("Known schools:")
for s in mod.list_schools():
    print(f"  {s['key']:<16} UDISE {s['udise']}   aliases: {', '.join(s['aliases'])}")
PYEOF
  exit 0
fi

# Path A: direct one-time credentials (registered school or not)
if [[ -n "$USERNAME_ARG" || -n "$PASSWORD_ARG" ]]; then
  if [[ -z "$USERNAME_ARG" || -z "$PASSWORD_ARG" ]]; then
    echo "ERROR: --username and --password must be given together" >&2
    exit 2
  fi
  if [[ -z "$UDISE_ARG" ]]; then
    echo "ERROR: --udise is required (or use --school <name> for a registered school)" >&2
    exit 2
  fi
  export ESHIKSHAKOSH_TARGET_UDISE="$UDISE_ARG"
  export ESHIKSHAKOSH_USERNAME="$USERNAME_ARG"
  export ESHIKSHAKOSH_PASSWORD="$PASSWORD_ARG"
  exec "$PY" -u "$EXTRACTOR"
fi

if [[ -n "${ESHIKSHAKOSH_USERNAME:-}" && -n "${ESHIKSHAKOSH_PASSWORD:-}" ]]; then
  if [[ -z "$UDISE_ARG" ]]; then
    echo "ERROR: --udise is required when using ESHIKSHAKOSH_USERNAME/PASSWORD" >&2
    exit 2
  fi
  export ESHIKSHAKOSH_TARGET_UDISE="$UDISE_ARG"
  exec "$PY" -u "$EXTRACTOR"
fi

# Path B: Bitwarden-backed (registered school, or explicit key names)
if [[ -n "$USER_KEY_ARG" || -n "$PASS_KEY_ARG" ]]; then
  if [[ -z "$UDISE_ARG" || -z "$USER_KEY_ARG" || -z "$PASS_KEY_ARG" ]]; then
    echo "ERROR: --user-key/--pass-key require --udise as well" >&2
    exit 2
  fi
else
  [[ -f "$REGISTRY" ]] || { echo "ERROR: school registry missing: $REGISTRY" >&2; exit 2; }
  if [[ -z "$SCHOOL" ]]; then
    SCHOOL="${ESHIKSHAKOSH_SCHOOL:-Sahaspur}"
  fi
  resolved="$("$PY" - "$REGISTRY" "$SCHOOL" <<'PYEOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("esk_schools", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
entry = mod.find(sys.argv[2])
if not entry:
    print(f"ERROR: unknown school '{sys.argv[2]}'. Run with --list.", file=sys.stderr)
    raise SystemExit(3)
print(entry["udise"], entry["username_key"], entry["password_key"])
PYEOF
  )" || exit 3
  read -r UDISE_ARG USER_KEY_ARG PASS_KEY_ARG <<< "$resolved"
fi

export ESHIKSHAKOSH_TARGET_UDISE="$UDISE_ARG"

exec "$HOME/.local/bin/secret-run-scoped" \
  "ESHIKSHAKOSH_USERNAME=$USER_KEY_ARG" \
  "ESHIKSHAKOSH_PASSWORD=$PASS_KEY_ARG" \
  -- "$PY" -u "$EXTRACTOR"
