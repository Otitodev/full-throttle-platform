#!/usr/bin/env bash
# Full Throttle — promote an onboarded client to live.
#
# Given a slug, this script:
#   1. derives the same deterministic webhook port the onboarding script wrote
#      into ~hermes/.hermes/profiles/<slug>/config.yaml (8645 + sha256(slug) % 300),
#   2. writes a Caddy subdomain block at /etc/full-throttle/caddy.d/<slug>.caddy,
#   3. enables + starts the systemd unit hermes-gateway@<slug>.service,
#   4. reloads Caddy,
#   5. tail-tests https://<slug>.<base-domain>/healthz.
#
# Usage (run as root or with sudo):
#     ./promote_client.sh <slug> [--base-domain hooks.example.com] [--port N] [--dry-run]
#
# Idempotent: re-running re-writes the fragment + restarts the unit.

set -euo pipefail

SLUG=""
BASE_DOMAIN="hooks.example.com"
PORT=""
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --base-domain) BASE_DOMAIN="$2"; shift 2 ;;
    --port)        PORT="$2"; shift 2 ;;
    --dry-run)     DRY=1; shift ;;
    -h|--help)     sed -n '2,18p' "$0"; exit 0 ;;
    --*)           echo "unknown flag: $1" >&2; exit 2 ;;
    *)             SLUG="$1"; shift ;;
  esac
done

[ -n "$SLUG" ] || { echo "usage: $0 <slug> [--base-domain X] [--port N] [--dry-run]" >&2; exit 2; }
[[ "$SLUG" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] || { echo "invalid slug: $SLUG" >&2; exit 2; }

PROFILE_DIR="/home/hermes/.hermes/profiles/${SLUG}"
FRAGMENT="/etc/full-throttle/caddy.d/${SLUG}.caddy"
HOST="${SLUG}.${BASE_DOMAIN}"

if [ -z "$PORT" ]; then
  # Port is the registry-allocated value the onboarding script wrote into the
  # profile's config.yaml. No hash fallback — collisions in a small range made
  # that unsafe.
  if [ -f "${PROFILE_DIR}/config.yaml" ] && command -v python3 >/dev/null; then
    PORT=$(python3 - "${PROFILE_DIR}/config.yaml" <<'PY' || true
import sys, yaml
try:
    cfg = yaml.safe_load(open(sys.argv[1], encoding='utf-8')) or {}
    print((((cfg.get('platforms') or {}).get('webhook') or {}).get('extra') or {}).get('port') or '')
except Exception:
    pass
PY
)
  fi
  if [ -z "$PORT" ]; then
    echo "no port found in ${PROFILE_DIR}/config.yaml — run onboard_client.py first, or pass --port N" >&2
    exit 1
  fi
fi

log() { printf '\033[1;36m[promote]\033[0m %s\n' "$*"; }

log "slug:        $SLUG"
log "base domain: $BASE_DOMAIN"
log "host:        https://$HOST"
log "port:        $PORT"
log "fragment:    $FRAGMENT"
log "unit:        hermes-gateway@${SLUG}.service"

FRAGMENT_CONTENT=$(cat <<EOF
${HOST} {
	handle /healthz {
		respond "ok" 200
	}

	# Owner-dashboard API → the central aggregator (binds 127.0.0.1:9201).
	# Auth is per-profile Bearer (FT_DASHBOARD_TOKEN); aggregator enforces it.
	handle /api/client/* {
		reverse_proxy 127.0.0.1:9201
	}

	# Owner dashboard SPA at /dash/*. The Vite build's base is "/dash/" so
	# all asset URLs already start with /dash/; handle_path strips that
	# prefix before file_server resolves against dist/.
	handle_path /dash/* {
		root * /srv/full-throttle-platform/dashboards/client/dist
		try_files {path} /index.html
		file_server
	}

	# Anything else (webhooks, etc.) → the per-client Hermes gateway.
	reverse_proxy 127.0.0.1:${PORT}

	request_body {
		max_size 1MB
	}

	log {
		output file /var/log/full-throttle/${SLUG}-access.log {
			roll_size 10mb
			roll_keep 5
		}
		format json
	}
}
EOF
)

# Read this client's FT_DASHBOARD_TOKEN so we can print the dashboard URL at
# the end. Falls back to empty (printing the URL without the fragment) if the
# profile was onboarded before Task 2.10 landed — in that case the SPA shows
# the NotAuthenticated state until a fresh onboard or manual token injection.
DASHBOARD_TOKEN=""
if [ -f "${PROFILE_DIR}/.env" ]; then
  DASHBOARD_TOKEN=$(grep -E '^FT_DASHBOARD_TOKEN=' "${PROFILE_DIR}/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)
fi

if [ "$DRY" -eq 1 ]; then
  log "DRY-RUN — would write fragment:"
  printf '%s\n' "$FRAGMENT_CONTENT" | sed 's/^/    /'
  log "DRY-RUN — would run:"
  echo "    systemctl enable --now hermes-gateway@${SLUG}.service"
  echo "    systemctl reload caddy"
  echo "    curl -fsSI https://${HOST}/healthz"
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "this script must be run as root (try: sudo $0 ${SLUG})" >&2; exit 1
fi

mkdir -p "$(dirname "$FRAGMENT")"
printf '%s\n' "$FRAGMENT_CONTENT" > "$FRAGMENT"
chmod 0644 "$FRAGMENT"
log "wrote $FRAGMENT"

systemctl enable --now "hermes-gateway@${SLUG}.service"
systemctl reload caddy

# Best-effort live check (cert + reverse proxy). The agent may still be starting.
sleep 1
if curl -fsSI "https://${HOST}/healthz" >/dev/null 2>&1; then
  log "live: https://${HOST}/healthz responds 200"
else
  log "live check failed (may still be provisioning the TLS cert); inspect with:"
  log "    journalctl -u hermes-gateway@${SLUG} -f"
  log "    journalctl -u caddy -f"
fi

# Owner dashboard URL. Token is delivered as a URL fragment (#token=…) so it
# never reaches access logs — the SPA reads it once, stows it in
# sessionStorage, and strips the hash before the user sees the URL bar.
if [ -n "$DASHBOARD_TOKEN" ]; then
  log "owner dashboard:"
  printf '\033[1;32m    https://%s/dash/#token=%s\033[0m\n' "$HOST" "$DASHBOARD_TOKEN"
else
  log "owner dashboard: https://${HOST}/dash/"
  log "  (no FT_DASHBOARD_TOKEN in ${PROFILE_DIR}/.env — re-run onboard_client.py to generate one)"
fi
