#!/usr/bin/env bash
set -euo pipefail

echo "▶ Creating .env locally (never committed)…"
read -rsp "TELEGRAM_BOT_TOKEN: " TG; echo
read -rsp "FINNHUB_KEY (optional, Enter to skip): " FH; echo
read -rsp "TWELVE_DATA_API_KEY (optional, Enter to skip): " TD; echo
read -rsp "ALPHA_VANTAGE_API_KEY (optional, Enter to skip): " AV; echo

# Minimal validation
if [ -z "$TG" ]; then
  echo "❌ TELEGRAM_BOT_TOKEN is required."; exit 1
fi

cat > .env <<ENVEOF
TELEGRAM_BOT_TOKEN=$TG
FINNHUB_KEY=$FH
TWELVE_DATA_API_KEY=$TD
ALPHA_VANTAGE_API_KEY=$AV

# Optional settings
SAFE_MODE=0
LOG_LEVEL=WARNING
LOG_DIR=logs
TZ=UTC
ENVEOF

chmod 600 .env
echo "✅ .env written (chmod 600)."
