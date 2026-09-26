#!/usr/bin/env bash
set -euo pipefail

YEAR="${1:-2026-27}"
exec "${HOME}/.local/bin/eshikshakosh-report" "$YEAR"
