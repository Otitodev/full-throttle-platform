#!/usr/bin/env python3
"""Select REAL, unused content for the next batch of social posts (guardrail step).

Surfaces candidates the agent can caption — before/after job photos (from an
assets manifest) and recyclable 4-5 star reviews (from the review skill's reviews
source). It NEVER fabricates content: every candidate points at a real asset or a
real review. Items already used/posted are skipped.

Output: JSON list of candidates {kind, source_ref, image_path|review, hint}.

Example:
    python pick_content.py --assets-file assets.json --reviews-file ../reviews.csv --count 3
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import fail, load_json, state_dir


def _load_assets(assets_file: Path) -> list[dict]:
    data = load_json(assets_file, [])
    if isinstance(data, dict):
        data = data.get("assets", [])
    return [a for a in data if isinstance(a, dict) and a.get("image_path")]


def _load_reviews(reviews_file: Path) -> list[dict]:
    if not reviews_file.is_file():
        return []
    text = reviews_file.read_text(encoding="utf-8")
    if reviews_file.suffix.lower() == ".json":
        data = json.loads(text)
        rows = data if isinstance(data, list) else data.get("reviews", [])
    else:
        rows = list(csv.DictReader(text.splitlines()))
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description="Pick real, unused content for social posts.")
    p.add_argument("--assets-file", help="JSON manifest of real job photos")
    p.add_argument("--reviews-file", help="reviews CSV/JSON (reuse the review skill's source)")
    p.add_argument("--count", type=int, default=3, help="max candidates to return")
    p.add_argument("--min-rating", type=int, default=4, help="min star rating for review posts")
    p.add_argument("--state-dir", help="override profile state dir")
    args = p.parse_args()

    if not args.assets_file and not args.reviews_file:
        fail("provide --assets-file and/or --reviews-file (real content only)")

    sdir = state_dir(args.state_dir)
    used = set(load_json(sdir / "used.json", []))   # source_refs already turned into posts

    candidates: list[dict] = []

    if args.assets_file:
        for a in _load_assets(Path(args.assets_file).expanduser()):
            ref = f"asset:{a.get('id')}"
            if a.get("used") or ref in used:
                continue
            candidates.append({
                "kind": "photo",
                "source_ref": ref,
                "image_path": a["image_path"],
                "hint": " ".join(x for x in [a.get("job_desc", ""), a.get("location", "")] if x).strip(),
            })

    if args.reviews_file:
        for r in _load_reviews(Path(args.reviews_file).expanduser()):
            rid = str(r.get("id") or r.get("review_id") or "").strip()
            ref = f"review:{rid}"
            try:
                rating = int(float(r.get("rating") or r.get("stars") or 0))
            except (TypeError, ValueError):
                rating = 0
            if not rid or rating < args.min_rating or ref in used:
                continue
            candidates.append({
                "kind": "review",
                "source_ref": ref,
                "review": str(r.get("text") or r.get("comment") or "").strip(),
                "author": str(r.get("author") or r.get("name") or "").strip(),
                "hint": "Recycle this real customer review into a quote post.",
            })

    print(json.dumps({
        "success": True,
        "count": len(candidates[: args.count]),
        "candidates": candidates[: args.count],
        "note": "Caption each candidate truthfully from the real asset/review. Do not invent projects or claims.",
    }, indent=2))


if __name__ == "__main__":
    main()
