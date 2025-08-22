#!/usr/bin/env bash
bash tools/env_sync.sh
# tools/cron_health.sh — run periodic health checks in a loop
set -euo pipefail

DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
ROOT="$(cd -- "$DIR/.." &>/dev/null && pwd)"
LOG_DIR="$ROOT/logs"
HC_LOG="$LOG_DIR/health_cron.log"
INTERVAL="${1:-86400}"    # default: 24h; pass 43200 for 12h, 21600 for 6h, etc.

mkdir -p "$LOG_DIR"

echo "------------------------------"            | tee -a "$HC_LOG"
echo "[cron] start $(date -u +"%Y-%m-%d %H:%M:%SZ")" | tee -a "$HC_LOG"
echo "[cron] interval: ${INTERVAL}s"            | tee -a "$HC_LOG"

# Ensure project imports work if health_check uses local modules later
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

while :; do
  echo "[cron] run $(date -u +"%Y-%m-%d %H:%M:%SZ")" | tee -a "$HC_LOG"
  # sync env every run; use JSON for compact machine-readable output
  bash "$DIR/run_health_check.sh" --json 2>&1 | tee -a "$HC_LOG"
  echo "[cron] sleep ${INTERVAL}s"               | tee -a "$HC_LOG"
  sleep "$INTERVAL"
done
