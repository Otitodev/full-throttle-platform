"""astro-git publishing adapter (greenfield path).

Writes a frontmatter'd Markdown file into <repo>/src/content/blog/<slug>.md so
the Astro `blog` collection renders it at /blog/<slug>; optionally git-commits.
Ports the logic of the retired seo-blog-publisher skill.
"""

from __future__ import annotations

from pathlib import Path

from adapters.base import PublishAdapter, Post
from _common import build_frontmatter, git


class AstroGitAdapter(PublishAdapter):
    name = "astro-git"

    def __init__(self, repo: str | None = None, commit: bool = False, overwrite: bool = False):
        if not repo:
            raise ValueError("astro-git adapter requires --repo")
        self.repo = Path(repo).expanduser().resolve()
        self.commit = commit
        self.overwrite = overwrite

    def publish(self, post: Post) -> dict:
        blog_dir = self.repo / "src" / "content" / "blog"
        if not blog_dir.is_dir():
            raise FileNotFoundError(f"blog collection dir not found: {blog_dir} (is --repo the Astro root?)")

        out_path = blog_dir / f"{post.slug}.md"
        if out_path.exists() and not self.overwrite:
            raise FileExistsError(f"post already exists: {out_path} (use --overwrite)")

        content = build_frontmatter(post) + "\n\n" + post.body_md.strip() + "\n"
        out_path.write_text(content, encoding="utf-8")

        rollback_ref = None
        committed = False
        if self.commit:
            rel = out_path.relative_to(self.repo).as_posix()
            add = git(self.repo, "add", rel)
            if add.returncode != 0:
                raise RuntimeError(f"git add failed: {add.stderr.strip()}")
            cm = git(self.repo, "commit", "-m", f'content(blog): publish "{post.title}"')
            if cm.returncode != 0:
                raise RuntimeError(f"git commit failed: {cm.stderr.strip() or cm.stdout.strip()}")
            committed = True
            rev = git(self.repo, "rev-parse", "HEAD")
            rollback_ref = rev.stdout.strip() if rev.returncode == 0 else None

        return {
            "adapter": self.name, "slug": post.slug, "path": str(out_path),
            "url": f"/blog/{post.slug}", "draft": post.draft,
            "committed": committed, "rollback_ref": rollback_ref,
        }
