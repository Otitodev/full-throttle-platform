#!/usr/bin/env bash
# Simulate an inbound Twilio SMS to the client gateway.
#
# Twilio's signature is HMAC-SHA1 over (full_url + concat(sorted(k+v))) using
# the account's auth token. Hermes validates that signature on every POST to
# /webhooks/twilio. Because we have the token in the profile .env, we can
# compute a valid signature ourselves and exercise the full inbound path
# (Caddy -> sms adapter -> signature check -> agent dispatch -> outbound reply)
# WITHOUT a real Twilio call. Useful when the originating phone's carrier
# blocks international SMS.
#
# Usage:
#   bash scripts/simulate_inbound_sms.sh <slug> <base-domain> <from-e164> "<body>"
#
# e.g.
#   bash scripts/simulate_inbound_sms.sh mrfence hooks.138.197.7.87.nip.io \
#        +2348127052315 "What services do you offer?"
set -euo pipefail

SLUG="${1:-}"; BASE="${2:-}"; FROM="${3:-}"; BODY="${4:-}"
[ -n "$SLUG" ] && [ -n "$BASE" ] && [ -n "$FROM" ] && [ -n "$BODY" ] || {
  echo "usage: $0 <slug> <base-domain> <from-e164> \"<body>\"" >&2; exit 2
}

PROF="/home/hermes/.hermes/profiles/$SLUG"
URL="https://${SLUG}.${BASE}/webhooks/twilio"

sudo -u hermes /usr/bin/python3 - "$PROF/.env" "$URL" "$FROM" "$BODY" <<'PY'
import sys, pathlib, hmac, hashlib, base64, urllib.request, urllib.parse, urllib.error, time

env = {}
for line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
tok = env["TWILIO_AUTH_TOKEN"]
to  = env["TWILIO_PHONE_NUMBER"]
url, frm, body = sys.argv[2], sys.argv[3], sys.argv[4]

# Twilio inbound SMS standard params
params = {
    "AccountSid":      env["TWILIO_ACCOUNT_SID"],
    "MessagingServiceSid": "",
    "MessageSid":      f"SM{int(time.time()*1000):x}".ljust(34, "0")[:34],
    "From":            frm,
    "To":              to,
    "Body":            body,
    "NumMedia":        "0",
    "NumSegments":     "1",
    "SmsStatus":       "received",
    "ApiVersion":      "2010-04-01",
    "FromCountry":     frm[1:4] == "234" and "NG" or "US",
    "ToCountry":       "US",
}
# Signature: HMAC-SHA1 of (url + sorted concat of k+v), b64.
signing = url + "".join(k + params[k] for k in sorted(params))
sig = base64.b64encode(hmac.new(tok.encode(), signing.encode(), hashlib.sha1).digest()).decode()

# POST as form
data = urllib.parse.urlencode(params).encode()
req  = urllib.request.Request(url, data=data, method="POST", headers={
    "Content-Type":      "application/x-www-form-urlencoded",
    "X-Twilio-Signature": sig,
    "User-Agent":         "TwilioProxy/1.1",
})
print(f"POST {url}")
print(f"From: {frm}  To: {to}  MessageSid: {params['MessageSid']}")
print(f"Body: {body!r}")
print(f"X-Twilio-Signature: {sig[:24]}…")
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print(f"HTTP {resp.status}")
    print(resp.read().decode()[:1000])
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}")
    print(e.read().decode()[:1000])
PY
