"""Review provider adapters — common interface.

A ReviewAdapter abstracts *where reviews live* so the skill scripts don't care
whether reviews come from Google Business Profile, a CSV the operator exported,
or (later) Podium/Birdeye. Mirrors the publishing-adapter pattern.

Each adapter implements:
- list_reviews()      -> list[Review]   (all reviews the source currently exposes)
- post_reply(id,text) -> dict           (post/record an owner reply to one review)

De-dup of "new since last run" is handled by the caller (fetch_reviews.py via
seen.json), NOT the adapter — so every adapter stays a thin source/sink.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date


@dataclass
class Review:
    id: str
    author: str
    rating: int          # 1-5
    text: str
    created: str         # ISO date string (YYYY-MM-DD) when known, else ""

    def to_dict(self) -> dict:
        return asdict(self)


class ReviewAdapter:
    """Abstract base. Subclasses must implement list_reviews + post_reply."""

    name = "base"

    def list_reviews(self) -> list[Review]:
        raise NotImplementedError

    def post_reply(self, review_id: str, text: str) -> dict:
        raise NotImplementedError


def _coerce_rating(value) -> int:
    try:
        r = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(5, r))


def normalize_review(raw: dict) -> Review:
    """Build a Review from a loosely-typed dict (CSV row / JSON object / API item)."""
    return Review(
        id=str(raw.get("id") or raw.get("review_id") or raw.get("reviewId") or "").strip(),
        author=str(raw.get("author") or raw.get("name") or raw.get("reviewer") or "").strip(),
        rating=_coerce_rating(raw.get("rating") or raw.get("starRating") or raw.get("stars")),
        text=str(raw.get("text") or raw.get("comment") or raw.get("body") or "").strip(),
        created=str(raw.get("created") or raw.get("date") or raw.get("createTime") or "").strip(),
    )


def today_iso() -> str:
    return date.today().isoformat()
