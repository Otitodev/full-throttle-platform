#!/usr/bin/env bash
# Test the Anthropic API key from the mrfence profile WITHOUT echoing it.
# Makes a 5-token completion and reports HTTP status + message.
# The key is read inside the script, never exposed to argv, never printed.
set -euo pipefail

SLUG="${1:-mrfence}"
ENV_FILE="/home/hermes/.hermes/profiles/$SLUG/.env"

if ! sudo -u hermes test -f "$ENV_FILE"; then
  echo "missing $ENV_FILE" >&2; exit 1
fi

sudo -u hermes /home/hermes/.hermes/hermes-agent/venv/bin/python3 - "$ENV_FILE" <<'PY'
import os, sys, time, pathlib

env_file = pathlib.Path(sys.argv[1])
key = None
for line in env_file.read_text(encoding="utf-8").splitlines():
    if line.startswith("ANTHROPIC_API_KEY="):
        key = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
if not key:
    print("ANTHROPIC_API_KEY missing from .env"); sys.exit(2)

print(f"key length: {len(key)}, prefix: {key[:8]}...{key[-4:]}")

import anthropic
client = anthropic.Anthropic(api_key=key, timeout=30.0)

print("--- list available models ---")
try:
    models = client.models.list()
    for m in models.data[:15]:
        print(f"  {m.id}")
except Exception as e:
    print(f"  models.list FAIL: {type(e).__name__}: {e}")

candidates = [
    "claude-sonnet-4-6",                # what config.yaml says (likely invalid)
    "claude-sonnet-4-5-20250929",       # known real sonnet 4.5
    "claude-haiku-4-5-20251001",        # known real haiku 4.5
]
for model in candidates:
    print(f"--- try model={model} ---")
    t0 = time.time()
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        dt = time.time() - t0
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        print(f"  OK in {dt:.2f}s — stop_reason={resp.stop_reason}, model={resp.model}, content={text!r}")
    except anthropic.APIStatusError as e:
        dt = time.time() - t0
        print(f"  STATUS_ERR in {dt:.2f}s — {e.status_code}: {e.message}")
    except anthropic.APIConnectionError as e:
        dt = time.time() - t0
        print(f"  CONN_ERR in {dt:.2f}s — {type(e).__name__}: {e}")
    except Exception as e:
        dt = time.time() - t0
        print(f"  OTHER_ERR in {dt:.2f}s — {type(e).__name__}: {e}")
PY
