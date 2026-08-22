#!/bin/bash
# Holt frische Strava-Daten und baut das Dashboard neu.
# Fuer cron/launchd gedacht - laeuft immer im eigenen Ordner, egal von wo gestartet.

set -euo pipefail
cd "$(dirname "$0")"

PY=$(command -v python3)
LOG="update.log"

{
  echo "--- $(date '+%Y-%m-%d %H:%M:%S') ---"
  "$PY" tracker.py
  "$PY" render.py
} >> "$LOG" 2>&1

# Log nicht endlos wachsen lassen: nur die letzten 500 Zeilen behalten
tail -n 500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
