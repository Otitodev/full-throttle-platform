#!/usr/bin/env bash
# Send a signed test lead to a promoted client's webhook.
#
# Usage:
#     bash scripts/send_test_lead.sh <slug> <base-domain>
#
#   e.g. bash scripts/send_test_lead.sh mrfence hooks.138.197.7.87.nip.io
#
# Reads the slug's WEBHOOK_LEAD_SECRET from <profile>/.env, signs the body
# with HMAC-SHA256, POSTs to https://<slug>.<base-domain>/webhooks/lead.

set -euo pipefail

SLUG="${1:-}"
BASE_DOMAIN="${2:-}"
[ -n "$SLUG" ] && [ -n "$BASE_DOMAIN" ] || {
  echo "usage: $0 <slug> <base-domain>" >&2; exit 2
}

ENV_FILE="/home/hermes/.hermes/profiles/${SLUG}/.env"
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE" >&2; exit 1; }

SECRET=$(grep ^WEBHOOK_LEAD_SECRET= "$ENV_FILE" | head -1 | cut -d= -f2-)
[ -n "$SECRET" ] || { echo "WEBHOOK_LEAD_SECRET not in $ENV_FILE" >&2; exit 1; }

# Realistic-but-fake lead. Edit if you want to drive different agent paths.
BODY='{"name":"Sarah Chen","phone":"+18505550199","email":"sarah@example.com","source":"website-form","message":"Need a quote for 200ft of privacy vinyl fence in Lynn Haven, FL"}'
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
