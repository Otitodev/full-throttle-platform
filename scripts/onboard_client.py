#!/usr/bin/env python3
"""Onboard a Full Throttle client → a configured Hermes profile (augment mode).

Operator-run CLI (not a per-turn skill). Turns an intake file + a secrets file
into a ready-to-start Hermes profile under <profiles-root>/<slug>/: config.yaml,
.env, the platform skills, and seeded brand/memory context — plus a NEXT_STEPS.md
runbook of the manual steps that can't be automated offline.

Hybrid profile creation: uses `hermes profile create` if the binary is on PATH,
otherwise creates the profile layout directly (offline-testable). Plain Python +
pyyaml; no Hermes imports.

    python onboard_client.py --intake client.json --secrets secrets.json
    python onboard_client.py --intake client.json --secrets secrets.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NoReturn

import yaml

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
PROFILE_DIRS = ["memories", "sessions", "skills", "skins", "logs", "plans", "workspace", "cron", "home"]
SKILLS = ["content-publisher", "review-automation", "social-scheduler", "lead-response"]
VALID_ADAPTERS = {"wordpress-rest", "proxy-subdir", "manual"}

# secrets.json key → profile .env key (only present keys are written)
SECRET_ENV_MAP = {
    "model_api_key": None,            # resolved to provider-specific key below
    "twilio_account_sid": "TWILIO_ACCOUNT_SID",
    "twilio_auth_token": "TWILIO_AUTH_TOKEN",
    "twilio_phone_number": "TWILIO_PHONE_NUMBER",
    "wp_app_password": "WP_APP_PASSWORD",
    "jobber_access_token": "JOBBER_ACCESS_TOKEN",
    "webhook_lead_secret": "WEBHOOK_LEAD_SECRET",
}
PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def die(msg: str) -> NoReturn:
    print(json.dumps({"success": False, "error": msg}))
    raise SystemExit(1)


def load_json(path: str) -> dict:
    p = Path(path).expanduser()
    if not p.is_file():
        die(f"file not found: {p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"{p} is not valid JSON: {exc}")


# --------------------------------------------------------------------------- #

def validate(intake: dict) -> None:
    client = intake.get("client", {})
    slug = client.get("slug", "")
    if not SLUG_RE.match(slug):
        die(f"client.slug invalid (must match {SLUG_RE.pattern}): {slug!r}")
    if not client.get("business_name"):
        die("client.business_name is required")
    site = intake.get("site", {})
    if site.get("mode", "augment") != "augment":
        die("this MVP onboards site.mode == 'augment' only (greenfield deferred)")
    adapter = site.get("adapter")
    if adapter not in VALID_ADAPTERS:
        die(f"site.adapter must be one of {sorted(VALID_ADAPTERS)}; got {adapter!r}")
    if adapter == "wordpress-rest" and not site.get("wp_url"):
        die("site.adapter=wordpress-rest requires site.wp_url")
    if adapter == "proxy-subdir" and not site.get("public_base"):
        die("site.adapter=proxy-subdir requires site.public_base")


def build_config(intake: dict) -> dict:
    """Partial config.yaml — deep-merged with Hermes DEFAULT_CONFIG at load."""
    client = intake["client"]
    site = intake["site"]
    model = intake.get("model", {})
    channels = intake.get("channels", {})
    lead_route = channels.get("lead_route", "lead")

    cfg: dict = {
        "site_type": "augment",
        "publishing": {"adapter": site["adapter"]},
        "model": {
            "provider": model.get("provider", "anthropic"),
            "default": model.get("model", "claude-sonnet-4-6"),
        },
        "terminal": {"cwd": str(Path(client.get("workspace", "workspace")))},
        "platforms": {
            "webhook": {
                "extra": {
                    "routes": {
                        lead_route: {
                            "secret_env": "WEBHOOK_LEAD_SECRET",
                            "skills": ["lead-response"],
                            "prompt": (
                                "A new sales lead arrived. Use the lead-response skill: "
                                "name={name} phone={phone} email={email} source={source} "
                                "message={message}. Run intake.py, send the first-touch via "
                                "send_message, then sync_lead.py and notify the owner."
                            ),
                            "deliver": "log",
                        }
                    }
                }
            }
        },
    }
    if site["adapter"] == "wordpress-rest":
        cfg["publishing"]["wp_url"] = site["wp_url"]
        if site.get("wp_user"):
            cfg["publishing"]["wp_user"] = site["wp_user"]
    if site["adapter"] == "proxy-subdir":
        cfg["publishing"]["public_base"] = site["public_base"]

    owner = channels.get("owner_sms")
    if owner:
        cfg["platforms"]["sms"] = {"enabled": True, "allowed_users": [owner]}
    return cfg


def build_env(intake: dict, secrets: dict) -> dict:
    env: dict[str, str] = {}
    provider = intake.get("model", {}).get("provider", "anthropic")
    if secrets.get("model_api_key"):
        env[PROVIDER_KEY_ENV.get(provider, "ANTHROPIC_API_KEY")] = secrets["model_api_key"]
    for skey, ekey in SECRET_ENV_MAP.items():
        if ekey and secrets.get(skey):
            env[ekey] = secrets[skey]
    return env


def render_env_file(env: dict) -> str:
    return "".join(f"{k}={v}\n" for k, v in env.items())


def memory_md(intake: dict) -> str:
    c = intake["client"]
    services = ", ".join(intake.get("keywords", []) or c.get("services", []) or [])
    return (
        f"# {c['business_name']} — business facts\n\n"
        f"- Phone (E.164): {c.get('phone', '')}\n"
        f"- Domain: {c.get('domain', '')}\n"
        f"- Service area: {c.get('service_area', '')}\n"
        f"- Services / keywords: {services}\n"
        f"- Timezone: {c.get('timezone', '')}\n"
        f"- Site mode: augment (adapter: {intake['site']['adapter']})\n"
    )


def user_md(intake: dict) -> str:
    owner = intake.get("channels", {}).get("owner_sms", "")
    return (
        f"# Owner\n\n- Reaches the agent via SMS: {owner}\n"
        "- Prefers concise updates; approves risky changes by SMS.\n"
    )


def agents_md(intake: dict) -> str:
    c = intake["client"]
    voice = c.get("brand_voice", "direct, local, no fluff")
    return (
        f"# {c['business_name']} — agent guardrails\n\n"
        f"Brand voice: {voice}.\n\n"
        "## Hard rules\n"
        "- Real content only — never fabricate projects, reviews, or claims (E-E-A-T).\n"
        "- Augment, do not replace: publish via the configured adapter; never migrate the site.\n"
        "- Phone numbers must be E.164 for SMS.\n"
        "- Risky/destructive changes require owner approval before execution.\n"
        "- First-touch to leads uses the approved template; reply within seconds.\n"
    )


def cron_commands(slug: str, cadence: dict) -> list[str]:
    rev = cadence.get("reviews", "0 9 * * *")
    soc = cadence.get("social", "0 10 * * 1,3,5")
    con = cadence.get("content", "0 9 * * 1")
    rep = cadence.get("report", "0 8 * * 1")
    base = f"hermes -p {slug} cron add"
    return [
        f'{base} "{rev}" --skills review-automation --prompt "Fetch new reviews, draft replies, get owner approval, post."',
        f'{base} "{soc}" --skills social-scheduler --prompt "Build + publish approved real-content social posts."',
        f'{base} "{con}" --skills content-publisher --prompt "Draft + publish one real local blog post via the configured adapter."',
        f'{base} "{rep}" --prompt "Compile weekly report (leads, reviews, rankings, content) and send to the owner."',
    ]


def next_steps_md(slug: str, intake: dict, crons: list[str], hermes_present: bool) -> str:
    site = intake["site"]
    lines = [f"# Next steps — {intake['client']['business_name']} ({slug})", ""]
    lines.append("Manual steps the onboarding script can't do offline:\n")
    lines.append("1. Provision/assign a Twilio number for the owner and confirm inbound routing.")
    lines.append("2. Point the client's website lead form at the gateway webhook:")
    lines.append("   `https://<your-host>/webhooks/lead` (HMAC = WEBHOOK_LEAD_SECRET).")
    if site["adapter"] == "wordpress-rest":
        lines.append("3. Create a WordPress Application Password and confirm WP_APP_PASSWORD in .env.")
    if site["adapter"] == "proxy-subdir":
        lines.append("3. Deploy the Cloudflare Worker mapping the /blog route to our origin "
                     "(see content-publisher/references/proxy_subdir_setup.md).")
    lines.append("4. Set up GBP OAuth (business.manage) and the CRM token if using Jobber.")
    lines.append("")
    lines.append("## Cron jobs")
    if hermes_present:
        lines.append("Created automatically. Verify with `hermes -p %s cron list`." % slug)
    else:
        lines.append("`hermes` not found at onboard time — run these on the box:")
        lines.append("```")
        lines.extend(crons)
        lines.append("```")
    lines.append("")
    lines.append(f"## Start the gateway\n```\nhermes -p {slug} gateway\n```")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description="Onboard a Full Throttle client (augment mode).")
    ap.add_argument("--intake", required=True, help="intake.json (non-secret business/site config)")
    ap.add_argument("--secrets", default="", help="secrets.json (API keys → profile .env)")
    ap.add_argument("--profiles-root", default="", help="default $HERMES_HOME or ~/.hermes/profiles")
    ap.add_argument("--skills-src", default="", help="dir holding the platform skills (default: ../skills)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-provision an existing profile")
    args = ap.parse_args()

    intake = load_json(args.intake)
    validate(intake)
    secrets = load_json(args.secrets) if args.secrets else {}
    slug = intake["client"]["slug"]

    if args.profiles_root:
        root = Path(args.profiles_root).expanduser()
    elif os.environ.get("HERMES_HOME"):
        root = Path(os.environ["HERMES_HOME"]) / "profiles"
    else:
        root = Path.home() / ".hermes" / "profiles"
    profile = root / slug

    skills_src = Path(args.skills_src).expanduser() if args.skills_src else (
        Path(__file__).resolve().parent.parent / "skills"
    )

    if profile.exists() and not args.force:
        die(f"profile already exists: {profile} (use --force)")

    cfg = build_config(intake)
    env = build_env(intake, secrets)
    hermes_present = shutil.which("hermes") is not None
    crons = cron_commands(slug, intake.get("cadence", {}))

    planned = {
        "slug": slug, "profile": str(profile), "hermes_present": hermes_present,
        "config_keys": sorted(cfg.keys()), "env_keys": sorted(env.keys()),
        "skills": SKILLS, "adapter": intake["site"]["adapter"],
    }
    if args.dry_run:
        print(json.dumps({"success": True, "dry_run": True, "planned": planned}, indent=2))
        return

    # 1. Create profile (hybrid)
    if hermes_present:
        subprocess.run(["hermes", "profile", "create", slug, "--no-alias"],
                       capture_output=True, text=True, encoding="utf-8")
    profile.mkdir(parents=True, exist_ok=True)
    for d in PROFILE_DIRS:
        (profile / d).mkdir(exist_ok=True)

    # 2. config.yaml (partial overrides; deep-merged by Hermes)
    (profile / "config.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False), encoding="utf-8")

    # 3. .env (secrets), restricted perms
    env_path = profile / ".env"
    env_path.write_text(render_env_file(env), encoding="utf-8")
    try:
        env_path.chmod(0o600)
    except OSError:
        pass  # best-effort on Windows

    # 4. Install skills
    for name in SKILLS:
        src = skills_src / name
        if not src.is_dir():
            die(f"skill source not found: {src} (pass --skills-src)")
        dest = profile / "skills" / name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    # 5. Seed context
    (profile / "memories" / "MEMORY.md").write_text(memory_md(intake), encoding="utf-8")
    (profile / "memories" / "USER.md").write_text(user_md(intake), encoding="utf-8")
    (profile / "AGENTS.md").write_text(agents_md(intake), encoding="utf-8")

    # 6. Cron jobs
    if hermes_present:
        for cmd in crons:
            subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8")

    # 7. Runbook
    (profile / "NEXT_STEPS.md").write_text(
        next_steps_md(slug, intake, crons, hermes_present), encoding="utf-8")

    print(json.dumps({
        "success": True, "profile": str(profile), "adapter": intake["site"]["adapter"],
        "skills_installed": SKILLS, "env_keys": sorted(env.keys()),
        "cron_created": hermes_present, "next_steps": str(profile / "NEXT_STEPS.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
