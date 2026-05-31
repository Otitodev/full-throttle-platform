#!/usr/bin/env bash
# Send a signed test lead to a promoted client's webhook.
#
# Usage:
#     bash scripts/send_test_lead.sh <slug> <base-domain> [--phone +1234567890]
#                                                         [--name "Some Name"]
#                                                         [--message "..."]
#
#   e.g. bash scripts/send_test_lead.sh mrfence hooks.138.197.7.87.nip.io
#        bash scripts/send_test_lead.sh mrfence hooks.138.197.7.87.nip.io --phone +2348127052315
#
# Reads the slug's WEBHOOK_LEAD_SECRET from <profile>/.env, signs the body
# with HMAC-SHA256, POSTs to https://<slug>.<base-domain>/webhooks/lead.
#
# The --phone arg is what shows up as the customer's contact number in the
# lead. For Twilio trial accounts, this number must be verified at
# twilio.com/console/phone-numbers/verified before SMS delivery succeeds.

set -euo pipefail

SLUG="${1:-}"
BASE_DOMAIN="${2:-}"
[ -n "$SLUG" ] && [ -n "$BASE_DOMAIN" ] || {
  echo "usage: $0 <slug> <base-domain> [--phone +E.164] [--name STR] [--message STR]" >&2
  exit 2
}
shift 2

PHONE="+18505550199"
NAME="Sarah Chen"
EMAIL="sarah@example.com"
SOURCE="website-form"
MESSAGE="Need a quote for 200ft of privacy vinyl fence in Lynn Haven, FL"

while [ $# -gt 0 ]; do
  case "$1" in
    --phone)   PHONE="$2"; shift 2 ;;
    --name)    NAME="$2"; shift 2 ;;
    --email)   EMAIL="$2"; shift 2 ;;
    --source)  SOURCE="$2"; shift 2 ;;
    --message) MESSAGE="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

ENV_FILE="/home/hermes/.hermes/profiles/${SLUG}/.env"
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE" >&2; exit 1; }

SECRET=$(grep ^WEBHOOK_LEAD_SECRET= "$ENV_FILE" | head -1 | cut -d= -f2-)
[ -n "$SECRET" ] || { echo "WEBHOOK_LEAD_SECRET not in $ENV_FILE" >&2; exit 1; }

# Build the body via python so quoting/escaping for arbitrary --name/--message is safe.
BODY=$(python3 -c "
import json, sys
print(json.dumps({
    'name': sys.argv[1],
    'phone': sys.argv[2],
    'email': sys.argv[3],
    'source': sys.argv[4],
    'message': sys.argv[5],
}))
" "$NAME" "$PHONE" "$EMAIL" "$SOURCE" "$MESSAGE")
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')

URL="https://${SLUG}.${BASE_DOMAIN}/webhooks/lead"

printf '\033[1;36m[lead]\033[0m posting to %s\n' "$URL"
printf '\033[1;36m[lead]\033[0m sig: %s\n' "$SIG"
printf '\033[1;36m[lead]\033[0m response:\n'
curl -sS -i -X POST \
  -H 'Content-Type: application/json' \
  -H "X-Webhook-Signature: $SIG" \
  -d "$BODY" \
  "$URL" | head -20
echo
