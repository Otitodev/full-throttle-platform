#!/usr/bin/env bash
# One-shot: convert mrfence's model config from provider=openai (which Hermes
# doesn't ship as a first-class provider) to the canonical pattern:
#   provider: custom
#   default:  gpt-4o
#   base_url: https://api.openai.com/v1
# The `custom` provider already knows to read OPENAI_API_KEY from .env when
# base_url is api.openai.com (see hermes-agent/agent/auxiliary_client.py:4395).
#
# Safe to re-run — idempotent.

set -euo pipefail

CFG=/home/hermes/.hermes/profiles/mrfence/config.yaml
[ -f "$CFG" ] || { echo "missing $CFG" >&2; exit 1; }

# Use Python for the edit — sed is too quote-fragile when invoked through
# multiple shell layers.
sudo -u hermes python3 - "$CFG" <<'PY'
import sys, yaml, pathlib
p = pathlib.Path(sys.argv[1])
d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
d.setdefault("model", {})
d["model"]["provider"] = "custom"
d["model"].setdefault("default", "gpt-4o")
d["model"]["base_url"] = "https://api.openai.com/v1"
# Disable reasoning. gpt-4o is not a reasoning model and rejects the
# `include: ["reasoning.encrypted_content"]` line Hermes adds when reasoning
# is enabled (HTTP 400). Setting effort=none → {"enabled": False} suppresses
# the include line at the source. See hermes_constants.parse_reasoning_effort
# and run_agent.py:3883.
d.setdefault("agent", {})
d["agent"]["reasoning_effort"] = "none"
p.write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8")
print({"model": d["model"], "agent.reasoning_effort": d["agent"]["reasoning_effort"]})
PY

systemctl restart hermes-gateway@mrfence
sleep 4
echo "---"
journalctl -u hermes-gateway@mrfence -n 8 --no-pager | tail -8
