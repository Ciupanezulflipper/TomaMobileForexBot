#!/usr/bin/env bash
# env_sync.sh — load .env and normalize API keys so the bot always sees them.

set -euo pipefail

# 1) Move to repo root (script lives in tools/, we want project root)
cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null || true

# 2) Load .env if present so its variables become exported to the environment
if [ -f .env ]; then
  # export everything loaded from .env
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  echo "[env_sync] WARNING: .env not found in $(pwd)"
fi

# 3) Normalize/alias incoming keys → canonical names, keep both for compatibility

# Telegram
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${BOT_TOKEN:-}}"

# Finnhub
export FINNHUB_API_KEY="${FINNHUB_API_KEY:-${FINNHUB_KEY:-${FINNHUB_TOKEN:-}}}"
export FINNHUB_KEY="${FINNHUB_API_KEY}"
export FINNHUB_KEY="${FINNHUB_API_KEY:-${FINNHUB_KEY:-}}"

# Alpha Vantage
export ALPHA_VANTAGE_API_KEY="${ALPHA_VANTAGE_API_KEY:-${ALPHAVANTAGE_API_KEY:-${ALPHA_API_KEY:-}}}"

# Twelve Data
export TWELVE_DATA_API_KEY="${TWELVE_DATA_API_KEY:-${TWELVEDATA_API_KEY:-${TWELVE_API_KEY:-}}}"

# 4) Summary
echo "======== ENV SUMMARY ========"
for k in TELEGRAM_BOT_TOKEN FINNHUB_API_KEY FINNHUB_KEY TWELVE_DATA_API_KEY ALPHA_VANTAGE_API_KEY; do
  if [ -n "${!k-}" ]; then
    echo "$k: SET"
  else
    echo "$k: MISSING"
  fi
done
export FINNHUB_KEY="$FINNHUB_API_KEY"
