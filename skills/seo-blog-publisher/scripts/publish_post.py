#!/usr/bin/env python3
"""Publish an SEO blog post into a client's Astro site.

Writes a frontmatter'd Markdown file into <repo>/src/content/blog/<slug>.md so
the Astro `blog` collection renders it at /blog/<slug>. Optionally git-commits
the new file. Cross-platform (no shell-isms; explicit UTF-8 everywhere).

Example:
    python publish_post.py \\
        --repo /path/to/mrfence-site \\
        --title "How Much Does a Vinyl Fence Cost in Panama City?" \\
        --category "Cost Guide" \\
        --excerpt "Real per-foot pricing for vinyl fencing in Bay County." \\
        --keyword "vinyl fence cost panama city" \\
        --body-file /tmp/post.md \\
        --commit

The body may be passed inline with --body or from a file with --body-file.
Output is a single JSON object on stdout (success/path/slug/committed).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return re.sub(r"-{2,}", "-", value)


def yaml_escape(value: str) -> str:
    # Double-quote and escape so colons/quotes in titles can't break frontmatter.
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for key in ("title", "excerpt", "category"):
        lines.append(f"{key}: {yaml_escape(meta[key])}")
    lines.append(f"pubDate: {meta['pubDate']}")
    if meta.get("keyword"):
        lines.append(f"keyword: {yaml_escape(meta['keyword'])}")
    lines.append(f"author: {yaml_escape(meta['author'])}")
    lines.append(f"draft: {'true' if meta['draft'] else 'false'}")
    lines.append("---")
    return "\n".join(lines)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def fail(message: str) -> None:
    print(json.dumps({"success": False, "error": message}))
    sys.exit(1)


def main() -> None:
    p = argparse.ArgumentParser(description="Publish an SEO blog post to an Astro site.")
    p.add_argument("--repo", required=True, help="Path to the client's Astro repo root.")
    p.add_argument("--title", required=True)
    p.add_argument("--category", required=True, help='e.g. "Buying Guide", "Cost Guide".')
    p.add_argument("--excerpt", required=True, help="1-2 sentence meta/preview blurb.")
    p.add_argument("--keyword", default="", help="Primary target keyword (optional).")
    p.add_argument("--author", default="Mr. Fence of Florida")
    p.add_argument("--date", default=date.today().isoformat(), help="pubDate (YYYY-MM-DD).")
    p.add_argument("--slug", default="", help="Override the auto-generated slug.")
    p.add_argument("--body", default="", help="Markdown body (inline).")
    p.add_argument("--body-file", default="", help="Path to a file holding the Markdown body.")
    p.add_argument("--draft", action="store_true", help="Mark as draft (won't render/list).")
    p.add_argument("--overwrite", action="store_true", help="Allow overwriting an existing post.")
    p.add_argument("--commit", action="store_true", help="git add + commit the new file.")
    args = p.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    blog_dir = repo / "src" / "content" / "blog"
    if not blog_dir.is_dir():
        fail(f"blog collection dir not found: {blog_dir} (is --repo the Astro root?)")

    body = args.body
    if args.body_file:
        bf = Path(args.body_file).expanduser()
        if not bf.is_file():
            fail(f"--body-file not found: {bf}")
        body = bf.read_text(encoding="utf-8")
    body = body.strip()
    if not body:
        fail("post body is empty (pass --body or --body-file)")

    slug = slugify(args.slug or args.title)
    if not slug:
        fail("could not derive a slug from the title")

    out_path = blog_dir / f"{slug}.md"
    if out_path.exists() and not args.overwrite:
        fail(f"post already exists: {out_path} (use --overwrite to replace)")

    meta = {
        "title": args.title,
        "excerpt": args.excerpt,
        "category": args.category,
        "pubDate": args.date,
        "keyword": args.keyword,
        "author": args.author,
        "draft": args.draft,
    }
    content = build_frontmatter(meta) + "\n\n" + body + "\n"
    out_path.write_text(content, encoding="utf-8")

    committed = False
    commit_msg = None
    if args.commit:
        rel = out_path.relative_to(repo).as_posix()
        add = git(repo, "add", rel)
        if add.returncode != 0:
            fail(f"git add failed: {add.stderr.strip()}")
        commit_msg = f"content(blog): publish \"{args.title}\""
        cm = git(repo, "commit", "-m", commit_msg)
        if cm.returncode != 0:
            fail(f"git commit failed: {cm.stderr.strip() or cm.stdout.strip()}")
        committed = True

    print(json.dumps({
        "success": True,
        "slug": slug,
        "path": str(out_path),
        "url": f"/blog/{slug}",
        "draft": args.draft,
        "committed": committed,
        "commit_message": commit_msg,
    }))


if __name__ == "__main__":
    main()
