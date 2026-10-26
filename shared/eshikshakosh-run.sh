#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: eshikshakosh-run COMMAND [ARGS...]" >&2
    exit 1
fi

# bws-run breaks -c flags (treats quoted code as shell commands).
# If child is "python3 -c <code>", extract code to temp file.
if [[ "${1:-}" == "python3" && "${2:-}" == "-c" && -n "${3:-}" ]]; then
    _code="${3}"
    _codefile=$(mktemp)
    printf '%s\n' "$_code" > "$_codefile"
    chmod +x "$_codefile"
    trap 'rm -f "$_codefile"' EXIT
    set -- python3 "$_codefile" "${@:4}"
fi

# Write environment setup script to temp file (script-file approach works with bws-run)
_tmpenv=$(mktemp)
trap 'rm -f "$_tmpenv"' EXIT

cat > "$_tmpenv" <<'INNEREOF'
#!/bin/sh
set -eu

SCHOOL="${ESHIKSHAKOSH_SCHOOL:-Tetahali}"
case "$SCHOOL" in
    Sahaspur|UMV_SAHASPUR)
        USERNAME="${ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_USERNAME:-}"
        PASSWORD="${ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_PASSWORD:-}"
        ;;
    Tetahali|UMV_TETAHALI)
        USERNAME="${ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_USERNAME:-}"
        PASSWORD="${ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_PASSWORD:-}"
        ;;
    *) echo "ERROR: unknown school key; select Sahaspur or Tetahali." >&2; exit 2 ;;
esac

if [ -z "$USERNAME" ]; then
    echo "ERROR: eShikshakosh username secret is missing or empty." >&2
    exit 1
fi

if [ -z "$PASSWORD" ]; then
    echo "ERROR: eShikshakosh password secret is missing or empty." >&2
    exit 1
fi

export ESHIKSHAKOSH_USERNAME="$USERNAME"
export ESHIKSHAKOSH_PASSWORD="$PASSWORD"

unset ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_USERNAME
unset ESHIKSHAKOSH_UMV_SAHASPUR_OPERATOR_PASSWORD
unset ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_USERNAME
unset ESHIKSHAKOSH_UMV_TETAHALI_SCHOOL_PASSWORD
unset ESHIKSHAKOSH_SCHOOL

exec "$@"
INNEREOF

chmod +x "$_tmpenv"

exec "${HOME}/.local/bin/secret-run" sh "$_tmpenv" "$@"
