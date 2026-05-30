#!/usr/bin/env bash
# Re-point mrfence's model to Anthropic Claude Sonnet 4.6 (primary), keeping
# OpenAI o4-mini as a fallback when Anthropic 5xxs or rate-limits.
#
# Prerequisite: ANTHROPIC_API_KEY must be present in
# /home/hermes/.hermes/profiles/mrfence/.env (the .env is gitignored and
# hermes-owned mode 600; add the line with `sudo -u hermes nano <env>`).
#
# Idempotent: re-run any time you want to reset the model config.

set -euo pipefail

CFG=/home/hermes/.hermes/profiles/mrfence/config.yaml
ENV_FILE=/home/hermes/.hermes/profiles/mrfence/.env
[ -f "$CFG" ] || { echo "missing $CFG" >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE" >&2; exit 1; }

if ! grep -q '^ANTHROPIC_API_KEY=' "$ENV_FILE"; then
  echo "ANTHROPIC_API_KEY missing from $ENV_FILE" >&2
  echo "Edit it first: sudo -u hermes nano $ENV_FILE" >&2
  exit 1
fi

sudo -u hermes python3 - "$CFG" <<'PY'
import sys, yaml, pathlib
p = pathlib.Path(sys.argv[1])
d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
d.setdefault("model", {})
d["model"]["provider"] = "anthropic"
d["model"]["default"] = "claude-sonnet-4-6"
# Anthropic doesn't need base_url; drop any leftover from the OpenAI run.
d["model"].pop("base_url", None)
# Keep OpenAI o4-mini as fallback: if Anthropic 5xxs or auth-fails, Hermes
# transparently rolls over.
d["model"]["fallback_providers"] = [
    {"provider": "custom", "model": "o4-mini",
     "base_url": "https://api.openai.com/v1"}
]
# Anthropic reads reasoning differently; keep effort=low for cheaper turns.
d.setdefault("agent", {})
d["agent"]["reasoning_effort"] = "low"
p.write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8")
print({"model": d["model"], "agent.reasoning_effort": d["agent"]["reasoning_effort"]})
PY

systemctl restart hermes-gateway@mrfence
sleep 5
echo "---"
journalctl -u hermes-gateway@mrfence -n 14 --no-pager | tail -12
