#!/usr/bin/env python3
"""Publish a blog post via the chosen adapter (astro-git | wordpress-rest | proxy-subdir | manual).

The SEO/Content agent writes a truthful, E-E-A-T-respecting post body, then runs this once with
the client's configured adapter. Output is a single JSON object (slug, url, rollback_ref, …).

Examples:
    # Greenfield Astro
    python publish.py --adapter astro-git --repo /path/site --commit \
        --title "Vinyl Fence Cost in Panama City" --category "Cost Guide" \
        --excerpt "Real per-foot pricing." --body-file post.md

    # Existing WordPress (preview)
    python publish.py --adapter wordpress-rest --wp-url https://client.com --wp-user editor \
        --title "…" --category "Guide" --excerpt "…" --body-file post.md --dry-run

    # Proxied blog on the client's domain
    python publish.py --adapter proxy-subdir --repo /our/client-blog --public-base https://client.com \
        --commit --title "…" --category "Guide" --excerpt "…" --body-file post.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import add_adapter_args, audit, build_adapter, fail, slugify, state_dir
from adapters.base import Post, today_iso


def main() -> None:
    p = argparse.ArgumentParser(description="Publish a blog post via a publishing adapter.")
    p.add_argument("--title", required=True)
    p.add_argument("--category", required=True)
    p.add_argument("--excerpt", required=True)
    p.add_argument("--keyword", default="")
    p.add_argument("--author", default="our team")
    p.add_argument("--date", default=today_iso(), help="pubDate YYYY-MM-DD")
    p.add_argument("--slug", default="", help="override the auto-generated slug")
    p.add_argument("--body", default="", help="markdown body (inline)")
    p.add_argument("--body-file", default="", help="markdown body from a file")
    p.add_argument("--draft", action="store_true")
    add_adapter_args(p)
    args = p.parse_args()

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

    post = Post(
        title=args.title, excerpt=args.excerpt, category=args.category, body_md=body,
        slug=slug, keyword=args.keyword, author=args.author, pub_date=args.date, draft=args.draft,
    )

    # touch state dir so the profile namespace exists (parity with other skills)
    state_dir(args.state_dir)

    try:
        adapter = build_adapter(args)
        result = adapter.publish(post)
        audit("content-publisher", action="publish", target=str(result.get("url", "")),
              status="ok", rollback_ref=result.get("rollback_ref"),
              repo=getattr(args, "repo", None))
        print(json.dumps({"success": True, **result}, indent=2))
    except Exception as exc:
        fail(f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
