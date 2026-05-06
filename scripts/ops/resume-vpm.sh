#!/usr/bin/env bash
# resume-vpm.sh — Auto-resume Claude Code session for the autonomous build (Linux/macOS).
#
# Schedule via cron (every hour). Example crontab line:
#   0 * * * * /home/josep/projects/vpm/scripts/ops/resume-vpm.sh
#
# When Claude Code hits its usage limit, the next firing after the limit
# resets will succeed; other attempts log a one-line skip and exit.

set -e

PROJECT_DIR="${VPM_PROJECT_DIR:-$HOME/projects/vpm}"
LOCK_FILE="$PROJECT_DIR/.claude-running.lock"
LOG_FILE="$PROJECT_DIR/.claude-resume.log"

# Bail if a session is already running (avoid duplicate concurrent sessions)
if [ -f "$LOCK_FILE" ]; then
    # Cross-platform mtime: GNU stat then BSD stat
    age_seconds=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || stat -f %m "$LOCK_FILE") ))
    if [ "$age_seconds" -lt 28800 ]; then  # <8h
        echo "$(date -Iseconds) skipped - lock present" >> "$LOG_FILE"
        exit 0
    fi
    # Stale lock (>8h) — likely orphaned by a crashed session
    rm -f "$LOCK_FILE"
fi

cd "$PROJECT_DIR"
touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

echo "$(date -Iseconds) resume attempt START" >> "$LOG_FILE"
git pull origin main >> "$LOG_FILE" 2>&1 || true
claude --continue --dangerously-skip-permissions \
    -p "if you stopped due to usage limit, continue with /gsd-autonomous" \
    >> "$LOG_FILE" 2>&1 || true
echo "$(date -Iseconds) resume attempt END" >> "$LOG_FILE"
