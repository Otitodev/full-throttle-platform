#!/bin/bash
# Deploy landing page to Caddy serve path
# Run from repo root: bash scripts/deploy-landing.sh

set -e

SERVE_DIR="/srv/full-throttle-platform/landing"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Deploying landing page..."
rm -rf "$SERVE_DIR"
cp -r "$REPO_DIR/landing" "$SERVE_DIR"
echo "→ $SERVE_DIR"
echo "Done. Live at https://fullthrottle.otito.site/"
