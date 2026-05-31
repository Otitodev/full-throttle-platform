#!/usr/bin/env bash
# Fetch the body that Twilio actually received for a specific message SID,
# plus its num_segments, num_media, error details, and any sub-resources.
set -euo pipefail

SLUG="${1:-mrfence}"
SID_ARG="${2:-}"  # optional message SID; defaults to most recent failed
PROF="/home/hermes/.hermes/profiles/$SLUG"

sudo -u hermes python3 - "$PROF/.env" "$SID_ARG" <<'PY'
import sys, pathlib, urllib.request, urllib.error, base64, json

env = {}
for line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

sid = env["TWILIO_ACCOUNT_SID"]; tok = env["TWILIO_AUTH_TOKEN"]
auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()

def tget(path):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:500]}

want_sid = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
if not want_sid:
    data = tget("/Messages.json?PageSize=5")
    for m in (data.get("messages") or []):
        if m.get("status") == "failed" and m.get("to","").startswith("+234"):
            want_sid = m["sid"]; break

if not want_sid:
    print("no failed +234 message found"); sys.exit(0)

print(f"=== full Twilio message detail for {want_sid}")
full = tget(f"/Messages/{want_sid}.json")
for k in ("sid","status","error_code","error_message","direction","date_sent",
         "from","to","body","num_segments","num_media","price","price_unit",
         "messaging_service_sid","api_version","uri","subresource_uris"):
    print(f"  {k}: {full.get(k)!r}")
PY
