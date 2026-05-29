"""proxy-subdir publishing adapter.

Publishes to an Astro blog WE host per client (same content mechanics as
astro-git), then reports the PUBLIC url on the client's own domain — because a
Cloudflare Worker reverse-proxies client.com/blog/* to our origin (see
../references/proxy_subdir_setup.md). This is the augment wedge for clients on
locked/legacy CMSes: SEO equity stays on their domain, no migration.
"""

from __future__ import annotations

from adapters.base import Post
from adapters.astro_git import AstroGitAdapter


class ProxySubdirAdapter(AstroGitAdapter):
    name = "proxy-subdir"

    def __init__(self, repo: str | None = None, commit: bool = False, overwrite: bool = False,
                 public_base: str | None = None):
        super().__init__(repo=repo, commit=commit, overwrite=overwrite)
        if not public_base:
            raise ValueError("proxy-subdir adapter requires --public-base (e.g. https://client.com)")
        self.public_base = public_base.rstrip("/")

    def publish(self, post: Post) -> dict:
        result = super().publish(post)
        result["adapter"] = self.name
        # Override the url to the client's domain (served via the Worker).
        result["url"] = f"{self.public_base}/blog/{post.slug}"
        return result
