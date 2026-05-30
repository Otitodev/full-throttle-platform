#!/usr/bin/env bash
# Throwaway onboarding for smoke-testing the deployment slice.
# Creates a 'test' client profile in /home/hermes/.hermes/profiles/test/
# and runs onboard_client.py as the hermes user. Idempotent (--force).
#
# Usage (run as root):
#     bash scripts/test_onboard.sh

set -euo pipefail

INTAKE=/home/hermes/test.intake.json
SECRETS=/home/hermes/test.secrets.json

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root (sudo)" >&2; exit 1
fi

echo "==> writing $INTAKE"
cat > "$INTAKE" <<'JSON'
{
  "client": {
    "slug": "test",
    "business_name": "Throwaway Test Co",
    "timezone": "UTC",
    "service_area": "n/a",
    "services": ["misc"],
    "brand_voice": "test"
  },
  "site": { "mode": "augment", "adapter": "manual" },
  "channels": { "owner_sms": "+10000000000", "lead_route": "lead" },
  "crm": { "provider": "manual" },
  "model": { "provider": "anthropic", "model": "claude-sonnet-4-6" }
}
JSON

echo "==> writing $SECRETS"
cat > "$SECRETS" <<'JSON'
{
  "model_api_key": "sk-ant-test-placeholder",
  "webhook_lead_secret": "test-hmac-secret-rotate-me"
}
JSON

chown hermes:hermes "$INTAKE" "$SECRETS"
chmod 600 "$SECRETS"

echo "==> running onboard_client.py as hermes"
sudo -u hermes -i bash -c "python3 /srv/full-throttle-platform/scripts/onboard_client.py --intake $INTAKE --secrets $SECRETS --force"

echo ""
echo "==> profile contents"
ls -la /home/hermes/.hermes/profiles/test/ 2>/dev/null || echo "profile dir not created — check output above"

echo ""
echo "==> webhook port in config.yaml"
grep -A1 "webhook" /home/hermes/.hermes/profiles/test/config.yaml 2>/dev/null | head -10 || true
