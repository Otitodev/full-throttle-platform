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
import hashlib
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
SKILLS = ["content-publisher", "review-automation", "social-scheduler", "lead-response", "governance"]
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
    mode = site.get("mode", "augment")
    if mode not in {"augment", "greenfield"}:
        die(f"site.mode must be 'augment' or 'greenfield'; got {mode!r}")
    if mode == "augment":
        adapter = site.get("adapter")
        if adapter not in VALID_ADAPTERS:
            die(f"site.adapter must be one of {sorted(VALID_ADAPTERS)}; got {adapter!r}")
        if adapter == "wordpress-rest" and not site.get("wp_url"):
            die("site.adapter=wordpress-rest requires site.wp_url")
        if adapter == "proxy-subdir" and not site.get("public_base"):
            die("site.adapter=proxy-subdir requires site.public_base")
    else:  # greenfield
        if not site.get("template_repo"):
            die("site.mode=greenfield requires site.template_repo (path to the Astro template)")
        if not site.get("repo_dest"):
            die("site.mode=greenfield requires site.repo_dest (where to create the client site repo)")


PORT_BASE = 8645
PORT_SPAN = 1000   # 8645..9644 — comfortably more than the planned client count


def allocate_port(slug: str, profiles_root: Path) -> int:
    """Allocate a unique webhook port per client and persist the mapping.

    Hash-only allocation collides quickly (birthday paradox: ~25 clients with a
    300-port range is already >50% likely to collide). So we keep a small
    registry file `<HERMES_HOME>/ports.json` next to `profiles/`. The slug's
    hash chooses the *starting point*, then we probe forward until we find a
    free port — same slug always gets the same port (idempotent re-onboarding),
    and we never assign two clients the same port.
    """
    home = profiles_root.parent
    reg_path = home / "ports.json"
    reg: dict = {}
    if reg_path.is_file():
        try:
            reg = json.loads(reg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            reg = {}
    if slug in reg:
        return int(reg[slug])
    used = set(int(v) for v in reg.values())
    start_offset = int(hashlib.sha256(slug.encode("utf-8")).hexdigest(), 16) % PORT_SPAN
    for i in range(PORT_SPAN):
        cand = PORT_BASE + (start_offset + i) % PORT_SPAN
        if cand not in used:
            reg[slug] = cand
            reg_path.parent.mkdir(parents=True, exist_ok=True)
            reg_path.write_text(json.dumps(reg, indent=2, sort_keys=True), encoding="utf-8")
            return cand
    raise RuntimeError(f"no free port in {PORT_BASE}..{PORT_BASE + PORT_SPAN - 1}")


def build_config(intake: dict) -> dict:
    """Partial config.yaml — deep-merged with Hermes DEFAULT_CONFIG at load."""
    client = intake["client"]
    site = intake["site"]
    model = intake.get("model", {})
    channels = intake.get("channels", {})
    lead_route = channels.get("lead_route", "lead")

    mode = site.get("mode", "augment")
    cfg: dict = {
        "site_type": mode,
        # Governance (G1): no unrestricted code execution in production.
        "agent": {"disabled_toolsets": ["code_execution"]},
        "publishing": {"adapter": site["adapter"]} if mode == "augment" else {},
        "model": {
            "provider": model.get("provider", "anthropic"),
            "default": model.get("model", "claude-sonnet-4-6"),
        },
        "terminal": {"cwd": str(Path(client.get("workspace", "workspace")))},
        "platforms": {
            "webhook": {
                # Hermes gateway only starts the HTTP listener for platforms with
                # enabled: true. Without this flag the gateway runs cron-only and
                # /webhooks/* returns 502 at the Caddy layer.
                "enabled": True,
                "extra": {
                    # `port` is injected by main() after allocate_port() (registry-based,
                    # collision-free; same slug always gets the same port).
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
    if mode == "greenfield":
        # We own + commit the client's Astro site; publish via astro-git.
        cfg["publishing"] = {"adapter": "astro-git", "repo": site["repo_dest"]}
        cfg["terminal"] = {"cwd": site["repo_dest"]}
    elif site["adapter"] == "wordpress-rest":
        cfg["publishing"]["wp_url"] = site["wp_url"]
        if site.get("wp_user"):
            cfg["publishing"]["wp_user"] = site["wp_user"]
    elif site["adapter"] == "proxy-subdir":
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


def synthesize_business(intake: dict) -> dict:
    """Build the site's business.json from the intake (operator-provided
    site.business wins; otherwise derive sensible defaults from client fields)."""
    c = intake["client"]
    site = intake["site"]
    name = c["business_name"]
    digits = "".join(ch for ch in str(c.get("phone", "")) if ch.isdigit())
    base = {
        "name": name,
        "nameShort": name.upper(),
        "nameTitle": name,
        "nameSuffix": "",
        "foundedYear": c.get("founded_year", 2020),
        "yearsServing": c.get("years_serving", "10+"),
        "tagline": c.get("tagline", f"{c.get('location_primary', 'your area')}'s trusted fencing contractor."),
        "phone": {"display": c.get("phone", ""), "href": f"tel:{digits}" if digits else ""},
        "siteUrl": f"https://{c['domain']}" if c.get("domain") else "",
        "estimateUrl": c.get("estimate_url", ""),
        "gtmId": c.get("gtm_id", ""),
        "location": {
            "primary": c.get("location_primary", ""),
            "region": c.get("region", ""),
            "state": c.get("state", ""),
            "stateAbbr": c.get("state_abbr", ""),
        },
        "citiesCount": c.get("cities_count", "20+"),
        "rating": c.get("rating", "5★"),
        "hours": c.get("hours", "Mon – Fri · 8am – 5pm"),
        "services": c.get("services", []),
        "socials": c.get("socials", {"facebook": "", "instagram": "", "youtube": "", "tiktok": ""}),
        "logo": c.get("logo", "/images/logo-sm-white.png"),
    }
    base.update(site.get("business", {}))  # explicit business block overrides
    return base


def provision_greenfield_site(intake: dict) -> dict:
    """Clone the Astro template to the client site repo and inject business.json
    (+ locations.json). Returns a summary dict."""
    site = intake["site"]
    template = Path(site["template_repo"]).expanduser().resolve()
    dest = Path(site["repo_dest"]).expanduser().resolve()
    if not (template / "src").is_dir():
        die(f"template_repo doesn't look like an Astro site (no src/): {template}")
    if dest.exists() and any(dest.iterdir()):
        die(f"repo_dest is not empty: {dest} (refusing to overwrite a non-empty dir)")

    shutil.copytree(template, dest,
                    ignore=shutil.ignore_patterns("node_modules", "dist", ".git", ".astro"))
    data_dir = dest / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "business.json").write_text(
        json.dumps(synthesize_business(intake), indent=2), encoding="utf-8")
    if site.get("cities"):
        (dest / "src" / "content" / "locations.json").write_text(
            json.dumps(site["cities"], indent=2), encoding="utf-8")

    subprocess.run(["git", "init", "-q", str(dest)], capture_output=True, text=True, encoding="utf-8")
    subprocess.run(["git", "-C", str(dest), "add", "-A"], capture_output=True, text=True, encoding="utf-8")
    subprocess.run(["git", "-C", str(dest), "-c", "user.email=onboard@fullthrottle.local",
                    "-c", "user.name=Full Throttle", "commit", "-q", "-m",
                    "chore: initialize client site from template"],
                   capture_output=True, text=True, encoding="utf-8")
    return {"template": str(template), "dest": str(dest),
            "business_json": str(data_dir / "business.json")}


def render_env_file(env: dict) -> str:
    return "".join(f"{k}={v}\n" for k, v in env.items())


def memory_md(intake: dict) -> str:
    c = intake["client"]
    site = intake["site"]
    mode = site.get("mode", "augment")
    adapter = "astro-git" if mode == "greenfield" else site.get("adapter", "")
    services = ", ".join(intake.get("keywords", []) or c.get("services", []) or [])
    return (
        f"# {c['business_name']} — business facts\n\n"
        f"- Phone (E.164): {c.get('phone', '')}\n"
        f"- Domain: {c.get('domain', '')}\n"
        f"- Service area: {c.get('service_area', '')}\n"
        f"- Services / keywords: {services}\n"
        f"- Timezone: {c.get('timezone', '')}\n"
        f"- Site mode: {mode} (adapter: {adapter})\n"
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
        "- First-touch to leads uses the approved template; reply within seconds.\n\n"
        "## Governance (see the governance skill)\n"
        "- Before a risky mutation, emit a plan (governance plan.py) and gate it with clarify.\n"
        "- Delegate workers with role=\"leaf\" and only the toolsets their job needs "
        "(see governance/references/scope_matrix.md).\n"
        "- Every external mutation is audited automatically; use governance status.py to review "
        "and revert.py to roll back.\n"
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


def next_steps_md(slug: str, intake: dict, crons: list[str], hermes_present: bool,
                  port: int, suggested_host: str) -> str:
    site = intake["site"]
    mode = site.get("mode", "augment")
    lines = [f"# Next steps — {intake['client']['business_name']} ({slug})", ""]
    lines.append("Manual steps the onboarding script can't do offline:\n")
    lines.append("1. Provision/assign a Twilio number for the owner and confirm inbound routing.")
    lines.append(f"2. Point the client's website lead form at the gateway webhook:")
    lines.append(f"   `https://{suggested_host}/webhooks/lead` (HMAC = WEBHOOK_LEAD_SECRET).")
    if mode == "greenfield":
        lines.append(f"3. In the cloned site (`{site.get('repo_dest')}`): `npm install && npm run build`, "
                     "then deploy to Vercel and point the client's domain at it.")
    elif site.get("adapter") == "wordpress-rest":
        lines.append("3. Create a WordPress Application Password and confirm WP_APP_PASSWORD in .env.")
    elif site.get("adapter") == "proxy-subdir":
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
    lines.append("## Promote to live (production droplet)")
    lines.append(f"On the server, after `install_server.sh`:\n```\nsudo infra/promote_client.sh "
                 f"{slug} --base-domain {suggested_host.split('.', 1)[1] if '.' in suggested_host else 'hooks.example.com'}\n```")
    lines.append(f"This wires Caddy `{suggested_host} → 127.0.0.1:{port}`, enables "
                 f"`hermes-gateway@{slug}.service`, and reloads Caddy.")
    lines.append("")
    lines.append(f"## Or start the gateway manually (dev / non-systemd)\n```\nhermes -p {slug} gateway\n```\n"
                 f"(listens on port {port})")
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

    mode = intake["site"].get("mode", "augment")
    adapter = "astro-git" if mode == "greenfield" else intake["site"]["adapter"]
    port = allocate_port(slug, root)
    base_domain = intake.get("channels", {}).get("public_base_domain", "hooks.example.com")
    suggested_host = f"{slug}.{base_domain}"
    cfg = build_config(intake)
    cfg["platforms"]["webhook"]["extra"]["port"] = port
    env = build_env(intake, secrets)
    hermes_present = shutil.which("hermes") is not None
    crons = cron_commands(slug, intake.get("cadence", {}))

    planned = {
        "slug": slug, "profile": str(profile), "mode": mode, "hermes_present": hermes_present,
        "config_keys": sorted(cfg.keys()), "env_keys": sorted(env.keys()),
        "skills": SKILLS, "adapter": adapter,
        "webhook_port": port, "suggested_host": suggested_host,
    }
    if mode == "greenfield":
        planned["site_dest"] = str(Path(intake["site"]["repo_dest"]).expanduser())
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

    # 5b. Greenfield: clone the Astro template + inject business.json/locations.json
    site_info = provision_greenfield_site(intake) if mode == "greenfield" else None

    # 6. Cron jobs
    if hermes_present:
        for cmd in crons:
            subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8")

    # 7. Runbook
    (profile / "NEXT_STEPS.md").write_text(
        next_steps_md(slug, intake, crons, hermes_present, port, suggested_host), encoding="utf-8")

    print(json.dumps({
        "success": True, "profile": str(profile), "mode": mode, "adapter": adapter,
        "skills_installed": SKILLS, "env_keys": sorted(env.keys()),
        "cron_created": hermes_present, "site": site_info,
        "webhook_port": port, "suggested_host": suggested_host,
        "next_steps": str(profile / "NEXT_STEPS.md"),
    }, indent=2))


if __name__ == "__main__":
    main()
