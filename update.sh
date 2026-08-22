#!/bin/bash
# Fetches fresh Strava data and rebuilds the dashboard.
# Designed for cron/launchd; always runs in its own folder.

set -euo pipefail
cd "$(dirname "$0")"

PY=$(command -v python3)
LOG="update.log"

{
  echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"
  "$PY" tracker.py
  "$PY" render.py
} >> "$LOG" 2>&1

# Keep the log from growing indefinitely: retain only the last 500 lines.
tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
