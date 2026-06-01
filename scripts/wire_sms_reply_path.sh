#!/usr/bin/env bash
# Wire the inbound-SMS reply path so customer replies to the first-touch
# reach the same agent session.
#
# Idempotent. Reversible (prints rollback steps at the end).
#
# Steps:
#   1. Add a `handle /webhooks/twilio*` route to the client's Caddy fragment
#      that reverse-proxies to 127.0.0.1:8080 (Hermes SMS adapter). Inserted
#      ABOVE the catch-all `reverse_proxy 127.0.0.1:<webhook_port>`.
#   2. Set `GATEWAY_ALLOW_ALL_USERS=true` in the profile .env so non-allowlisted
#      phone numbers (real customers) can interact. Twilio signature
#      validation still protects against spoofing.
#   3. Repoint the Twilio number's sms_url via the Twilio REST API to the
#      mrfence webhook. Prints the OLD url so it can be restored.
#   4. `caddy validate` + reload, then restart the gateway so the env change
#      is picked up.
set -euo pipefail

SLUG="${1:-mrfence}"
BASE_DOMAIN="${2:-hooks.138.197.7.87.nip.io}"
PROF="/home/hermes/.hermes/profiles/$SLUG"
ENV_FILE="$PROF/.env"
FRAG="/etc/full-throttle/caddy.d/$SLUG.caddy"
PUBLIC_URL="https://${SLUG}.${BASE_DOMAIN}/webhooks/twilio"

[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE" >&2; exit 1; }
[ -f "$FRAG"     ] || { echo "missing $FRAG" >&2; exit 1; }

echo "=== 1. Add /webhooks/twilio* handle to Caddy fragment"
if grep -q '/webhooks/twilio' "$FRAG"; then
  echo "  already present; skipping"
else
  cp -a "$FRAG" "$FRAG.bak-$(date +%s)"
  python3 - "$FRAG" <<'PY'
import sys, re, pathlib
p = pathlib.Path(sys.argv[1])
txt = p.read_text(encoding="utf-8")
# Insert a handle block immediately before the bare `reverse_proxy 127.0.0.1:<port>`
# catch-all line. Match indentation so Caddyfile stays readable.
pat = re.compile(r"(\n\s*# Anything else.*?\n\s*reverse_proxy 127\.0\.0\.1:\d+\n)", re.S)
m = pat.search(txt)
if not m:
    # Fallback: insert before bare reverse_proxy line
    pat = re.compile(r"(\n\s*reverse_proxy 127\.0\.0\.1:\d+\n)")
    m = pat.search(txt)
if not m:
    raise SystemExit("could not find catch-all reverse_proxy line in fragment")
block = (
    "\n\t# Inbound SMS replies (Twilio POST) -> Hermes sms adapter on :8080.\n"
    "\thandle /webhooks/twilio* {\n"
    "\t\treverse_proxy 127.0.0.1:8080\n"
    "\t}\n"
)
new = txt[:m.start()] + block + txt[m.start():]
p.write_text(new, encoding="utf-8")
print("  inserted handle /webhooks/twilio* block")
PY
fi

echo
echo "=== 2. Set GATEWAY_ALLOW_ALL_USERS=true in profile .env"
if sudo -u hermes grep -q '^GATEWAY_ALLOW_ALL_USERS=' "$ENV_FILE"; then
  sudo -u hermes sed -i 's/^GATEWAY_ALLOW_ALL_USERS=.*/GATEWAY_ALLOW_ALL_USERS=true/' "$ENV_FILE"
  echo "  updated existing line"
else
  echo "GATEWAY_ALLOW_ALL_USERS=true" | sudo -u hermes tee -a "$ENV_FILE" >/dev/null
  echo "  appended"
fi

echo
echo "=== 3. Repoint Twilio sms_url to $PUBLIC_URL"
sudo -u hermes python3 - "$ENV_FILE" "$PUBLIC_URL" <<'PY'
import sys, pathlib, urllib.request, urllib.parse, urllib.error, base64, json

env = {}
for line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
acct = env["TWILIO_ACCOUNT_SID"]; tok = env["TWILIO_AUTH_TOKEN"]
frm  = env["TWILIO_PHONE_NUMBER"]
new_url = sys.argv[2]
auth = base64.b64encode(f"{acct}:{tok}".encode()).decode()

# Find PN sid for the FROM number
url = f"https://api.twilio.com/2010-04-01/Accounts/{acct}/IncomingPhoneNumbers.json?PhoneNumber={urllib.parse.quote(frm)}"
req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
data = json.loads(urllib.request.urlopen(req, timeout=10).read())
nums = data.get("incoming_phone_numbers") or []
if not nums:
    print(f"  ERROR: no IncomingPhoneNumber matches {frm}"); sys.exit(1)
pn = nums[0]; pn_sid = pn["sid"]; old_url = pn.get("sms_url")
print(f"  PN sid: {pn_sid}")
print(f"  OLD sms_url: {old_url}")
print(f"  NEW sms_url: {new_url}")

# PATCH (Twilio uses POST with form body for resource updates)
patch_url = f"https://api.twilio.com/2010-04-01/Accounts/{acct}/IncomingPhoneNumbers/{pn_sid}.json"
body = urllib.parse.urlencode({"SmsUrl": new_url, "SmsMethod": "POST"}).encode()
req = urllib.request.Request(patch_url, data=body, method="POST",
    headers={"Authorization": f"Basic {auth}",
             "Content-Type": "application/x-www-form-urlencoded"})
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    print(f"  updated. now sms_url={resp.get('sms_url')}  sms_method={resp.get('sms_method')}")
    print()
    print(f"  ROLLBACK if needed: set SmsUrl back to: {old_url}")
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
    sys.exit(1)
PY

echo
echo "=== 4. Validate + reload Caddy, restart gateway"
caddy validate --config /etc/caddy/Caddyfile 2>&1 | tail -5
systemctl reload caddy
echo "  caddy reloaded"
systemctl restart "hermes-gateway@$SLUG"
sleep 6
systemctl is-active "hermes-gateway@$SLUG"

echo
echo "=== 5. Smoke probes"
echo "  /webhooks/twilio (expect 403 or 400 — Twilio sig required):"
curl -sS -o /dev/null -w "    HTTP %{http_code}\n" -X POST "$PUBLIC_URL" -d "From=%2B15555550100&Body=test" || true
echo "  /health on the sms adapter (loopback only, expect ok):"
curl -sS -o /dev/null -w "    HTTP %{http_code}\n" "http://127.0.0.1:8080/health" || true
