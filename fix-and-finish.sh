#!/bin/bash
# fix-and-finish-hermes — one-shot: install missing deps + finish Hermes + complete platform setup
set -euo pipefail

echo "=== 1/3: Installing missing packages (ripgrep, ffmpeg, build tools) ==="
apt-get install -y ripgrep ffmpeg build-essential python3-dev libffi-dev

echo ""
echo "=== 2/3: Finishing Hermes install as hermes user ==="
sudo -u hermes -i bash -c 'curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash'

echo ""
echo "=== 3/3: Running full platform setup ==="
bash /srv/full-throttle-platform/infra/install_server.sh

echo ""
echo "Done. Run this to verify: start-hermes"
