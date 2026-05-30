#!/usr/bin/env bash
# Full Throttle — one-shot server bootstrap (Debian/Ubuntu).
#
# Installs system deps, Hermes, Node, Caddy, creates a hermes user, drops the
# base Caddyfile + systemd template, and enables Caddy. Idempotent: re-running
# is safe; existing things are left alone unless --reinstall is passed.
#
# Usage (run as root or with sudo):
#     ./install_server.sh                     # provision
#     ./install_server.sh --check             # verify everything is in place; don't install
#     ./install_server.sh --reinstall         # force reinstall of platform-managed files
#
# What it does NOT do (intentional):
#   - Configure DNS (you point *.hooks.<domain> at this droplet's IP yourself).
#   - Onboard a client (use scripts/onboard_client.py for that).
#   - Promote a client to live (use infra/promote_client.sh for that).

set -euo pipefail

MODE="install"
case "${1:-}" in
  --check) MODE="check" ;;
  --reinstall) MODE="reinstall" ;;
  "" ) ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac

INFRA_DIR="$(cd "$(dirname "$0")" && pwd)"
PLATFORM_DIR="$(cd "${INFRA_DIR}/.." && pwd)"

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "this script must be run as root (try: sudo $0)" >&2; exit 1
  fi
}

log() { printf '\033[1;36m[install]\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m[ ok ]\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }

apt_install() {
  log "apt: install $*"
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@"
}

step_apt_base() {
  log "apt update + base packages"
  DEBIAN_FRONTEND=noninteractive apt-get update -y
  apt_install ca-certificates curl gnupg lsb-release git python3 python3-pip python3-venv jq
}

step_node() {
  if command -v node >/dev/null 2>&1; then
    ok "node already installed: $(node -v)"; return
  fi
  log "installing Node.js 20 (NodeSource)"
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt_install nodejs
}

step_caddy() {
  if command -v caddy >/dev/null 2>&1; then
    ok "caddy already installed: $(caddy version | head -1)"; return
  fi
  log "installing Caddy (cloudsmith deb repo)"
  curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  DEBIAN_FRONTEND=noninteractive apt-get update -y
  apt_install caddy
}

step_user() {
  if id hermes >/dev/null 2>&1; then
    ok "hermes user already exists"
  else
    log "creating hermes user"
    useradd --create-home --shell /bin/bash hermes
  fi
}

step_hermes() {
  if sudo -u hermes -i bash -c 'command -v hermes >/dev/null 2>&1'; then
    ok "hermes binary already installed"; return
  fi
  log "installing Hermes Agent (official installer, as the hermes user)"
  sudo -u hermes -i bash -c 'curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash'
  # Place a symlink for systemd ExecStart to be predictable
  if [ -x /home/hermes/.local/bin/hermes ] && [ ! -e /usr/local/bin/hermes ]; then
    ln -sf /home/hermes/.local/bin/hermes /usr/local/bin/hermes
  fi
}

step_dirs() {
  log "creating /etc/full-throttle and /var/log/full-throttle"
  mkdir -p /etc/full-throttle/caddy.d /var/log/full-throttle
  chown -R hermes:hermes /var/log/full-throttle
}

step_caddyfile() {
  if [ -f /etc/caddy/Caddyfile ] && [ "$MODE" != "reinstall" ]; then
    if ! grep -q '/etc/full-throttle/caddy.d' /etc/caddy/Caddyfile; then
      warn "/etc/caddy/Caddyfile exists but doesn't import /etc/full-throttle/caddy.d/*.caddy"
      warn "  add: import /etc/full-throttle/caddy.d/*.caddy"
    else
      ok "/etc/caddy/Caddyfile already references the platform caddy.d dir"
    fi
  else
    log "installing base Caddyfile"
    install -m 0644 "${INFRA_DIR}/caddy/Caddyfile" /etc/caddy/Caddyfile
  fi
}

step_systemd_unit() {
  if [ -f /etc/systemd/system/hermes-gateway@.service ] && [ "$MODE" != "reinstall" ]; then
    ok "hermes-gateway@.service already installed"; return
  fi
  log "installing systemd template unit hermes-gateway@.service"
  install -m 0644 "${INFRA_DIR}/systemd/hermes-gateway@.service" /etc/systemd/system/hermes-gateway@.service
  systemctl daemon-reload
}

step_enable_caddy() {
  log "enabling + starting Caddy"
  systemctl enable --now caddy
  systemctl reload caddy || systemctl restart caddy
}

step_check() {
  log "checking install state"
  command -v hermes >/dev/null && ok "hermes:    $(command -v hermes)" || warn "hermes:    MISSING"
  command -v caddy  >/dev/null && ok "caddy:     $(caddy version | head -1)" || warn "caddy:     MISSING"
  command -v node   >/dev/null && ok "node:      $(node -v)" || warn "node:      MISSING"
  id hermes        >/dev/null 2>&1 && ok "user:      hermes" || warn "user:      MISSING"
  [ -d /etc/full-throttle/caddy.d ] && ok "caddy.d:   /etc/full-throttle/caddy.d" || warn "caddy.d:   MISSING"
  [ -f /etc/systemd/system/hermes-gateway@.service ] && ok "unit:      hermes-gateway@.service" || warn "unit:      MISSING"
  systemctl is-active --quiet caddy && ok "caddy:     active" || warn "caddy:     not running"
}

require_root
log "platform repo: ${PLATFORM_DIR}"

if [ "$MODE" = "check" ]; then
  step_check
  exit 0
fi

step_apt_base
step_node
step_caddy
step_user
step_hermes
step_dirs
step_caddyfile
step_systemd_unit
step_enable_caddy
step_check

log "done. next: onboard a client (scripts/onboard_client.py) then promote (infra/promote_client.sh)."
