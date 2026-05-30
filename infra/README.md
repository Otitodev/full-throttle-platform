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

## Smoke-test the deployment (no real client needed)

`scripts/test_onboard.sh` provisions a throwaway `smoke` profile with a placeholder
API key and a fake phone number. Useful right after `install_server.sh` to prove
the chain works before pointing real customer traffic at the box:

```bash
sudo bash scripts/test_onboard.sh
# returns: profile created, webhook port allocated, summary JSON
sudo bash infra/promote_client.sh smoke --base-domain hooks.$(curl -s -4 ifconfig.me).nip.io
# returns: Caddy fragment written, systemd unit enabled, TLS cert obtained
```

Verify all layers:
```bash
# Caddy serving + TLS valid
curl -fsSI https://smoke.hooks.<ip>.nip.io/healthz
# Gateway listening on its allocated port
ss -tlnp | grep $(grep '^\s*port:' ~hermes/.hermes/profiles/smoke/config.yaml | awk '{print $2}')
# Webhook end-to-end: signed POST → 202 accepted
BODY='{"name":"x"}'
SECRET=$(sudo -u hermes python3 -c "import json,pathlib; print(json.loads(pathlib.Path('/home/hermes/test.secrets.json').read_text())['webhook_lead_secret'])")
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" -hex | awk '{print $2}')
curl -sS -i -X POST -H "Content-Type: application/json" -H "X-Webhook-Signature: $SIG" \
    -d "$BODY" https://smoke.hooks.<ip>.nip.io/webhooks/lead
```

Teardown when done:
```bash
sudo systemctl disable --now hermes-gateway@smoke
sudo rm /etc/full-throttle/caddy.d/smoke.caddy
sudo systemctl reload caddy
sudo rm -rf /home/hermes/.hermes/profiles/smoke
```

## Gotchas (caught during first real droplet validation)

Things that bit us provisioning the first droplet. All are now fixed in the
scripts, but if you're debugging an install they're worth knowing:

1. **Reserved profile slugs**. Hermes blocks `test`, `default`, and anything
   colliding with a system binary. Pick a slug that's specific to the client
   (e.g. `mrfence`, never `test`/`demo`/`temp`).
2. **`ifconfig.me` returns IPv6 first** if your droplet has dual stack. nip.io
   only handles IPv4-shaped subdomains; colons also break the Caddy host
   parser. Always use `curl -s -4 ifconfig.me` when scripting the IP.
3. **Caddy `request_body` body must be on separate lines** — `request_body
   { max_size 1MB }` on one line fails parse with "Unexpected next token
   after '{'". (Fixed in `promote_client.sh`.)
4. **`/var/log/full-throttle/` must be writable by `caddy:caddy`**, not
   `hermes:hermes` — Caddy writes per-client access logs there. (Fixed in
   `install_server.sh`.)
5. **`email ops@example.com` placeholder kills cert issuance**. Let's Encrypt
   rejects `example.com` as a forbidden contact domain → Caddy falls back to
   ZeroSSL → ZeroSSL rejects too many DNS labels in nip.io hostnames. Leave
   the email line out (works fine) or set a real one. (Fixed in
   `infra/caddy/Caddyfile`.)
6. **`systemctl reload caddy` doesn't always pick up global-block changes**
   (e.g. removing the `email` directive). In-memory ACME state survives.
   Use `systemctl restart caddy` after editing the global block.
7. **Webhook adapter needs `enabled: true` + a concrete `secret`**. The
   gateway loads only platforms with `enabled: true`, and the webhook
   adapter reads `route.secret` literally — no env interpolation. Onboarding
   now writes both. (Fixed in `scripts/onboard_client.py`.)
8. **Heredocs and `python3 -c` get auto-indented over SSH** on many terminal
   setups (bracketed paste / autoindent), which kills heredocs (`EOF` at
   non-column-0) and Python (`IndentationError`). Prefer one-liner commands,
   or upload a script (`scripts/test_onboard.sh` exists for this reason).

## What this packaging does NOT do (by design)

- **DNS provisioning**: you create the `*.hooks.<domain>` wildcard A record yourself.
- **Backups**: per-client `state.db` / `memories/` / `audit.jsonl` live under `~hermes/.hermes/`.
  Snapshot the droplet or `rsync` that tree elsewhere on your own cadence.
- **Multi-droplet / HA**: this packaging is for the single-droplet "to ~30 clients" tier. The
  scaling path (kanban dispatcher + worker fleet) is documented in `ARCHITECTURE.md` §10.
- **Per-client SSH access**: agents and operators share the `hermes` user; per-profile isolation
  is at the Hermes profile boundary (`HERMES_HOME` per `hermes -p <slug>`).
