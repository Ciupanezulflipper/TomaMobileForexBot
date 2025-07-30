#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BOT_DIR="$HOME/forex_bot"
LOG_FILE="$BOT_DIR/logs/startup.log"

echo -e "${BLUE}🚀 Starting Forex Trading Bot...${NC}"

# Create log directory
mkdir -p "$BOT_DIR/logs"

# Function to log with timestamp
log_message() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Check .env file
if [ ! -f "$BOT_DIR/.env" ]; then
  echo -e "${RED}❌ .env file not found${NC}"
  echo -e "${YELLOW}💡 Please create it using: nano $BOT_DIR/.env${NC}"
  exit 1
fi

# Check Python installation
if ! command -v python &> /dev/null; then
  echo -e "${RED}❌ Python not found${NC}"
  echo -e "${YELLOW}💡 Install with: pkg install python${NC}"
  exit 1
fi

# Check Python dependencies using import
log_message "Checking Python dependencies..."
python3 -c "import telegram, dotenv" 2>/dev/null
if [ $? -ne 0 ]; then
  echo -e "${RED}❌ Missing Python dependencies: python-telegram-bot or python-dotenv${NC}"
  echo -e "${YELLOW}💡 Install with: pip install python-telegram-bot python-dotenv${NC}"
  exit 1
else
  echo -e "${GREEN}✅ Python dependencies OK${NC}"
fi

# Run the bot
python3 "$BOT_DIR/main.py"
