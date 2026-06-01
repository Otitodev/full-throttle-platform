#!/usr/bin/env bash
# Allow the hermes-gateway systemd template to write to ~/.local/state.
#
# Why: the base unit sets ProtectHome=read-only and only whitelists
# /home/hermes/.hermes via ReadWritePaths. Hermes' Telegram (and any other
# platform that uses cross-profile scoped locks under XDG_STATE_HOME)
# writes to /home/hermes/.local/state/hermes/, which is outside the
# allowlist. Result: `OSError: [Errno 30] Read-only file system` at
# platform startup even though the underlying FS is fine.
#
# We add a drop-in (additive) so the base template stays untouched.
set -euo pipefail

DROPIN_DIR="/etc/systemd/system/hermes-gateway@.service.d"
DROPIN="$DROPIN_DIR/local-state.conf"

mkdir -p "$DROPIN_DIR"
cat > "$DROPIN" <<'CONF'
# Drop-in: extend ReadWritePaths so Hermes' XDG_STATE-anchored scoped locks
# (~/.local/state/hermes/) can be created. Required for the Telegram
# platform (and any future cross-profile-lock-using platform).
# Additive: systemd merges with the base unit's ReadWritePaths.
[Service]
ReadWritePaths=/home/hermes/.local/state
CONF
echo "wrote $DROPIN"

systemctl daemon-reload
echo "daemon reloaded"

# Restart the failed instance(s) so the new constraint takes effect.
for inst in $(systemctl list-units --all --no-pager --no-legend 'hermes-gateway@*.service' | awk '{print $1}'); do
  echo "restarting $inst"
  systemctl restart "$inst"
done

sleep 7
echo
echo "=== effective ReadWritePaths now"
systemctl show hermes-gateway@otito_socials -p ReadWritePaths --value
echo
echo "=== telegram connect status"
sudo -u hermes tail -25 /home/hermes/.hermes/profiles/otito_socials/logs/gateway.log | tail -20
