set -e
set -a
#!/bin/bash
set -e
if [ -f ".env" ]; then
  # shellcheck disable=SC1091
  source .env
else
  echo "Error: .env file not found in $(pwd)"
  exit 1
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
  echo "Error: TELEGRAM_BOT_TOKEN missing from .env"
  exit 1
fi

if [ -z "$FINNHUB_KEY" ] && [ -z "$TWELVE_DATA_API_KEY" ] && [ -z "$ALPHA_VANTAGE_API_KEY" ]; then
  echo "Error: No API keys found in .env (need at least one of FINNHUB_KEY / TWELVE_DATA_API_KEY / ALPHA_VANTAGE_API_KEY)"
  exit 1
fi

echo "Starting bot with keys loaded..."
python3 main.py
set +a
python3 main.py
