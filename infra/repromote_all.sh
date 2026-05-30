#!/usr/bin/env bash
# Re-run promote_client.sh for every active per-client gateway unit.
#
# Use this after changing the per-client Caddy fragment template
# (in promote_client.sh) so every onboarded client picks up the new shape
# without onboarding them from scratch.
#
# Usage:
#     ./repromote_all.sh <base-domain>
#
#   e.g. ./repromote_all.sh hooks.138.197.7.87.nip.io

set -euo pipefail

BASE_DOMAIN="${1:-}"
[ -n "$BASE_DOMAIN" ] || { echo "usage: $0 <base-domain>" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROMOTE="${SCRIPT_DIR}/promote_client.sh"
[ -x "$PROMOTE" ] || { echo "missing $PROMOTE" >&2; exit 1; }

# Pull slugs from every enabled-and-active hermes-gateway@<slug>.service.
mapfile -t units < <(
  systemctl list-units --type=service --state=active --no-legend \
    'hermes-gateway@*.service' | awk '{print $1}'
)

if [ "${#units[@]}" -eq 0 ]; then
  echo "no active hermes-gateway@*.service units — nothing to do"
  exit 0
fi

failed=()
for unit in "${units[@]}"; do
  slug=$(echo "$unit" | sed 's/hermes-gateway@\(.*\)\.service/\1/')
  printf '\n\033[1;36m==> re-promoting %s\033[0m\n' "$slug"
  if ! bash "$PROMOTE" "$slug" --base-domain "$BASE_DOMAIN"; then
    failed+=("$slug")
  fi
done

if [ "${#failed[@]}" -gt 0 ]; then
  echo "FAILED: ${failed[*]}" >&2
  exit 1
fi
echo
echo "re-promoted ${#units[@]} client(s)"
