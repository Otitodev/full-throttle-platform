# Client onboarding runbook

`onboard_client.py` provisions a new client as an isolated Hermes profile (augment mode):
config, secrets, the four platform skills, and seeded brand/memory context. It does the
offline-automatable parts; external setup (Twilio number, OAuth, web-form wiring, proxy Worker)
is listed in the generated `NEXT_STEPS.md`.

## Inputs

- **`intake.json`** — non-secret business + site + channel + cadence config (safe to keep / commit
  per client if you want). See `intake.example.json`.
- **`secrets.json`** — API keys, written into the profile `.env`. **Gitignored — never commit.**
  See `secrets.example.json`. Only the keys you provide are written.

## Run

```
# Preview (writes nothing)
python scripts/onboard_client.py --intake intake.json --secrets secrets.json --dry-run

# Provision
python scripts/onboard_client.py --intake intake.json --secrets secrets.json
```

Flags: `--profiles-root` (default `$HERMES_HOME` else `~/.hermes/profiles`), `--skills-src`
(default this repo's `skills/`), `--force` (re-provision an existing profile).

## What it produces

`<profiles-root>/<slug>/`:
- `config.yaml` — partial overrides (model, `site_type: augment`, publishing adapter, the lead
  webhook route, owner SMS). Deep-merged with Hermes defaults at load.
- `.env` — secrets (chmod 600).
- `skills/` — content-publisher, review-automation, social-scheduler, lead-response.
- `memories/MEMORY.md` + `USER.md`, `AGENTS.md` — brand voice, facts, guardrails.
- `NEXT_STEPS.md` — the manual finish-up checklist.
- cron jobs (created automatically if `hermes` is on PATH; otherwise the commands are in NEXT_STEPS).

## Profile creation modes

- If `hermes` is on PATH → runs `hermes profile create <slug>` (authoritative scaffolding) and
  overlays our config/skills/memory.
- Otherwise → creates the profile layout directly (the standard subdirs). Same result for our
  purposes; useful in CI/dev without the binary.

## Finish on the box

After running, complete `NEXT_STEPS.md`, then:

```
hermes -p <slug> gateway          # or a systemd unit per client
```

## Adding a client at scale

Beyond ~20–30 profiles, move from one gateway-process-per-client to the kanban dispatcher +
worker fleet (see ARCHITECTURE.md §10). The onboarding inputs stay the same.
