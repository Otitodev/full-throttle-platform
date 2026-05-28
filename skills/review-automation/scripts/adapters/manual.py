"""Manual review adapter — reviews from a CSV/JSON file, replies to a file.

The fallback adapter for clients before the Google Business Profile API is wired
(GBP access is gated). The operator exports reviews to a CSV or JSON file; the
agent's approved replies are appended to a responses file the operator pastes
back into Google. Same interface as the gbp adapter, so flipping later is a
config change, not a code change.

CSV columns (header row): id,author,rating,text,created
JSON: a list of objects with the same keys (any of the aliases in
adapters.base.normalize_review are accepted).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from adapters.base import ReviewAdapter, Review, normalize_review, today_iso


class ManualAdapter(ReviewAdapter):
    name = "manual"

    def __init__(self, reviews_file: str, responses_dir: str | None = None):
        if not reviews_file:
            raise ValueError("manual adapter requires --reviews-file")
        self.reviews_file = Path(reviews_file).expanduser()
        self.responses_dir = Path(responses_dir).expanduser() if responses_dir else None

    def list_reviews(self) -> list[Review]:
        if not self.reviews_file.is_file():
            raise FileNotFoundError(f"reviews file not found: {self.reviews_file}")
        text = self.reviews_file.read_text(encoding="utf-8")
        suffix = self.reviews_file.suffix.lower()
        rows: list[dict]
        if suffix == ".json":
            data = json.loads(text)
            rows = data if isinstance(data, list) else data.get("reviews", [])
        else:  # treat everything else as CSV
            rows = list(csv.DictReader(text.splitlines()))
        reviews = [normalize_review(r) for r in rows]
        return [r for r in reviews if r.id]  # drop rows with no id

    def post_reply(self, review_id: str, text: str) -> dict:
        # "Posting" for the manual adapter = appending to a responses file the
        # operator pastes into Google. Default location next to the reviews file.
        out_dir = self.responses_dir or self.reviews_file.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "review_responses.jsonl"
        record = {"review_id": review_id, "reply": text, "posted_at": today_iso()}
        with out_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return {"adapter": self.name, "review_id": review_id, "written_to": str(out_path)}
