#!/usr/bin/env bash
# Find and kill any Hermes gateway process whose executable points at a
# deleted /opt/hermes-agent install (the ghost gateway from the previous
# install that's still bound to the Telegram bot's long-poll and intercepts
# messages before the live otito_socials profile sees them).
set -euo pipefail

echo "=== all hermes processes"
pgrep -af hermes 2>&1 | grep -v evict_ghost || true

echo
echo "=== ghost candidates (cmdline contains /opt/hermes-agent, OR /proc/exe is missing/deleted)"
GHOSTS=()
for pid in $(pgrep -f hermes 2>/dev/null); do
  cmd=$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null | head -c 200)
  exe=$(readlink /proc/$pid/exe 2>/dev/null || echo "<readlink-failed>")
  case "$cmd $exe" in
    *opt/hermes-agent*|*"(deleted)"*|*"<readlink-failed>"*)
      echo "  PID $pid"
      echo "    cmd: $cmd"
      echo "    exe: $exe"
      GHOSTS+=("$pid")
      ;;
  esac
done

if [ ${#GHOSTS[@]} -eq 0 ]; then
  echo "  none — no ghost found"
  exit 0
fi

echo
echo "=== killing ghosts (SIGTERM, then SIGKILL after 5s if still alive)"
for pid in "${GHOSTS[@]}"; do
  echo "  TERM $pid"
  kill -TERM "$pid" 2>/dev/null || true
done
sleep 5
for pid in "${GHOSTS[@]}"; do
  if [ -d "/proc/$pid" ]; then
    echo "  still alive — KILL $pid"
    kill -KILL "$pid" 2>/dev/null || true
  fi
done

echo
echo "=== bouncing otito_socials so its Telegram poller takes over cleanly"
systemctl restart hermes-gateway@otito_socials
sleep 6
systemctl is-active hermes-gateway@otito_socials
sudo -u hermes tail -15 /home/hermes/.hermes/profiles/otito_socials/logs/gateway.log | grep -i 'telegram\|connected\|error' | tail -10 || true
