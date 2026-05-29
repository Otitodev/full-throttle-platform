"""Publishing adapters — common interface.

A PublishAdapter abstracts *where a blog post lands* so the SEO/Content agent
doesn't care whether it goes to a greenfield Astro repo, the client's WordPress,
a proxied blog we host, or a manual outbox. Mirrors the review/social/lead
adapter pattern.

Each adapter implements:
- publish(post) -> dict   (publish one Post; idempotent on slug; returns url + rollback_ref)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date


@dataclass
class Post:
    title: str
    excerpt: str
    category: str
    body_md: str
    slug: str = ""
    keyword: str = ""
    author: str = "our team"
    pub_date: str = ""          # YYYY-MM-DD
    draft: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class PublishAdapter:
    name = "base"

    def publish(self, post: Post) -> dict:
        raise NotImplementedError


def today_iso() -> str:
    return date.today().isoformat()
