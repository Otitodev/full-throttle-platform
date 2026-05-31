#!/usr/bin/env bash
# Widen the toolset that the mrfence webhook agent gets.
#
# Hermes ships a `hermes-webhook` toolset that's intentionally minimal
# (web_search + web_extract + vision_analyze + clarify) because webhook bodies
# are usually untrusted (PR titles, public form posts). Our lead webhook is
# HMAC-signed by us, so we trust it. The lead-response skill needs:
#   - `terminal` toolset → terminal + process (to run intake.py / sync_lead.py)
#   - `messaging` toolset → send_message (to dispatch the SMS via the sms platform)
#   - `web` toolset is kept so the agent can still research the lead's area.
#
# Sets:
#   platform_toolsets:
#     webhook: [hermes-webhook, terminal, messaging]
#
# Idempotent: re-run any time.
set -euo pipefail

SLUG="${1:-mrfence}"
CFG="/home/hermes/.hermes/profiles/$SLUG/config.yaml"
[ -f "$CFG" ] || { echo "missing $CFG" >&2; exit 1; }

sudo -u hermes python3 - "$CFG" <<'PY'
import sys, yaml, pathlib
p = pathlib.Path(sys.argv[1])
d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
d.setdefault("platform_toolsets", {})
d["platform_toolsets"]["webhook"] = ["hermes-webhook", "terminal", "messaging"]
p.write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8")
print({"platform_toolsets.webhook": d["platform_toolsets"]["webhook"]})
PY

systemctl restart "hermes-gateway@$SLUG"
sleep 4
echo "--- post-restart status ---"
systemctl is-active "hermes-gateway@$SLUG"
sudo -u hermes tail -5 "/home/hermes/.hermes/profiles/$SLUG/logs/gateway.log"
