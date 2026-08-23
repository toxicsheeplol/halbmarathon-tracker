#!/bin/zsh
# Refresh Strava data, regenerate the static dashboard and publish it.
# Intended to be run by launchd every 12 hours.

set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
LOG_FILE="$PROJECT_DIR/refresh.log"

exec >> "$LOG_FILE" 2>&1

log() {
  print -- "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] $*"
}

cd "$PROJECT_DIR"
log "Starting scheduled Strava refresh."

# Never publish over work that is currently being edited locally.
if ! /usr/bin/git diff --quiet || ! /usr/bin/git diff --cached --quiet; then
  log "Stopped: the repository has uncommitted changes."
  exit 1
fi

# Bring an otherwise clean checkout forward when it is behind GitHub, but
# refuse to guess how to resolve diverging histories.
/usr/bin/git fetch --quiet origin main
LOCAL_SHA=$(/usr/bin/git rev-parse HEAD)
REMOTE_SHA=$(/usr/bin/git rev-parse origin/main)
if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
  if /usr/bin/git merge-base --is-ancestor HEAD origin/main; then
    /usr/bin/git merge --ff-only --quiet origin/main
    log "Fast-forwarded to the latest GitHub version."
  elif /usr/bin/git merge-base --is-ancestor origin/main HEAD; then
    log "Local branch is ahead of GitHub; its commit will be published with this refresh."
  else
    log "Stopped: local and GitHub histories diverge; resolve this manually."
    exit 1
  fi
fi

/usr/bin/python3 tracker.py
/usr/bin/python3 render.py

if /usr/bin/git diff --quiet -- data.json index.html; then
  log "No Strava changes to publish."
  exit 0
fi

/usr/bin/git add -- data.json index.html
/usr/bin/git commit --quiet -m "Refresh Strava data"
/usr/bin/git push --quiet origin main
log "Published refreshed Strava data."
