"""manual publishing adapter.

Renders the post (frontmatter + markdown, and an HTML version) to a file in an
outbox dir for the operator to paste wherever needed. The fallback when no real
publishing target is wired yet.
"""

from __future__ import annotations

from pathlib import Path

from adapters.base import PublishAdapter, Post
from _common import build_frontmatter, md_to_html


class ManualAdapter(PublishAdapter):
    name = "manual"

    def __init__(self, outbox_dir: str):
        self.outbox_dir = Path(outbox_dir).expanduser()

    def publish(self, post: Post) -> dict:
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        md_path = self.outbox_dir / f"{post.slug}.md"
        html_path = self.outbox_dir / f"{post.slug}.html"
        md_path.write_text(build_frontmatter(post) + "\n\n" + post.body_md.strip() + "\n", encoding="utf-8")
        html_path.write_text(md_to_html(post.body_md), encoding="utf-8")
        return {"adapter": self.name, "slug": post.slug,
                "md_path": str(md_path), "html_path": str(html_path), "draft": post.draft}
