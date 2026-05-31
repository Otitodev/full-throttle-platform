#!/usr/bin/env bash
# Deeper inspection of why webhooks never reach the LLM.
# - Full webhook platform config from config.yaml
# - All recent sessions (not just one) with chat_id, message_count, provider
# - request_dump file list (proves whether ANY LLM call has been attempted)
# - log level config (LOG_LEVEL env, agent.log_level, etc.)
set -euo pipefail

SLUG="${1:-mrfence}"
PROF="/home/hermes/.hermes/profiles/$SLUG"

echo "=== platforms.webhook config"
sudo -u hermes python3 - "$PROF/config.yaml" <<'PY'
import sys, yaml, pathlib
d = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")) or {}
print(yaml.safe_dump({"platforms": (d.get("platforms") or {})}, sort_keys=False, default_flow_style=False))
PY

echo "=== agent + logging config"
sudo -u hermes python3 - "$PROF/config.yaml" <<'PY'
import sys, yaml, pathlib
d = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")) or {}
print(yaml.safe_dump({
    "agent": d.get("agent"),
    "logging": d.get("logging"),
    "gateway": d.get("gateway"),
}, sort_keys=False, default_flow_style=False))
PY

echo "=== log-level env vars in profile .env"
sudo -u hermes grep -iE "log|level|debug|verbose" "$PROF/.env" 2>/dev/null || echo "none"

echo "=== systemd unit env"
systemctl cat "hermes-gateway@$SLUG" | grep -E "^Environment|^EnvironmentFile" || echo "no env directives"

echo "=== all sessions, sorted by last_active desc"
sudo -u hermes python3 - "$PROF/sessions/sessions.json" <<'PY'
import sys, json, pathlib
p = pathlib.Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
sessions = list(data.values()) if isinstance(data, dict) else data
sessions.sort(key=lambda s: s.get("last_active", "") or s.get("updated_at", ""), reverse=True)
print(f"total sessions: {len(sessions)}")
for s in sessions[:8]:
    chat_id = s.get("chat_id") or (s.get("source") or {}).get("chat_id") or "?"
    print({
        "id": s.get("id") or s.get("session_id"),
        "chat_id": chat_id,
        "last_active": s.get("last_active") or s.get("updated_at"),
        "provider": s.get("provider"),
        "model": s.get("model"),
        "messages": len(s.get("messages", []) or []),
        "total_tokens": s.get("total_tokens"),
        "last_error": s.get("last_error"),
    })
PY

echo "=== request_dump files (proof of LLM call attempts)"
sudo -u hermes ls -lt "$PROF/sessions/" | grep request_dump | head -10 || echo "none"

echo "=== latest 8 files in profile root (any new logs/state?)"
sudo -u hermes find "$PROF" -type f -printf "%T@ %p\n" 2>/dev/null | sort -nr | head -10 | while read t f; do
  echo "$(date -d @${t%.*} +%Y-%m-%d_%H:%M:%S) $f"
done
