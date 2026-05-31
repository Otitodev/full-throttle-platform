#!/usr/bin/env bash
# Inspect the live state of the mrfence gateway:
# - current systemd PID + status
# - last 80 journal lines for the running PID
# - whether governance/audit.jsonl exists
# - most recent session summary (provider, tokens, last_active, message count)
#
# Run on the droplet. Safe to re-run.
set -euo pipefail

SLUG="${1:-mrfence}"
PROF="/home/hermes/.hermes/profiles/$SLUG"

echo "=== date"; date
echo "=== systemd"
systemctl show "hermes-gateway@$SLUG" -p MainPID,ActiveState,SubState --value | paste -sd' '
PID=$(systemctl show "hermes-gateway@$SLUG" -p MainPID --value)
echo "PID=$PID"

echo "=== journal (last 80 lines for PID $PID)"
if [ "$PID" != "0" ]; then
  journalctl _PID="$PID" --no-pager -n 80 | tail -70 || true
fi

echo "=== audit"
if sudo -u hermes test -f "$PROF/governance/audit.jsonl"; then
  sudo -u hermes wc -l "$PROF/governance/audit.jsonl"
  sudo -u hermes tail -5 "$PROF/governance/audit.jsonl"
else
  echo "no audit.jsonl yet"
fi

echo "=== latest session"
sudo -u hermes python3 - "$PROF/sessions/sessions.json" <<'PY'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
if not p.exists():
    print("no sessions.json"); raise SystemExit
data = json.loads(p.read_text(encoding="utf-8"))
sessions = list(data.values()) if isinstance(data, dict) else data
if not sessions:
    print("empty sessions"); raise SystemExit
sessions.sort(key=lambda s: s.get("last_active", "") or s.get("updated_at", ""), reverse=True)
top = sessions[0]
summary = {
    "id": top.get("id") or top.get("session_id"),
    "last_active": top.get("last_active") or top.get("updated_at"),
    "provider": top.get("provider"),
    "model": top.get("model"),
    "total_tokens": top.get("total_tokens"),
    "last_prompt_tokens": top.get("last_prompt_tokens"),
    "last_completion_tokens": top.get("last_completion_tokens"),
    "message_count": len(top.get("messages", []) or []),
    "last_msg_role": (top.get("messages") or [{}])[-1].get("role"),
}
print(json.dumps(summary, indent=2, default=str))
PY
