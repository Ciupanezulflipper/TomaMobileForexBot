#!/data/data/com.termux/files/usr/bin/bash
bash tools/env_sync.sh
set -euo pipefail

WORKDIR="$HOME/TomaMobileForexBot"
LOGDIR="$WORKDIR/logs"
LOGFILE="$LOGDIR/bot.log"

mkdir -p "$LOGDIR"
cd "$WORKDIR"

# load secrets for each run
if [ -f .env ]; then
  # shellcheck disable=SC1091
  source .env
fi

echo "[supervise] starting loop at $(date -u +"%Y-%m-%d %H:%M:%SZ")" | tee -a "$LOGFILE"

# restart loop
while true; do
  echo "------------------------------------------------------------" | tee -a "$LOGFILE"
  echo "[supervise] launching bot at $(date -u +"%Y-%m-%d %H:%M:%SZ")" | tee -a "$LOGFILE"

  # run the bot; capture python's exit code (not tee's)
  python3 main.py 2>&1 | tee -a "$LOGFILE"
  rc=${PIPESTATUS[0]}

  echo "[supervise] bot exited with code $rc at $(date -u +"%Y-%m-%d %H:%M:%SZ")" | tee -a "$LOGFILE"

  # backoff before restart (5s on error, 15s if clean exit)
  if [ "$rc" -ne 0 ]; then
    sleep 5
  else
    sleep 15
  fi
done
