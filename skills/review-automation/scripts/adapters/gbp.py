"""Google Business Profile review adapter.

Reads reviews and posts replies via the Google Business Profile (legacy "My
Business" v4) reviews endpoints. Auth follows the same pattern as the Hermes
`google-workspace` skill: an OAuth authorized-user token JSON, refreshed on use.

This adapter is the "real" source; it only works once GBP API access is granted
and OAuth is set up (see ../references/gbp_setup.md). Until then the skill runs
on the `manual` adapter — no code change needed to switch.

Dependencies (google extra) are imported lazily so the manual path never needs
them installed.
"""

from __future__ import annotations

import os
from pathlib import Path

from adapters.base import ReviewAdapter, Review, normalize_review

# v4 reviews live on this host (not in the newer discovery-based client).
_API_ROOT = "https://mybusiness.googleapis.com/v4"
_SCOPES = ["https://www.googleapis.com/auth/business.manage"]
_STAR_WORDS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


class GBPAdapter(ReviewAdapter):
    name = "gbp"

    def __init__(self, location: str | None = None, token_path: str | None = None):
        # location: "accounts/{accountId}/locations/{locationId}"
        self.location = location or os.environ.get("GBP_LOCATION", "")
        if not self.location:
            raise ValueError("gbp adapter requires --location or GBP_LOCATION env")
        self.token_path = Path(token_path).expanduser() if token_path else (
            _hermes_home() / "google_token.json"
        )

    def _session(self):
        # Lazy import: only needed for the gbp path.
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.auth.transport.requests import AuthorizedSession, Request  # type: ignore

        if not self.token_path.is_file():
            raise FileNotFoundError(
                f"OAuth token not found: {self.token_path} — run GBP setup (see references/gbp_setup.md)"
            )
        creds = Credentials.from_authorized_user_file(str(self.token_path), _SCOPES)
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
        return AuthorizedSession(creds)

    def list_reviews(self) -> list[Review]:
        sess = self._session()
        reviews: list[Review] = []
        page_token = None
        while True:
            url = f"{_API_ROOT}/{self.location}/reviews"
            params = {"pageSize": 50}
            if page_token:
                params["pageToken"] = page_token
            resp = sess.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("reviews", []):
                reviews.append(normalize_review({
                    "id": item.get("reviewId"),
                    "author": (item.get("reviewer") or {}).get("displayName", ""),
                    "rating": _STAR_WORDS.get(item.get("starRating", ""), 0),
                    "text": item.get("comment", ""),
                    "created": item.get("createTime", ""),
                }))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return [r for r in reviews if r.id]

    def post_reply(self, review_id: str, text: str) -> dict:
        sess = self._session()
        url = f"{_API_ROOT}/{self.location}/reviews/{review_id}/reply"
        resp = sess.put(url, json={"comment": text}, timeout=30)
        resp.raise_for_status()
        return {"adapter": self.name, "review_id": review_id, "posted": True}
