#!/usr/bin/env bash
# Pull the actual send_message tool response for the most recent lead, plus
# the Twilio FROM number Hermes is using, plus (if we can find a SID) the
# Twilio Messages API status for that SID — so we can tell apart "accepted by
# Twilio" from "delivered" / "undelivered" / "failed".
set -euo pipefail

SLUG="${1:-mrfence}"
PROF="/home/hermes/.hermes/profiles/$SLUG"
LOG="$PROF/logs/agent.log"

echo "=== FROM number in profile .env"
sudo -u hermes grep '^TWILIO_PHONE_NUMBER=' "$PROF/.env" || echo "not set"
echo "=== TWILIO_ACCOUNT_SID prefix"
sudo -u hermes grep '^TWILIO_ACCOUNT_SID=' "$PROF/.env" | awk -F= '{print substr($2,1,12)"…"}'

echo
echo "=== last 5 send_message tool entries from agent.log (raw, untruncated)"
sudo -u hermes grep -n "send_message" "$LOG" | tail -10
echo "--- expanded context for each ---"
sudo -u hermes grep -B1 -A3 "Tool send_message" "$LOG" | tail -40

echo
echo "=== last 30 minutes of send_message tool output, untruncated"
sudo -u hermes awk '
  /agent.tool_executor: Tool send_message/ {p=1}
  p {print; n++; if (n>=8) {p=0; n=0; print "---"}}
' "$LOG" | tail -60

echo
echo "=== Twilio API: list last 5 messages from account, status & error_code"
sudo -u hermes python3 - "$PROF/.env" <<'PY'
import sys, pathlib, urllib.request, urllib.error, base64, json, ssl

env = {}
for line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

sid = env.get("TWILIO_ACCOUNT_SID")
tok = env.get("TWILIO_AUTH_TOKEN")
if not sid or not tok:
    print("missing Twilio creds in .env"); sys.exit(0)

auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()
url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json?PageSize=10"
req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()[:400]}"); sys.exit(0)
except Exception as e:
    print(f"err: {type(e).__name__}: {e}"); sys.exit(0)

print(f"{'sid':<36} {'date_sent':<25} {'from':<16} {'to':<18} {'status':<14} err")
for m in (data.get("messages") or [])[:10]:
    print(f"{m.get('sid','?'):<36} {(m.get('date_sent') or m.get('date_created') or '?'):<25} "
          f"{m.get('from','?'):<16} {m.get('to','?'):<18} {m.get('status','?'):<14} "
          f"code={m.get('error_code')!r} msg={m.get('error_message')!r}")
PY
