#!/usr/bin/env bash
# Pull the full Twilio detail on the most recent failed messages to mrfence's
# verified destination:
#   1. Per-message: re-fetch each SID so error_message has time to populate
#   2. FROM number capabilities (can it send international SMS?)
#   3. Account balance (trial credit may be exhausted)
#   4. Trial-Verified Caller IDs (confirm +2348127052315 is actually there)
set -euo pipefail

SLUG="${1:-mrfence}"
PROF="/home/hermes/.hermes/profiles/$SLUG"

sudo -u hermes python3 - "$PROF/.env" <<'PY'
import sys, pathlib, urllib.request, urllib.error, base64, json

env = {}
for line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

sid = env["TWILIO_ACCOUNT_SID"]
tok = env["TWILIO_AUTH_TOKEN"]
frm = env.get("TWILIO_PHONE_NUMBER", "")

auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()

def tget(path):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:500]}
    except Exception as e:
        return -1, {"error": f"{type(e).__name__}: {e}"}

print("=== 1. Recent failed messages — re-fetched per SID")
_, data = tget("/Messages.json?PageSize=10")
for m in (data.get("messages") or []):
    if m.get("status") != "failed": continue
    psid = m["sid"]
    _, full = tget(f"/Messages/{psid}.json")
    print(f"SID {psid}  to={full.get('to')}  status={full.get('status')}  "
          f"code={full.get('error_code')}  msg={full.get('error_message')!r}")

print()
print("=== 2. Account balance")
_, bal = tget("/Balance.json")
print(json.dumps(bal, indent=2))

print()
print("=== 3. FROM number details / capabilities")
_, numbers = tget("/IncomingPhoneNumbers.json")
for n in (numbers.get("incoming_phone_numbers") or []):
    if n.get("phone_number") == frm:
        print(f"phone_number: {n.get('phone_number')}")
        print(f"capabilities: {n.get('capabilities')}")
        print(f"sms_url:      {n.get('sms_url')}")
        print(f"status:       {n.get('status')}")
        print(f"sid:          {n.get('sid')}")
        break
else:
    print(f"FROM number {frm} not found in account's IncomingPhoneNumbers")
    print("first 3 numbers we DO own:")
    for n in (numbers.get("incoming_phone_numbers") or [])[:3]:
        print(f"  {n.get('phone_number')}  caps={n.get('capabilities')}")

print()
print("=== 4. Verified Caller IDs (trial accounts can only message these)")
_, vci = tget("/OutgoingCallerIds.json")
for v in (vci.get("outgoing_caller_ids") or []):
    print(f"  {v.get('phone_number')}  friendly={v.get('friendly_name')}  verified=true")

print()
print("=== 5. Account details (look for 'Trial' status)")
_, acct = tget(".json")
print(f"status: {acct.get('status')}, type: {acct.get('type')}, friendly: {acct.get('friendly_name')}")
PY
