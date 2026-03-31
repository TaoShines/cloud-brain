#!/bin/zsh

set -euo pipefail

PROJECT_DIR="/Users/taoxuan/Desktop/cloud-brain"
PYTHON_BIN="/Users/taoxuan/miniconda3/bin/python3"
LOG_DIR="$PROJECT_DIR/logs"
RUN_LOG="$LOG_DIR/cloud_capture_sync.log"
STAMP="$(date '+%Y-%m-%d %H:%M:%S')"

mkdir -p "$LOG_DIR"

{
  echo "[$STAMP] Starting cloud capture sync"
  cd "$PROJECT_DIR"
  "$PYTHON_BIN" -m personal_brain sync-cloud-capture
  echo "[$STAMP] Cloud capture sync completed"
  echo
} >> "$RUN_LOG" 2>&1
