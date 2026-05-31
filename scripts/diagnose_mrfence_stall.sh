#!/usr/bin/env bash
# Diagnose why the mrfence gateway accepts webhooks but never reaches the LLM.
# Hypothesis: provider switch to Anthropic stalled on lazy SDK install / import.
#
# Checks:
#   1. Which venvs exist and which one the running gateway is from
#   2. Whether anthropic + openai SDKs are importable in the running venv
#   3. Pending pip processes (lazy install stuck)
#   4. Open network connections held by the gateway PID
#   5. Stack trace of the gateway PID via py-spy if available, else /proc state
#   6. config.yaml model section, redacted env (key prefixes only)
set -euo pipefail

SLUG="${1:-mrfence}"
PROF="/home/hermes/.hermes/profiles/$SLUG"
PID=$(systemctl show "hermes-gateway@$SLUG" -p MainPID --value)

echo "=== gateway PID=$PID"
if [ "$PID" = "0" ]; then echo "gateway not running"; exit 1; fi
PYTHON_EXE=$(readlink -f "/proc/$PID/exe" || true)
echo "exe=$PYTHON_EXE"

echo "=== gateway cwd / open files relevant"
ls -l "/proc/$PID/cwd" 2>/dev/null || true

echo "=== gateway process state"
cat "/proc/$PID/status" 2>/dev/null | grep -E "^(State|Threads|VmRSS|voluntary_ctxt|nonvoluntary_ctxt):" || true

echo "=== gateway thread states"
for t in /proc/$PID/task/*/status; do
  awk '/^Pid:/{p=$2} /^Name:/{n=$2} /^State:/{s=$2; print p, n, s}' "$t" 2>/dev/null
done | sort -u | head -30

echo "=== pip processes (lazy-install stuck?)"
pgrep -af "pip|uv|pip install" | grep -v "scripts/diagnose" || echo "none"

echo "=== open network connections for PID $PID"
ss -tnp 2>/dev/null | grep "pid=$PID" | head -20 || true

echo "=== importability of anthropic + openai in gateway venv python (not bare uv exe)"
VENV_PY="/home/hermes/.hermes/hermes-agent/venv/bin/python3"
sudo -u hermes "$VENV_PY" - <<'PY'
import importlib, time
for mod in ("anthropic", "openai", "httpx"):
    t0 = time.time()
    try:
        m = importlib.import_module(mod)
        v = getattr(m, "__version__", "?")
        print(f"{mod}: ok v={v} ({time.time()-t0:.3f}s)")
    except Exception as e:
        print(f"{mod}: FAIL {type(e).__name__}: {e}")
PY

echo "=== reverse-DNS the open TCP6 peer"
PEER=$(ss -tnp 2>/dev/null | awk -v p="pid=$PID" '$0 ~ p {print $5}' | head -1)
echo "peer raw: $PEER"
PEER_IP=$(echo "$PEER" | sed -E 's/\]?:[0-9]+$//' | tr -d '[]')
echo "peer ip: $PEER_IP"
if [ -n "$PEER_IP" ]; then
  getent hosts "$PEER_IP" 2>/dev/null || true
  # try a reverse lookup via dig if installed
  command -v dig >/dev/null 2>&1 && dig +short -x "$PEER_IP" || true
fi

echo "=== py-spy stack dump (if available)"
if command -v py-spy >/dev/null 2>&1; then
  py-spy dump --pid "$PID" 2>&1 | head -80
else
  echo "py-spy not installed; skip"
fi

echo "=== config.yaml model section"
sudo -u hermes python3 - "$PROF/config.yaml" <<'PY'
import sys, yaml, pathlib
d = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")) or {}
print(yaml.safe_dump({"model": d.get("model"), "agent": {"reasoning_effort": d.get("agent", {}).get("reasoning_effort")}}, sort_keys=False))
PY

echo "=== .env (redacted: key prefixes/lengths only)"
sudo -u hermes awk -F= '
  /^[A-Z_]+=/{
    k=$1; v=substr($0, length(k)+2);
    if (v ~ /KEY|SECRET|TOKEN/ || k ~ /KEY|SECRET|TOKEN/) {
      printf "%s=<len=%d, prefix=%s>\n", k, length(v), substr(v, 1, 8);
    } else {
      print k"="v;
    }
  }' "$PROF/.env" 2>/dev/null || echo "no .env"
