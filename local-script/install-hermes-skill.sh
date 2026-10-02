#!/usr/bin/env bash
set -euo pipefail

REPO="${HOME}/projects/eshikshakosh-automation"
SKILL_SRC="${REPO}/skills/eshikshakosh-otr/SKILL.md"
SKILL_DST="${HOME}/.hermes/skills/eshikshakosh-otr"
BIN_DST="${HOME}/.local/bin"
WRAPPER="${BIN_DST}/eshikshakosh-report"

if [[ ! -f "$SKILL_SRC" ]]; then
  echo "ERROR: skill source missing: $SKILL_SRC" >&2
  exit 2
fi

mkdir -p "$SKILL_DST" "$BIN_DST"
chmod 700 "$BIN_DST"

install -m 600 "$SKILL_SRC" "$SKILL_DST/SKILL.md"

cat > "$WRAPPER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO="${HOME}/projects/eshikshakosh-automation"
RUNNER="${REPO}/local-script/run_report.sh"
YEAR="${1:-}"
MODE="${2:-full}"

if [[ "$MODE" != "full" && "$MODE" != "masked" ]]; then
  echo "ERROR: mode must be full or masked" >&2
  exit 2
fi

if [[ ! -x "$RUNNER" ]]; then
  echo "ERROR: report runner missing or not executable: $RUNNER" >&2
  exit 2
fi

if [[ -n "$YEAR" ]]; then
  export ESHIKSHAKOSH_YEAR="$YEAR"
else
  unset ESHIKSHAKOSH_YEAR || true
fi
export ESHIKSHAKOSH_EXPORT_MODE="$MODE"
exec eshikshakosh-run "$RUNNER"
EOF

chmod 700 "$WRAPPER"
chmod 700 "$REPO/local-script/run_report.sh"

echo "SKILL_INSTALLED=$SKILL_DST/SKILL.md"
echo "COMMAND_INSTALLED=$WRAPPER"
echo "READY"
