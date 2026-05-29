"""Social publishing adapters — common interface.

A SocialAdapter abstracts *where a post goes* so the skill doesn't care whether
a post lands in a manual content-calendar/outbox (the demo path), Google Business
Profile, or (later) Facebook/Buffer. Mirrors the review-automation adapter pattern.

Each adapter implements:
- publish(post) -> dict   (publish/queue one approved, due Post)
- supports_media          (whether it can attach an image)

The skill enforces the real-content guardrail BEFORE this layer — adapters just
deliver whatever Post they're given.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Post:
    id: str
    kind: str                       # "photo" | "review"
    caption: str
    image_path: str = ""            # local path to a REAL job photo (optional for review posts)
    source_ref: str = ""            # asset id or review id this post was built from
    targets: list = field(default_factory=list)   # e.g. ["gbp", "facebook"]
    scheduled_at: str = ""          # ISO timestamp
    status: str = "pending"         # pending | approved | posted

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Post":
        return Post(
            id=str(d.get("id", "")),
            kind=str(d.get("kind", "photo")),
            caption=str(d.get("caption", "")),
            image_path=str(d.get("image_path", "")),
            source_ref=str(d.get("source_ref", "")),
            targets=list(d.get("targets", [])),
            scheduled_at=str(d.get("scheduled_at", "")),
            status=str(d.get("status", "pending")),
        )


class SocialAdapter:
    name = "base"
    supports_media = False

    def publish(self, post: Post) -> dict:
        raise NotImplementedError
