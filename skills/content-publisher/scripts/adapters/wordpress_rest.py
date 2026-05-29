"""wordpress-rest publishing adapter.

Publishes a post to a client's existing WordPress via the REST API
(POST /wp-json/wp/v2/posts) using an Application Password (HTTP Basic auth).
Markdown body is converted to minimal HTML. Idempotent on slug (skips if a post
with that slug already exists, unless overwrite). `requests` is imported lazily,
so the non-WordPress adapters need no extra deps. See ../references/wordpress_setup.md.
"""

from __future__ import annotations

import os

from adapters.base import PublishAdapter, Post
from _common import md_to_html


class WordPressRestAdapter(PublishAdapter):
    name = "wordpress-rest"

    def __init__(self, wp_url: str | None = None, wp_user: str | None = None,
                 categories: str | None = None, overwrite: bool = False, dry_run: bool = False):
        self.wp_url = (wp_url or os.environ.get("WP_URL", "")).rstrip("/")
        self.wp_user = wp_user or os.environ.get("WP_USER", "")
        self.app_password = os.environ.get("WP_APP_PASSWORD", "")
        self.categories = [int(c) for c in categories.split(",")] if categories else []
        self.overwrite = overwrite
        self.dry_run = dry_run
        if not self.wp_url:
            raise ValueError("wordpress-rest requires --wp-url or WP_URL")

    def _endpoint(self) -> str:
        return f"{self.wp_url}/wp-json/wp/v2/posts"

    def publish(self, post: Post) -> dict:
        body = {
            "title": post.title,
            "slug": post.slug,
            "excerpt": post.excerpt,
            "content": md_to_html(post.body_md),
            "status": "draft" if post.draft else "publish",
        }
        if self.categories:
            body["categories"] = self.categories

        if self.dry_run:
            return {"adapter": self.name, "dry_run": True, "endpoint": self._endpoint(),
                    "slug": post.slug, "payload": body}

        if not (self.wp_user and self.app_password):
            raise ValueError("wordpress-rest requires --wp-user and WP_APP_PASSWORD for a live publish")

        import requests  # lazy
        auth = (self.wp_user, self.app_password)

        # Idempotency: skip if a post with this slug already exists (unless overwrite).
        existing = requests.get(self._endpoint(), params={"slug": post.slug, "status": "any"},
                                auth=auth, timeout=30)
        existing.raise_for_status()
        found = existing.json()
        if found and not self.overwrite:
            pid = found[0].get("id")
            return {"adapter": self.name, "slug": post.slug, "skipped": "exists",
                    "post_id": pid, "url": found[0].get("link", ""), "rollback_ref": pid}

        if found and self.overwrite:
            pid = found[0]["id"]
            resp = requests.post(f"{self._endpoint()}/{pid}", json=body, auth=auth, timeout=30)
        else:
            resp = requests.post(self._endpoint(), json=body, auth=auth, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return {
            "adapter": self.name, "slug": post.slug, "post_id": data.get("id"),
            "url": data.get("link", ""), "status": data.get("status"),
            "rollback_ref": data.get("id"),
        }
