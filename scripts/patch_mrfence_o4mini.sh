#!/usr/bin/env bash
# Re-point mrfence's model to OpenAI o4-mini (reasoning model, supports the
# `include: ["reasoning.encrypted_content"]` Hermes sends). Sets
# agent.reasoning_effort=low because o4-mini reasons natively, but we don't
# need expensive depth for lead-response.

set -euo pipefail

CFG=/home/hermes/.hermes/profiles/mrfence/config.yaml
[ -f "$CFG" ] || { echo "missing $CFG" >&2; exit 1; }

sudo -u hermes python3 - "$CFG" <<'PY'
import sys, yaml, pathlib
p = pathlib.Path(sys.argv[1])
d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
d.setdefault("model", {})
d["model"]["provider"] = "custom"
d["model"]["default"] = "o4-mini"
d["model"]["base_url"] = "https://api.openai.com/v1"
d.setdefault("agent", {})
d["agent"]["reasoning_effort"] = "low"
p.write_text(yaml.safe_dump(d, sort_keys=False), encoding="utf-8")
print({"model": d["model"], "agent.reasoning_effort": d["agent"]["reasoning_effort"]})
PY

systemctl restart hermes-gateway@mrfence
sleep 5
echo "---"
journalctl -u hermes-gateway@mrfence -n 12 --no-pager | tail -10
