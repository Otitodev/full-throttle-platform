# AGENTS.md

## Project identity
- **Python 3.10+** only. No package.json, no npm/npx, no Rust. Dependencies: `pyyaml`, `ruff` (dev).
- Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent) (external, not in repo). The platform ships skills + scripts; Hermes is the engine.
- Augment-first philosophy: never rebuild a client's site. Publish into their existing CMS via adapters.

## Commands

```bash
# Lint (only tool)
ruff check --diff .

# Smoke-test the onboarding pipeline
python scripts/onboard_client.py --intake scripts/intake.example.json --secrets scripts/secrets.example.json --dry-run
```

There is no test framework. CI runs the two commands above — nothing else.

## Architecture (what you can't guess from filenames)

```
skills/<name>/
  SKILL.md          # metadata + instructions (Markdown)
  scripts/          # executable Python, JSON-to-stdout, NO Hermes imports
    _common.py      # shared helpers per skill
    adapters/
      base.py       # interface class
      <provider>.py # concrete adapter
      manual.py     # always-ships fallback
  references/       # setup guides (Markdown)
scripts/            # repo-level tooling (onboard_client.py, intake/secrets templates)
infra/              # deployment shell scripts (bare-metal droplet, no Docker)
```

## Conventions

- **Output format**: every script prints JSON to stdout — `{"success": true, "data": ...}` or `{"success": false, "error": "..."}` and exits non-zero on failure.
- **Adapter pattern**: every skill has a `base.py` interface + provider implementations + a `manual` adapter that always works without external APIs.
- **Secrets**: never in VCS. Keys live in `~/.hermes/profiles/<slug>/.env` (chmod 600). Templates live in `scripts/*.example.json`; actual values are gitignored.
- **State**: profile-relative via `HERMES_HOME` env var (defaults to `~/.hermes`). Never hardcode `~/.hermes`.
- **Audit**: every mutation appends to `<HERMES_HOME>/governance/audit.jsonl` (append-only, never edited). Use the `audit()` helper from each skill's `_common.py`.
- **code_execution** toolset is disabled in production profiles (written by `onboard_client.py` into `config.yaml`).
- **Idempotency per skill**: content-publisher checks slugs before publishing, review-automation tracks handled reviews in `seen.json`, social-scheduler tracks posted content in `used.json`, lead-response deduplicates by delivery_id.
- **Disciplines**: `ruff` for both linting and formatting; no separate `black`/`isort` config exists.

## Writing a new skill

1. Create `skills/<name>/` with `SKILL.md`, `scripts/`, and `references/`.
2. Add a `scripts/_common.py` with at minimum: `state_dir()`, `load_json()`, `audit()`, `fail()`, `build_adapter()`.
3. Every entry-point script accepts `--adapter` with `manual` default and prints `{"success": true/false}`.
4. Add the skill to the `SKILLS` list in `scripts/onboard_client.py` so it gets installed into client profiles.

## CI

- Trigger: push or PR to `master`
- Jobs: `ruff check --diff .` + dry-run `onboard_client.py`
- No deployment automation; infra scripts are manual.

## Key reference files

- `ARCHITECTURE.md` — full architecture, data flows, agent topology
- `REVISION.md` — v2 design decisions, deferred scope
- `skills/governance/references/scope_matrix.md` — tool-permission matrix and governance policy (G1–G5)
- `scripts/ONBOARDING.md` — operator runbook
- `infra/README.md` — deployment runbook
