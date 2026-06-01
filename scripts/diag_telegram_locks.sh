#!/usr/bin/env bash
# Investigate why Hermes' Telegram platform can't write its scoped lock
# under /home/hermes/.local/state/hermes/ ("Read-only file system" error).
set -euo pipefail

SLUG="${1:-otito_socials}"

echo "=== 1. Actual perms/state of ~/.local hierarchy"
ls -la /home/hermes/.local/ 2>&1 | head -10
echo "---"
ls -la /home/hermes/.local/state/ 2>&1 | head -10 || echo "  (dir may not exist)"
echo "---"
ls -la /home/hermes/.local/state/hermes/ 2>&1 | head -10 || echo "  (dir may not exist)"

echo
echo "=== 2. Filesystem mount info for /home"
mount | grep -E '/home|/$' 2>&1 || true

echo
echo "=== 3. Can the hermes user actually write there manually?"
sudo -u hermes bash -lc '
  set -e
  TARGET=/home/hermes/.local/state/hermes
  mkdir -p "$TARGET" && echo "  mkdir ok"
  T=$(mktemp -p "$TARGET" probe.XXXX)
  echo "  wrote $T"
  rm -f "$T" && echo "  removed probe"
' 2>&1 || echo "  ✗ FAILED to write as hermes user"

echo
echo "=== 4. systemd unit ProtectSystem / ReadWritePaths / etc."
systemctl show "hermes-gateway@$SLUG" -p ProtectSystem,ProtectHome,ReadWritePaths,ReadOnlyPaths,InaccessiblePaths,PrivateTmp,PrivateDevices,User,Group 2>&1

echo
echo "=== 5. systemd unit file contents"
cat /etc/systemd/system/hermes-gateway@.service 2>&1

echo
echo "=== 6. Effective per-instance unit overrides (drop-ins)"
ls -la /etc/systemd/system/hermes-gateway@.service.d/ 2>&1 || echo "  (no drop-ins)"
ls -la /etc/systemd/system/hermes-gateway@${SLUG}.service.d/ 2>&1 || echo "  (no instance drop-ins)"
