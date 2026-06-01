#!/usr/bin/env bash
# Sync a skill from the platform repo into a live client profile.
#
# Profiles get a *copy* of each skill at onboarding time (see onboard_client.py).
# Edits to skills/ in the platform repo don't reach the live agent until the
# profile's local copy is refreshed. Run this after editing a skill in the repo
# and pulling on the droplet.
#
# Usage:
#   bash scripts/sync_skill_to_profile.sh <slug> <skill-name>
#   bash scripts/sync_skill_to_profile.sh mrfence lead-response
#
# Side effects:
#   - rsync platform repo skill -> profile skills dir (owner hermes)
#   - clear __pycache__/*.pyc so the new bytecode is regenerated
#   - no gateway restart needed; Hermes loads skill content per-turn
set -euo pipefail

SLUG="${1:-}"
NAME="${2:-}"
[ -n "$SLUG" ] && [ -n "$NAME" ] || {
  echo "usage: $0 <slug> <skill-name>" >&2; exit 2
}

SRC="/srv/full-throttle-platform/skills/$NAME/"
DST="/home/hermes/.hermes/profiles/$SLUG/skills/$NAME/"

[ -d "$SRC" ] || { echo "missing source $SRC" >&2; exit 1; }
sudo -u hermes test -d "$DST" || { echo "missing dest $DST (profile not onboarded with this skill?)" >&2; exit 1; }

echo "=== syncing $SRC  ->  $DST"
sudo -u hermes rsync -av --delete \
  --exclude='__pycache__' --exclude='*.pyc' \
  "$SRC" "$DST"

echo
echo "=== clearing stale bytecode in profile"
sudo -u hermes find "$DST" -type d -name __pycache__ -prune -exec rm -rf {} +
sudo -u hermes find "$DST" -type f -name '*.pyc' -delete

echo
echo "=== verify the SMS template line in the synced intake.py (if present)"
if sudo -u hermes test -f "${DST}scripts/intake.py"; then
  sudo -u hermes grep -A4 '^FIRST_TOUCH' "${DST}scripts/intake.py" || true
fi
