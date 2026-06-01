#!/usr/bin/env bash
# Survey the Hermes installs on this box, what /usr/local/bin/hermes
# actually invokes, and whether slash_confirm exists in each.
set -euo pipefail

echo "=== /usr/local/bin/hermes resolves to:"
ls -la /usr/local/bin/hermes 2>&1
readlink -f /usr/local/bin/hermes 2>&1 || true
file /usr/local/bin/hermes 2>&1 | head -1
echo

echo "=== systemd unit ExecStart (effective)"
systemctl show hermes-gateway@otito_socials -p ExecStart --value
echo

echo "=== Hermes install at /opt/hermes-agent"
[ -d /opt/hermes-agent ] && {
  ls /opt/hermes-agent/ | head -10
  cat /opt/hermes-agent/version.py 2>/dev/null | head -3 || true
  cat /opt/hermes-agent/VERSION 2>/dev/null | head -3 || true
  echo "git status:"
  (cd /opt/hermes-agent && git log --oneline -1 2>&1 | head -1) || echo "  not a git repo"
  echo "slash_confirm exported?"
  grep -E 'slash_confirm' /opt/hermes-agent/tools/__init__.py 2>&1 | head -3 || echo "  NOT in __init__.py"
  echo "slash_confirm module exists?"
  find /opt/hermes-agent/tools -maxdepth 2 -name 'slash_confirm*' 2>&1 | head -3 || echo "  not found"
} || echo "  /opt/hermes-agent missing"
echo

echo "=== Hermes install at /home/hermes/.hermes/hermes-agent"
H=/home/hermes/.hermes/hermes-agent
sudo -u hermes ls "$H/" 2>&1 | head -10
sudo -u hermes cat "$H/version.py" 2>/dev/null | head -3 || true
sudo -u hermes cat "$H/VERSION" 2>/dev/null | head -3 || true
echo "git status:"
sudo -u hermes bash -lc "cd $H && git log --oneline -1" 2>&1 | head -1 || echo "  not a git repo"
echo "slash_confirm exported?"
sudo -u hermes grep -E 'slash_confirm' "$H/tools/__init__.py" 2>&1 | head -3 || echo "  NOT in __init__.py"
echo "slash_confirm module exists?"
sudo -u hermes find "$H/tools" -maxdepth 2 -name 'slash_confirm*' 2>&1 | head -3 || echo "  not found"
echo

echo "=== Which python the running gateways actually use"
for pid in $(pgrep -af 'hermes -p .* gateway' | awk '{print $1}'); do
  exe=$(readlink -f /proc/$pid/exe 2>/dev/null || echo "?")
  args=$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null | head -c 200)
  echo "  PID $pid"
  echo "    exe: $exe"
  echo "    cmd: $args"
done
