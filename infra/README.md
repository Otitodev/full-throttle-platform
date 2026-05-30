# Deployment runbook

How to take this platform from a fresh Linux droplet to a live, internet-reachable agent serving
paying clients. Subdomain-per-client routing, Caddy auto-TLS, one systemd unit per gateway.

```
fresh droplet  →  install_server.sh  →  onboard_client.py <client>  →  promote_client.sh <slug>
```

## What you need before starting

- A Debian/Ubuntu droplet (any small size; 2GB RAM is fine for ~20 clients).
- A platform domain you control (e.g. `fullthrottle.io`) — used for client webhooks.
- **One wildcard DNS A record**: `*.hooks.<domain>` → droplet's public IP. (Caddy auto-provisions
  per-subdomain certs from there.)
- SSH access; you'll run the installer as root.

## 1. Provision the server (one-time)

```bash
git clone <this repo> /srv/full-throttle
cd /srv/full-throttle
sudo bash infra/install_server.sh
```

Idempotent. Re-run safely; use `--check` to verify state, `--reinstall` to force re-copy of the
platform-managed files. Installs:

- python3, git, curl, jq, Node 20.
- **Caddy** (Cloudsmith deb repo) → enabled + running via systemd.
- **Hermes Agent** (official installer, run as the `hermes` user; symlinked to `/usr/local/bin/hermes`).
- The `hermes` system user with `/home/hermes/.hermes/` as the Hermes home.
- `/etc/full-throttle/caddy.d/` (per-client fragments land here) and `/var/log/full-throttle/`.
- `/etc/caddy/Caddyfile` (base) and `/etc/systemd/system/hermes-gateway@.service` (templated unit).

Verify:
```bash
sudo bash infra/install_server.sh --check
```

## 2. Onboard a client

From the platform repo:
```bash
python3 scripts/onboard_client.py --intake client.json --secrets client-secrets.json
```

`scripts/ONBOARDING.md` covers the intake/secrets formats and the augment-vs-greenfield modes.
The script:

- Creates `~hermes/.hermes/profiles/<slug>/` with config/skills/memory/audit/etc.
- **Allocates a unique webhook port** (`~hermes/.hermes/ports.json` registry; idempotent per slug)
  and writes it into `<profile>/config.yaml` at `platforms.webhook.extra.port`.
- Writes `<profile>/NEXT_STEPS.md` including the exact `promote_client.sh` command to run.

## 3. Promote the client to live

```bash
sudo bash infra/promote_client.sh <slug> --base-domain hooks.<your-domain>
```

This:

1. Reads the webhook port from the profile's `config.yaml`.
2. Writes `/etc/full-throttle/caddy.d/<slug>.caddy` with
   `<slug>.hooks.<domain> { reverse_proxy 127.0.0.1:<port> ... }`.
3. `systemctl enable --now hermes-gateway@<slug>.service` (the gateway starts; Restart=always).
4. `systemctl reload caddy` — Caddy provisions a TLS cert for the new subdomain on first hit.
5. Probes `https://<slug>.hooks.<domain>/healthz`.

After this, point the client's lead form / LSA / Twilio webhook at
`https://<slug>.hooks.<domain>/webhooks/lead` (HMAC-signed with `WEBHOOK_LEAD_SECRET` from the
profile `.env`). `--dry-run` prints what would happen without touching the system.

## Daily operations

Logs (per client):
```bash
sudo journalctl -u hermes-gateway@<slug> -f
sudo journalctl -u caddy -f
sudo tail -F /var/log/full-throttle/<slug>-access.log
```

Restart / stop a client:
```bash
sudo systemctl restart hermes-gateway@<slug>
sudo systemctl stop    hermes-gateway@<slug>
```

Decommission a client:
```bash
sudo systemctl disable --now hermes-gateway@<slug>
sudo rm /etc/full-throttle/caddy.d/<slug>.caddy
sudo systemctl reload caddy
# Profile + port registry stay (audit trail). Remove manually if you really need to.
```

## What this packaging does NOT do (by design)

- **DNS provisioning**: you create the `*.hooks.<domain>` wildcard A record yourself.
- **Backups**: per-client `state.db` / `memories/` / `audit.jsonl` live under `~hermes/.hermes/`.
  Snapshot the droplet or `rsync` that tree elsewhere on your own cadence.
- **Multi-droplet / HA**: this packaging is for the single-droplet "to ~30 clients" tier. The
  scaling path (kanban dispatcher + worker fleet) is documented in `ARCHITECTURE.md` §10.
- **Per-client SSH access**: agents and operators share the `hermes` user; per-profile isolation
  is at the Hermes profile boundary (`HERMES_HOME` per `hermes -p <slug>`).
