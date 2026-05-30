#!/usr/bin/env bash
# One-shot helper to onboard Mr. Fence of Florida.
#
# Drops:
#   /home/hermes/mrfence.intake.json     — populated, ready to use
#   /home/hermes/mrfence.secrets.json    — TEMPLATE; replace the placeholders
#                                          with real values before running
#                                          onboard_client.py.
#
# Usage:
#     sudo bash scripts/onboard_mrfence.sh         # just drop the files
#     sudo bash scripts/onboard_mrfence.sh --run   # also runs onboard_client.py
#
# Re-running is safe — files are overwritten only if --force is passed; secrets
# you've edited will be preserved otherwise.

set -euo pipefail

ROOT=/home/hermes
INTAKE="${ROOT}/mrfence.intake.json"
SECRETS="${ROOT}/mrfence.secrets.json"

RUN=0
FORCE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --run)   RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root (sudo)" >&2; exit 1
fi

log() { printf '\033[1;36m[mrfence]\033[0m %s\n' "$*"; }

# --------------------------------------------------------------------------
# Intake — always rewritten, no secrets inside.
# --------------------------------------------------------------------------

log "writing $INTAKE"
cat > "$INTAKE" <<'JSON'
{
  "client": {
    "slug": "mrfence",
    "business_name": "Mr. Fence of Florida",
    "timezone": "America/Chicago",
    "service_area": "Panama City, FL and 49 surrounding cities",
    "services": [
      "vinyl fences",
      "aluminum fences",
      "wood fences",
      "chain link fences",
      "pool fences",
      "gates",
      "fence repair"
    ],
    "brand_voice": "Local Florida family-owned fence company; friendly, direct, no jargon; reply quickly and concretely. Mention the 4.8-star / 417-review reputation only when it fits naturally."
  },
  "site": { "mode": "augment", "adapter": "manual" },
  "channels": {
    "owner_sms": "+2349036675598",
    "lead_route": "lead",
    "public_base_domain": "hooks.138.197.7.87.nip.io"
  },
  "crm": { "provider": "manual" },
  "model": { "provider": "anthropic", "model": "claude-sonnet-4-6" }
}
JSON
chown hermes:hermes "$INTAKE"

# --------------------------------------------------------------------------
# Secrets — template only, do NOT overwrite existing edits unless --force.
# webhook_lead_secret is auto-generated so the operator never has to pick one.
# --------------------------------------------------------------------------

if [ -f "$SECRETS" ] && [ "$FORCE" -ne 1 ]; then
  log "$SECRETS already exists — preserving (pass --force to overwrite)"
else
  log "writing $SECRETS template (will need editing)"
  WEBHOOK_SECRET=$(openssl rand -hex 32)
  cat > "$SECRETS" <<JSON
{
  "_README": "Replace every <REPLACE_…> placeholder with a real value. Webhook secret is pre-generated below; you can leave it as-is.",

  "model_api_key": "<REPLACE_WITH_ANTHROPIC_API_KEY>",

  "webhook_lead_secret": "${WEBHOOK_SECRET}",

  "twilio_account_sid": "<REPLACE_WITH_TWILIO_ACCOUNT_SID>",
  "twilio_auth_token": "<REPLACE_WITH_TWILIO_AUTH_TOKEN>",
  "twilio_phone_number": "<REPLACE_WITH_TWILIO_FROM_NUMBER_E164>"
}
JSON
  chmod 600 "$SECRETS"
  chown hermes:hermes "$SECRETS"
fi

log "files in place"
log "  intake:  $INTAKE"
log "  secrets: $SECRETS (mode 600, hermes-owned)"
log ""
log "edit the secrets file (placeholders need replacing):"
log "    sudo -u hermes nano $SECRETS"
log ""

if [ "$RUN" -ne 1 ]; then
  log "next: sudo bash $0 --run     # to actually onboard"
  exit 0
fi

# --------------------------------------------------------------------------
# Validation + onboarding
# --------------------------------------------------------------------------

if grep -q '<REPLACE_' "$SECRETS"; then
  echo "secrets file still has <REPLACE_…> placeholders; refusing to run." >&2
  exit 1
fi

PLATFORM_DIR="$(cd "$(dirname "$0")/.." && pwd)"

log "running onboard_client.py"
sudo -u hermes -i bash -c "python3 ${PLATFORM_DIR}/scripts/onboard_client.py --intake ${INTAKE} --secrets ${SECRETS} --force"

log "done. next step:"
log "    sudo bash ${PLATFORM_DIR}/infra/promote_client.sh mrfence \\"
log "        --base-domain hooks.138.197.7.87.nip.io"
