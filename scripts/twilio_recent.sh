#!/usr/bin/env bash
# List the last N Twilio messages for the account regardless of status.
set -euo pipefail
SLUG="${1:-mrfence}"
N="${2:-10}"
PROF="/home/hermes/.hermes/profiles/$SLUG"

sudo -u hermes python3 - "$PROF/.env" "$N" <<'PY'
import sys, pathlib, urllib.request, urllib.error, base64, json
env = {}
for line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
sid = env["TWILIO_ACCOUNT_SID"]; tok = env["TWILIO_AUTH_TOKEN"]
auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()
n = int(sys.argv[2])
url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json?PageSize={n}"
req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
hdr = ("sid", "date_sent", "from", "to", "status", "num_segments", "error_code", "body_preview")
print(" | ".join(h.ljust(36 if h=="sid" else 25 if h=="date_sent" else 16 if h in ("from","to") else 12 if h=="status" else 4 if h=="num_segments" else 6 if h=="error_code" else 40) for h in hdr))
for m in (data.get("messages") or [])[:n]:
    body = (m.get("body") or "").replace("\n", " ")[:60]
    print(" | ".join([
        m.get("sid","?").ljust(36),
        (m.get("date_sent") or m.get("date_created") or "?")[:25].ljust(25),
        (m.get("from") or "?").ljust(16),
        (m.get("to") or "?").ljust(16),
        (m.get("status") or "?").ljust(12),
        str(m.get("num_segments","?")).ljust(4),
        str(m.get("error_code") or "-").ljust(6),
        body,
    ]))
PY
