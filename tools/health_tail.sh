#!/usr/bin/env bash
# tools/health_tail.sh — follow health_check log
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." &>/dev/null && pwd)"
LOG="$ROOT/logs/health_check.log"
[[ -f "$LOG" ]] || { echo "No log yet: $LOG"; exit 1; }
tail -n 200 -F "$LOG"
