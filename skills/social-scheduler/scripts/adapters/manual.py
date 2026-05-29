"""Manual social adapter — writes posts to an outbox the operator/Buffer publishes.

The demo-ready default, before Google Business Profile / Meta API access is wired.
Each published post is appended to an outbox file (a content calendar) as JSONL;
the operator (or a Buffer import) posts them to the actual channels. Same interface
as the gbp_post adapter, so flipping later is a config change, not code.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from adapters.base import SocialAdapter, Post


class ManualAdapter(SocialAdapter):
    name = "manual"
    supports_media = True   # the outbox just records the image path; operator attaches it

    def __init__(self, outbox_dir: str | None = None):
        self.outbox_dir = Path(outbox_dir).expanduser() if outbox_dir else None

    def publish(self, post: Post) -> dict:
        # Default outbox location is resolved by the caller (state dir) if not given.
        if self.outbox_dir is None:
            raise ValueError("manual adapter requires an outbox dir (set by --outbox-dir or state dir)")
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.outbox_dir / "outbox.jsonl"
        record = {
            "published_at": datetime.now(timezone.utc).isoformat(),
            "targets": post.targets,
            "kind": post.kind,
            "caption": post.caption,
            "image_path": post.image_path,
            "source_ref": post.source_ref,
            "post_id": post.id,
        }
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return {"adapter": self.name, "post_id": post.id, "written_to": str(out_path)}
