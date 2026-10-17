#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "${HOME}/.local/bin/eshikshakosh-report" "$1"
else
  exec "${HOME}/.local/bin/eshikshakosh-report"
fi
