#!/usr/bin/env bash
# Modernize a personal Hermes profile and bring it up under systemd with
# the Telegram platform.
#
# Assumes:
#   - Profile dir already exists at /home/hermes/.hermes/profiles/<slug>
#   - .env already contains ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, and
#     TELEGRAM_ALLOWED_USERS (set those via `sudo -u hermes nano` BEFORE
#     running this).
#
# Idempotent. Backs up the existing config.yaml before rewriting.
set -euo pipefail

SLUG="${1:-otito_socials}"
PROF="/home/hermes/.hermes/profiles/$SLUG"
CFG="$PROF/config.yaml"
ENV_FILE="$PROF/.env"

[ -d "$PROF"      ] || { echo "missing profile dir $PROF" >&2; exit 1; }
[ -f "$ENV_FILE"  ] || { echo "missing $ENV_FILE — create it first" >&2; exit 1; }

echo "=== 1. Verify required env vars present (values not printed)"
for var in ANTHROPIC_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_USERS; do
  if sudo -u hermes grep -q "^${var}=" "$ENV_FILE"; then
    echo "  ✓ $var present"
  else
    echo "  ✗ $var MISSING in $ENV_FILE" >&2
    echo "    Edit with: sudo -u hermes nano $ENV_FILE" >&2
    exit 1
  fi
done

echo
echo "=== 2. Modernize config.yaml (backup first)"
if [ -f "$CFG" ]; then
  sudo -u hermes cp -a "$CFG" "$CFG.bak-$(date +%s)"
fi
sudo -u hermes tee "$CFG" >/dev/null <<'YAML'
# Personal Hermes profile — modernized config.
# Telegram platform, Anthropic primary with OpenAI o4-mini fallback,
# full hermes-cli toolset over the Telegram chat. Single-user; allowlist
# is set via TELEGRAM_ALLOWED_USERS in .env.

model:
  provider: anthropic
  default: claude-sonnet-4-6
  fallback_providers:
    - provider: custom
      model: o4-mini
      base_url: https://api.openai.com/v1

agent:
  reasoning_effort: medium

delegation:
  enabled: true
  max_concurrent_children: 1

platforms:
  telegram:
    enabled: true
    # allowed_users: read from TELEGRAM_ALLOWED_USERS env var

platform_toolsets:
  telegram: [hermes-cli]
YAML
echo "  wrote $CFG"

echo
echo "=== 3. Enable + start systemd unit hermes-gateway@$SLUG"
systemctl enable "hermes-gateway@$SLUG" 2>&1 | tail -2
systemctl restart "hermes-gateway@$SLUG"
sleep 7
echo "  status: $(systemctl is-active hermes-gateway@$SLUG)"

echo
echo "=== 4. Tail startup log"
sudo -u hermes tail -40 "$PROF/logs/gateway.log" 2>/dev/null | tail -30 || echo "  no gateway.log yet"

echo
echo "=== 5. Telegram connection sanity check"
if sudo -u hermes grep -q '\[telegram\] Connected' "$PROF/logs/gateway.log" 2>/dev/null; then
  echo "  ✓ Telegram platform connected"
elif sudo -u hermes grep -q '\[telegram\]' "$PROF/logs/gateway.log" 2>/dev/null; then
  sudo -u hermes grep '\[telegram\]' "$PROF/logs/gateway.log" | tail -3
else
  echo "  (no [telegram] lines yet — give it ~10s more)"
fi
