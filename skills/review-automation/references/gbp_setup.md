# Google Business Profile (GBP) adapter setup

The `gbp` adapter reads reviews and posts replies through the Google Business Profile
(legacy "My Business" v4) API. This is **access-gated** by Google — until it's approved and
OAuth is set up, run the skill on the `manual` adapter. Setup mirrors the Hermes
`google-workspace` skill (`skills/productivity/google-workspace/scripts/setup.py`).

## 1. Google Cloud project + API access

1. Create (or reuse) a Google Cloud project.
2. Enable the Business Profile APIs: **My Business Account Management API**, **My Business
   Business Information API**, and request access to the **Business Profile API** group
   (reviews live in the v4 `mybusiness.googleapis.com` endpoints).
3. **Request API quota/access** via Google's Business Profile API access form. Approval can
   take days to weeks — this is the gate the `manual` adapter exists to work around.

## 2. OAuth credentials

1. Create an **OAuth 2.0 Client ID** (Desktop app) in the project.
2. Download the client secret JSON to the client profile, e.g.
   `<HERMES_HOME>/google_client_secret.json`.
3. Scope required: `https://www.googleapis.com/auth/business.manage`.

## 3. Authorize (produce the token)

Reuse the google-workspace OAuth flow (it writes an authorized-user token JSON). Point it at
the business.manage scope and save the token to `<HERMES_HOME>/google_token.json` — the path
the `gbp` adapter reads by default (override with `--token-path`).

## 4. Find the location id

The adapter needs `accounts/{accountId}/locations/{locationId}`. List accounts/locations via
the Account Management + Business Information APIs, then set it as `GBP_LOCATION` in the
profile `.env` (or pass `--location`).

## 5. Flip the adapter

Once the token + location are in place, switch the skill's commands from
`--adapter manual --reviews-file …` to `--adapter gbp --location accounts/…/locations/…`.
No skill code changes — same `fetch_reviews.py` / `post_response.py` interface.

## Verify

```
python scripts/fetch_reviews.py --adapter gbp --location accounts/<a>/locations/<l> --peek
```

Should return current reviews as JSON. If you get a token/credentials error, re-run the
OAuth authorization; if you get a 403, the API access request hasn't been granted yet —
stay on `manual`.
