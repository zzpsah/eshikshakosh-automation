#!/usr/bin/env bash
set -euo pipefail

REPO="${HOME}/projects/eshikshakosh-automation"
SKILL_SRC="${REPO}/skills/eshikshakosh-otr/SKILL.md"
SKILL_DST="${HOME}/.hermes/skills/eshikshakosh-otr"
BIN_DST="${HOME}/.local/bin"
WRAPPER="${BIN_DST}/eshikshakosh-report"
RUN_HELPER_SRC="${REPO}/local-script/eshikshakosh-run.sh"
RUN_HELPER_DST="${BIN_DST}/eshikshakosh-run"

if [[ ! -f "$SKILL_SRC" ]]; then
  echo "ERROR: skill source missing: $SKILL_SRC" >&2
  exit 2
fi

mkdir -p "$SKILL_DST" "$BIN_DST"
chmod 700 "$BIN_DST"

install -m 600 "$SKILL_SRC" "$SKILL_DST/SKILL.md"
install -m 700 "$RUN_HELPER_SRC" "$RUN_HELPER_DST"

cat > "$WRAPPER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO="${HOME}/projects/eshikshakosh-automation"
RUNNER="${REPO}/local-script/run_report.sh"
YEAR=""
MODE="full"
CLASS=""
SECTION=""
STREAM=""
SPLIT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --year) YEAR="${2:-}"; shift 2 ;;
    --mode) MODE="${2:-}"; shift 2 ;;
    --class) CLASS="${2:-}"; shift 2 ;;
    --section) SECTION="${2:-}"; shift 2 ;;
    --stream) STREAM="${2:-}"; shift 2 ;;
    --split-sheets) SPLIT=1; shift ;;
    full|masked) MODE="$1"; shift ;;
    [0-9][0-9][0-9][0-9]-[0-9][0-9]) YEAR="$1"; shift ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ "$MODE" != "full" && "$MODE" != "masked" ]]; then
  echo "ERROR: mode must be full or masked" >&2
  exit 2
fi
[[ -x "$RUNNER" ]] || { echo "ERROR: report runner missing or not executable: $RUNNER" >&2; exit 2; }

[[ -n "$YEAR" ]] && export ESHIKSHAKOSH_YEAR="$YEAR" || unset ESHIKSHAKOSH_YEAR || true
export ESHIKSHAKOSH_EXPORT_MODE="$MODE"
export ESHIKSHAKOSH_CLASS="$CLASS"
export ESHIKSHAKOSH_SECTION="$SECTION"
export ESHIKSHAKOSH_STREAM="$STREAM"
export ESHIKSHAKOSH_SPLIT_SHEETS="$SPLIT"
exec "${HOME}/.local/bin/eshikshakosh-run" "$RUNNER"
EOF

chmod 700 "$WRAPPER"
chmod 700 "$REPO/local-script/run_report.sh"

echo "SKILL_INSTALLED=$SKILL_DST/SKILL.md"
echo "COMMAND_INSTALLED=$WRAPPER"
echo "READY"
