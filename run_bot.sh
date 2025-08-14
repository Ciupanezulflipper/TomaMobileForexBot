#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

SESSION="bot"
WORKDIR="$HOME/TomaMobileForexBot"
LOGDIR="$WORKDIR/logs"
LOGFILE="$LOGDIR/bot.log"

mkdir -p "$LOGDIR"

# simple log rotate (~2 MB)
if [ -f "$LOGFILE" ] && [ "$(stat -c%s "$LOGFILE" 2>/dev/null || echo 0)" -gt 2000000 ]; then
  ts=$(date -u +"%Y%m%d-%H%M%S")
  mv "$LOGFILE" "$LOGDIR/bot-$ts.log"
fi

# start tmux session if not running; otherwise just report
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "[run_bot] tmux session '$SESSION' already running."
else
  tmux new -d -s "$SESSION" "$WORKDIR/supervise_bot.sh"
  echo "[run_bot] started tmux session '$SESSION'."
fi
