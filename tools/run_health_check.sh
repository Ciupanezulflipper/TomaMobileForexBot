#!/usr/bin/env bash
bash tools/env_sync.sh
bash tools/env_sync.sh
# run_health_check.sh — runs env sync, then executes health check

set -euo pipefail

# Always sync environment variables before running
bash "$(dirname "$0")/env_sync.sh"

# Run health check Python script
python3 "$(dirname "$0")/health_check.py"
