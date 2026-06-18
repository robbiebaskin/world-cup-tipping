#!/usr/bin/env bash
# Install / remove the wc_scorer adaptive auto-refresh cron job.
#
#   bash scripts/refresh-cron.sh install     # add the every-5-min job
#   bash scripts/refresh-cron.sh uninstall   # remove it
#   bash scripts/refresh-cron.sh status      # show it
#
# The job runs every 5 minutes; wc_scorer refresh itself throttles the actual
# ESPN pull to ~5 min while a match is on and ~2 h otherwise (see
# wc_scorer/schedule.py). So the cron cadence never has to change per round.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$(command -v python3)"
TAG="wc_scorer refresh"
LINE="*/5 * * * * cd ${REPO} && PATH=/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin ${PY} -m wc_scorer refresh >> out/refresh.log 2>&1"

case "${1:-status}" in
  install)
    { crontab -l 2>/dev/null | grep -v "${TAG}" || true; echo "${LINE}"; } | crontab -
    echo "Installed. Current job:"
    crontab -l | grep "${TAG}"
    echo
    echo "macOS note: if the job never writes out/refresh.log, grant Full Disk"
    echo "Access to /usr/sbin/cron in System Settings > Privacy & Security."
    ;;
  uninstall)
    crontab -l 2>/dev/null | grep -v "${TAG}" | crontab - 2>/dev/null || crontab -r 2>/dev/null || true
    echo "Removed."
    ;;
  status)
    crontab -l 2>/dev/null | grep "${TAG}" || echo "Not installed."
    ;;
  *)
    echo "usage: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
