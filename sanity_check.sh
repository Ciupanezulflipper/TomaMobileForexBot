#!/usr/bin/env bash
set -euo pipefail

green(){ printf "\033[32m%s\033[0m\n" "$*"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$*"; }
red(){ printf "\033[31m%s\033[0m\n" "$*"; }

# 1) Keys present?
echo "== [1/4] Keys present? =="
for k in EODHD_API_KEY TWELVE_DATA_API_KEY ALPHA_VANTAGE_API_KEY TELEGRAM_BOT_TOKEN; do
  if [ -n "${!k-}" ]; then green "$k: SET"; else yellow "$k: MISSING"; fi
done
echo

# Helper to curl with timeout and trim
curlj(){ curl -sS --max-time 10 "$1" || true; }

# 2) EODHD checks (free endpoints we already verified work)
echo "== [2/4] EODHD checks =="
if [ -n "${EODHD_API_KEY-}" ]; then
  # Stock realtime (TSLA)
  RES="$(curlj "https://eodhd.com/api/real-time/TSLA?api_token=${EODHD_API_KEY}&fmt=json")"
  if printf '%s' "$RES" | grep -q '"code":"TSLA'; then
    green "Stock realtime OK  -> $(printf '%s' "$RES" | cut -c1-160)…"
  else
    red   "Stock realtime FAIL -> $(printf '%s' "$RES" | head -n1)"
  fi
  # (Forex candles gives HTML on free tier; skip to avoid false red)
else
  yellow "SKIP EODHD (key missing)"
fi
echo

# 3) TwelveData FX (EUR/USD 1m, 1 bar)
echo "== [3/4] TwelveData EUR/USD 1m (1 bar) =="
if [ -n "${TWELVE_DATA_API_KEY-}" ]; then
  RES="$(curlj "https://api.twelvedata.com/time_series?symbol=EUR/USD&interval=1min&outputsize=1&apikey=${TWELVE_DATA_API_KEY}")"
  if printf '%s' "$RES" | grep -q '"values"'; then
    green "OK -> $(printf '%s' "$RES" | cut -c1-160)…"
  else
    red   "FAIL -> $(printf '%s' "$RES" | head -n1)"
  fi
else
  yellow "SKIP TwelveData (key missing)"
fi
echo

# 4) Telegram ping (optional)
echo "== [4/4] Telegram ping (optional) =="
if [ -n "${TELEGRAM_BOT_TOKEN-}" ] && [ -n "${TELEGRAM_CHAT_ID-}" ]; then
  MSG="Ping OK — Telegram reachable."
  RES="$(curl -sS --max-time 10 -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" -d text="${MSG}" -d disable_web_page_preview=true || true)"
  if printf '%s' "$RES" | grep -q '"ok":true'; then green "OK"; else red "FAIL -> $RES"; fi
else
  yellow "SKIP (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to test)"
fi
