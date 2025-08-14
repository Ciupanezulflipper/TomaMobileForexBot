#!/usr/bin/env bash
set -euo pipefail

SRC="${1:-env.secrets}"

if [ ! -f "$SRC" ]; then
  echo "❌ Missing $SRC (put your keys there)."
  exit 1
fi

# Load every var from the secrets file
set -o allexport
. "$SRC"
set +o allexport

# Require at least the Telegram token
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is required in $SRC}"

# Write .env with ALL keys we care about
cat > .env <<ENV
# generated from $SRC on $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Telegram
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}

# Data Sources
TWELVE_DATA_API_KEY=${TWELVE_DATA_API_KEY:-}
ALPHA_VANTAGE_API_KEY=${ALPHA_VANTAGE_API_KEY:-}
FINNHUB_API_KEY=${FINNHUB_API_KEY:-}
EXCHANGERATE_API_KEY=${EXCHANGERATE_API_KEY:-}
NEWS_API_KEY=${NEWS_API_KEY:-}
MARKETAUX_API_KEY=${MARKETAUX_API_KEY:-}
FMP_API_KEY=${FMP_API_KEY:-}
HETZNER_API_KEY=${HETZNER_API_KEY:-}

# General Bot Settings
SAFE_MODE=${SAFE_MODE:-0}
LOG_LEVEL=${LOG_LEVEL:-WARNING}
LOG_DIR=${LOG_DIR:-logs}
TZ=${TZ:-UTC}
ENV

chmod 600 .env
echo "✅ .env written from $SRC (chmod 600)."
