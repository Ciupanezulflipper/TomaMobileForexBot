#!/usr/bin/env bash
# supervise_bot.sh — runs env sync, then starts the bot

set -euo pipefail

# Always sync environment variables before running bot
bash "$(dirname "$0")/env_sync.sh"

# Start the bot (adjust path to your main Python script if needed)
python3 bot.py
