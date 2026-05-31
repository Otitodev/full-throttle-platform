#!/usr/bin/env bash
# Probe the mrfence gateway directly on its loopback port, bypassing Caddy.
# If the gateway processes this hit, we'll see `[webhook] POST event=lead ...`
# in the journal. If not, the gateway is silently dropping or never reached.
set -euo pipefail

SLUG="${1:-mrfence}"
PORT=$(sudo -u hermes python3 -c "
import yaml, pathlib
d = yaml.safe_load(pathlib.Path('/home/hermes/.hermes/profiles/$SLUG/config.yaml').read_text())
print(((d.get('platforms') or {}).get('webhook') or {}).get('extra', {}).get('port') or 8758)
")
ENV_FILE="/home/hermes/.hermes/profiles/$SLUG/.env"
SECRET=$(sudo -u hermes grep '^WEBHOOK_LEAD_SECRET=' "$ENV_FILE" | head -1 | cut -d= -f2-)

echo "gateway port: $PORT"
echo "secret length: ${#SECRET}"
echo

BODY='{"name":"Direct Probe","phone":"+18505550199","email":"probe@example.com","source":"direct","message":"Localhost probe — bypassing Caddy"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')

echo "=== POST /webhooks/lead on 127.0.0.1:$PORT"
T0=$(date +%s.%N)
curl -sS -i -m 8 -X POST \
  -H 'Content-Type: application/json' \
  -H "X-Webhook-Signature: $SIG" \
  -d "$BODY" \
  "http://127.0.0.1:$PORT/webhooks/lead" | head -20 || echo "curl exit=$?"
T1=$(date +%s.%N)
echo
echo "elapsed: $(echo "$T1 - $T0" | bc)s"

echo
echo "=== /healthz on 127.0.0.1:$PORT"
curl -sS -i -m 5 "http://127.0.0.1:$PORT/healthz" | head -10 || echo "curl exit=$?"

echo
echo "=== journal lines from this PID since probe"
sleep 2
PID=$(systemctl show "hermes-gateway@$SLUG" -p MainPID --value)
journalctl _PID="$PID" --no-pager -n 30 | tail -25
