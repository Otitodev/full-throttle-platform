"""Shared helpers for content-publisher.

Dependency-free, decoupled from Hermes internals (HERMES_HOME-aware state). Ports
slugify/build_frontmatter/git from the retired seo-blog-publisher, plus a minimal
markdown→HTML converter for the WordPress/manual adapters. Mirrors the other
skills' _common.py.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import NoReturn


# ----- slug / frontmatter (ported from seo-blog-publisher) -------------------

def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return re.sub(r"-{2,}", "-", value)


def _yaml_escape(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_frontmatter(post) -> str:
    lines = ["---"]
    lines.append(f"title: {_yaml_escape(post.title)}")
    lines.append(f"excerpt: {_yaml_escape(post.excerpt)}")
    lines.append(f"category: {_yaml_escape(post.category)}")
    lines.append(f"pubDate: {post.pub_date}")
    if post.keyword:
        lines.append(f"keyword: {_yaml_escape(post.keyword)}")
    lines.append(f"author: {_yaml_escape(post.author)}")
    lines.append(f"draft: {'true' if post.draft else 'false'}")
    lines.append("---")
    return "\n".join(lines)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


# ----- minimal markdown → HTML (covers what our posts use) -------------------

def md_to_html(md: str) -> str:
    """h2/h3, paragraphs, ul/ol, **bold**, [text](url). Not a full Markdown engine —
    deliberately limited to the elements our content uses + escapes the rest."""
    def inline(text: str) -> str:
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        return text

    html: list[str] = []
    lines = md.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.startswith("### "):
            html.append(f"<h3>{inline(line[4:].strip())}</h3>")
            i += 1
        elif line.startswith("## "):
            html.append(f"<h2>{inline(line[3:].strip())}</h2>")
            i += 1
        elif re.match(r"^[-*] ", line):
            items = []
            while i < len(lines) and re.match(r"^[-*] ", lines[i].rstrip()):
                items.append(f"<li>{inline(lines[i].rstrip()[2:].strip())}</li>")
                i += 1
            html.append("<ul>" + "".join(items) + "</ul>")
        elif re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i].rstrip()):
                items.append(f"<li>{inline(re.sub(r'^\d+\. ', '', lines[i].rstrip()).strip())}</li>")
                i += 1
            html.append("<ol>" + "".join(items) + "</ol>")
        else:
            para = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#{2,3} |[-*] |\d+\. )", lines[i]):
                para.append(lines[i].rstrip())
                i += 1
            html.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(html)


# ----- state / adapter factory ----------------------------------------------

def state_dir(override: str | None = None) -> Path:
    if override:
        base = Path(override).expanduser()
    else:
        home = Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
        base = home / "content-publisher"
    base.mkdir(parents=True, exist_ok=True)
    return base


def build_adapter(args):
    if args.adapter == "astro-git":
        from adapters.astro_git import AstroGitAdapter
        return AstroGitAdapter(repo=getattr(args, "repo", None), commit=getattr(args, "commit", False),
                               overwrite=getattr(args, "overwrite", False))
    if args.adapter == "proxy-subdir":
        from adapters.proxy_subdir import ProxySubdirAdapter
        return ProxySubdirAdapter(repo=getattr(args, "repo", None), commit=getattr(args, "commit", False),
                                  overwrite=getattr(args, "overwrite", False),
                                  public_base=getattr(args, "public_base", None))
    if args.adapter == "wordpress-rest":
        from adapters.wordpress_rest import WordPressRestAdapter
        return WordPressRestAdapter(wp_url=getattr(args, "wp_url", None), wp_user=getattr(args, "wp_user", None),
                                    categories=getattr(args, "categories", None),
                                    overwrite=getattr(args, "overwrite", False),
                                    dry_run=getattr(args, "dry_run", False))
    if args.adapter == "manual":
        from adapters.manual import ManualAdapter
        outbox = getattr(args, "outbox_dir", None) or str(state_dir(getattr(args, "state_dir", None)))
        return ManualAdapter(outbox_dir=outbox)
    raise ValueError(f"unknown adapter: {args.adapter}")


def add_adapter_args(parser):
    parser.add_argument("--adapter", choices=["astro-git", "wordpress-rest", "proxy-subdir", "manual"],
                        default="astro-git")
    parser.add_argument("--repo", help="[astro-git/proxy-subdir] Astro repo root")
    parser.add_argument("--commit", action="store_true", help="[astro-git/proxy-subdir] git commit")
    parser.add_argument("--public-base", help="[proxy-subdir] client domain, e.g. https://client.com")
    parser.add_argument("--wp-url", help="[wordpress-rest] site root, e.g. https://client.com")
    parser.add_argument("--wp-user", help="[wordpress-rest] WP username")
    parser.add_argument("--categories", help="[wordpress-rest] comma list of category IDs")
    parser.add_argument("--outbox-dir", help="[manual] dir for the rendered post")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing post of the same slug")
    parser.add_argument("--dry-run", action="store_true", help="preview a mutation without performing it")
    parser.add_argument("--state-dir", help="override profile state dir")


def fail(message: str) -> NoReturn:
    print(json.dumps({"success": False, "error": message}))
    raise SystemExit(1)
