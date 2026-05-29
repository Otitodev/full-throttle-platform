"""Google Business Profile post adapter (localPosts).

Publishes a post to the client's Business Profile via the legacy "My Business" v4
`localPosts.create` endpoint. Reuses the SAME OAuth token + `business.manage`
scope as the review-automation skill's gbp adapter (see
../../review-automation/references/gbp_setup.md) — no second OAuth.

Only works once GBP API access is granted; until then the skill runs on the
`manual` adapter. Google deps are imported lazily so the manual path never needs
them. Note: GBP localPost media requires a PUBLIC image URL (sourceUrl), so a
local-file image is posted as text-only here with a note — host the image first
(or use the manual outbox) to include the photo.
"""

from __future__ import annotations

import os
from pathlib import Path

from adapters.base import SocialAdapter, Post

_API_ROOT = "https://mybusiness.googleapis.com/v4"
_SCOPES = ["https://www.googleapis.com/auth/business.manage"]


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))


class GBPPostAdapter(SocialAdapter):
    name = "gbp"
    supports_media = True   # only when image_path is a public URL

    def __init__(self, location: str | None = None, token_path: str | None = None):
        self.location = location or os.environ.get("GBP_LOCATION", "")
        if not self.location:
            raise ValueError("gbp adapter requires --location or GBP_LOCATION env")
        self.token_path = Path(token_path).expanduser() if token_path else (
            _hermes_home() / "google_token.json"
        )

    def _session(self):
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.auth.transport.requests import AuthorizedSession, Request  # type: ignore

        if not self.token_path.is_file():
            raise FileNotFoundError(
                f"OAuth token not found: {self.token_path} — see review-automation/references/gbp_setup.md"
            )
        creds = Credentials.from_authorized_user_file(str(self.token_path), _SCOPES)
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
        return AuthorizedSession(creds)

    def publish(self, post: Post) -> dict:
        sess = self._session()
        body = {"languageCode": "en-US", "summary": post.caption, "topicType": "STANDARD"}
        # localPost media needs a public sourceUrl; only attach if image_path looks like a URL.
        if post.image_path.startswith(("http://", "https://")):
            body["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": post.image_path}]
        url = f"{_API_ROOT}/{self.location}/localPosts"
        resp = sess.post(url, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return {"adapter": self.name, "post_id": post.id, "gbp_name": data.get("name", ""), "posted": True}
