#!/usr/bin/env bash
# Unified diagnostics for env + health check
set -euo pipefail

ROOT="$HOME/TomaMobileForexBot"
DIR="$ROOT/tools"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"

banner(){ printf "\n===== %s =====\n" "$1"; }

summary(){
  bash "$DIR/env_sync.sh" >/dev/null
  echo "======== ENV SUMMARY ========"
  for k in TELEGRAM_BOT_TOKEN FINNHUB_API_KEY FINNHUB_KEY TWELVE_DATA_API_KEY ALPHA_VANTAGE_API_KEY; do
    if [ -n "${!k-}" ]; then echo "$k: SET"; else echo "$k: MISSING"; fi
  done
}

# 1) Current shell
banner "SHELL RUN"
(
  cd "$ROOT"
  # ensure env in this shell
  source .env 2>/dev/null || true
  bash "$DIR/env_sync.sh"
  summary
  bash "$DIR/run_health_check.sh" | tee -a "$LOGDIR/full_health.shell.log"
)

# 2) Fresh, clean subshell (no inherited env)
banner "FRESH SUBSHELL RUN"
env -i bash -lc "
  set -euo pipefail
  cd '$ROOT'
  source .env 2>/dev/null || true
  bash '$DIR/env_sync.sh'
  $(typeset -f summary)
  summary
  bash '$DIR/run_health_check.sh'
" | tee -a "$LOGDIR/full_health.subshell.log"

# 3) tmux run (isolated background)
banner "TMUX RUN"
TS=\"$(date -u +%Y%m%d-%H%M%SZ)\"
TMUX_NAME=\"hcdiag-\$TS\"
tmux new-session -d -s \"\$TMUX_NAME\" \"bash -lc 'cd \"$ROOT\" && source .env 2>/dev/null || true && bash \"$DIR/env_sync.sh\" && bash \"$DIR/run_health_check.sh\" | tee \"$LOGDIR/full_health.tmux.\$TS.log\"'\"
# give it a moment to run
sleep 3
if tmux has-session -t \"\$TMUX_NAME\" 2>/dev/null; then
  # grab last lines then clean up
  tmux capture-pane -pt \"\$TMUX_NAME\" -S -200 > \"$LOGDIR/full_health.tmux.capture.\$TS.txt\" || true
  tmux kill-session -t \"\$TMUX_NAME\" || true
fi

echo
echo \"Logs saved under: $LOGDIR\"
ls -1t \"$LOGDIR\" | head -n 6
