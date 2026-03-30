#!/bin/zsh

set -euo pipefail

PROJECT_DIR="/Users/taoxuan/Desktop/cloud-brain"
PYTHON_BIN="/Users/taoxuan/miniconda3/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"
RUN_LOG="$LOG_DIR/daily_sync.log"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"

mkdir -p "$LOG_DIR"

{
  echo "[$STAMP] Starting daily sync"
  cd "$PROJECT_DIR"
  "$PYTHON_BIN" -m personal_brain sync
  "$PYTHON_BIN" -m personal_brain stats
  echo "[$STAMP] Daily sync completed"
  echo
} >> "$RUN_LOG" 2>&1
