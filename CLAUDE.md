# CLAUDE.md

Fast index for Claude Code. **`AGENTS.md` is the source of truth** for architecture,
conventions, and per-skill expectations — read it for any non-trivial change. This
file collects the operational gotchas that are easy to fall into and aren't in
AGENTS.md.

## Where to look when something silently breaks

Hermes' gateway under systemd writes INFO-level logs to **profile-local files**,
not journald. `journalctl -u hermes-gateway@<slug>` only shows WARNING+, so if a
gateway "looks idle" but the agent is actually processing webhooks, you'll miss
everything in the journal alone.

```
~hermes/.hermes/profiles/<slug>/logs/gateway.log   # webhook receive, response send, sms events
~hermes/.hermes/profiles/<slug>/logs/agent.log     # per-turn LLM calls, tool executions, tool errors
~hermes/.hermes/profiles/<slug>/governance/audit.jsonl   # only exists after the first successful skill action
~hermes/.hermes/profiles/<slug>/sessions/sessions.json   # session state, last_active, provider, model, message_count
~hermes/.hermes/profiles/<slug>/sessions/request_dump_*  # written on non-retryable LLM errors
```

Helper scripts under `scripts/` to keep handy (avoid one-off ssh-quote hell):
- `inspect_mrfence_state.sh` / `inspect_mrfence_full.sh` — systemd PID, journal,
  session summary, recent files.
- `diagnose_mrfence_stall.sh` — gateway thread/socket state, SDK importability,
  redacted env.
- `twilio_recent.sh`, `twilio_failure_detail.sh`, `twilio_msg_body.sh` — Twilio
  Messages REST API direct fetches with status, error codes, body, segments.

## Webhook agent toolset is intentionally minimal

The default `hermes-webhook` toolset (`web_search`, `web_extract`, `vision_analyze`,
`clarify`) excludes `terminal` and `send_message` because webhook bodies are
usually untrusted (public form posts, PR titles, etc.).

For **HMAC-signed** webhook routes (lead-response, Stripe, etc.) where you control
the secret, widen the toolset explicitly in the profile's `config.yaml`:

```yaml
platform_toolsets:
  webhook: [hermes-webhook, terminal, messaging]
```

- `terminal` → `terminal` + `process` tools (runs `intake.py`, `sync_lead.py`).
- `messaging` → `send_message` tool (cross-platform delivery → SMS via the gateway's
  `sms` platform).

Canonical patcher: `scripts/patch_mrfence_webhook_toolsets.sh`. Do **NOT** widen
the toolset for unsigned webhook routes.

## Twilio: success ≠ delivered

`send_message`'s `{"status":"ok"}` reflects Twilio's create-API 201 (message queued),
not actual SMS delivery. Twilio rejects delivery downstream for many reasons that
never propagate back to the agent (the audit log still says `ok`).

When debugging "agent says it sent but customer didn't receive", **always** verify
against the Twilio Messages REST API per-SID:

```bash
bash scripts/twilio_failure_detail.sh <slug>   # account/balance/from-number/verified-caller-IDs/last 5 failures
bash scripts/twilio_recent.sh <slug> 10        # last 10 messages with status, segments, error_code
bash scripts/twilio_msg_body.sh <slug> <SID>   # full message body + error detail for one SID
```

### Twilio Trial-specific traps (only matter when `type: Trial`)

Trial accounts impose three quiet restrictions worth knowing:

1. **Forty-character prefix.** Every message is silently prepended with
   `"Sent from your Twilio trial account - "` (~40 chars). It eats into the
   segment budget but doesn't show in the body you pass in.
2. **Multi-segment cap (error 30044).** Trial accounts reject messages that span
   multiple segments. 1 GSM-7 segment = 160 chars; ONE non-GSM-7 character (em
   dash `—`, smart quotes `'"`, emoji 📋, accented letters) flips encoding to
   UCS-2 = 70 chars/segment.
3. **Verified-Caller-ID only (error 21608).** Trial can only message numbers
   verified as Caller IDs in the Twilio console.

Upgrading to a **Full** account removes the prefix, the segment cap, and the
verified-Caller-ID restriction. Mr. Fence's pilot ran into all three before the
upgrade — see the comment block at the top of `skills/lead-response/scripts/intake.py`
for why `FIRST_TOUCH` is now tightly bounded.

### First-touch SMS budget

`skills/lead-response/scripts/intake.py` enforces:
- Target ≤ 160 chars (Mr. Fence pilot renders to ~150).
- GSM-7-safe (em dashes, smart quotes, ellipsis normalized after templating).
- 160-char truncation guard for pathological business-name + message slices.

If you change the template, re-run the length probe in the file header before
committing.

## Quote-stripping over PowerShell → ssh → bash

The chain strips outer quotes, so anything more than a single bash word per arg
gets re-tokenized on the remote. Symptoms: `unknown arg: for`, `command not found`,
secrets leaking into error messages because the host treats them as positional
args.

Rules:
- Don't pass multi-word strings or `python3 -c "…"` blobs through the chain.
  Write a script file, commit, `git pull` on the droplet, then `bash <script>`.
- Don't send secrets (API keys) via remote curl invocations from your shell.
  Edit `~hermes/.hermes/profiles/<slug>/.env` directly via `sudo -u hermes nano`
  on the droplet.

## Pilot profile snapshot (Mr. Fence)

Droplet `138.197.7.87`, profile `mrfence`:

- Primary model: Anthropic `claude-sonnet-4-6` (validated 2026-06-01).
- Fallback: `custom` provider, `o4-mini`, base `https://api.openai.com/v1`
  (validated 2026-05-30; needs OpenAI org verification before reasoning models
  work).
- Reasoning effort: `low`.
- Webhook toolset: `[hermes-webhook, terminal, messaging]`.
- Twilio: Full account, FROM `+12183074659`, owner SMS `+2348127052315` (Otito
  as proxy owner during pilot).
- Lead webhook: `https://mrfence.hooks.138.197.7.87.nip.io/webhooks/lead`,
  HMAC-SHA256 signed via `WEBHOOK_LEAD_SECRET` in the profile `.env`.

Patcher scripts that set this up live in `scripts/patch_mrfence_*.sh`.
