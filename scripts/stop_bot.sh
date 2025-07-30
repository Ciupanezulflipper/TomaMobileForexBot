#!/data/data/com.termux/files/usr/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BOT_DIR="$HOME/forex_bot"
PID_FILE="$BOT_DIR/run/bot.pid"

echo -e "${YELLOW}🛑 Stopping Forex Trading Bot...${NC}"

if [ ! -f "$PID_FILE" ]; then
  echo -e "${RED}❌ PID file not found. Bot may not be running.${NC}"
  exit 1
fi

PID=$(cat "$PID_FILE")

if ! ps -p $PID > /dev/null 2>&1; then
  echo -e "${RED}❌ Bot process (PID: $PID) not found${NC}"
  rm -f "$PID_FILE"
  exit 1
fi

echo -e "${BLUE}📨 Sending SIGTERM to bot (PID: $PID)${NC}"
kill -TERM $PID

for i in {1..10}; do
  if ! ps -p $PID > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Bot stopped gracefully${NC}"
    rm -f "$PID_FILE"
    exit 0
  fi
  sleep 1
done

echo -e "${YELLOW}⚠️ Forcing bot shutdown...${NC}"
kill -KILL $PID
sleep 2

if ! ps -p $PID > /dev/null 2>&1; then
  echo -e "${GREEN}✅ Bot stopped (forced)${NC}"
  rm -f "$PID_FILE"
else
  echo -e "${RED}❌ Unable to stop bot${NC}"
  exit 1
fi
