# WordPress (`wordpress-rest` adapter) setup

Publishes to a client's existing WordPress via the REST API — augment, no migration. Uses an
**Application Password** (WordPress 5.6+), which is the standard for programmatic access and is
revocable independently of the user's login password.

## 1. Create an Application Password

In the client's WordPress admin: **Users → Profile → Application Passwords** → add one named
"Full Throttle". Copy the generated password (shown once, looks like `abcd EFGH ijkl …`).

The WP user needs a role that can publish posts (Author/Editor/Admin).

## 2. Store credentials (profile)

```
# profile .env
WP_APP_PASSWORD=abcdEFGHijkl...      # spaces optional; the app password
```

`--wp-url` (site root, e.g. `https://client.com`) and `--wp-user` (the WP username) are passed on
the command line (or `WP_URL` / `WP_USER` env).

## 3. Publish

```
python scripts/publish.py --adapter wordpress-rest \
  --wp-url https://client.com --wp-user editor \
  --title "Aluminum Fencing 101" --category "Guide" --excerpt "Basics." \
  --body-file post.md            # add --dry-run first to preview the payload
```

- Endpoint: `POST {wp-url}/wp-json/wp/v2/posts`, HTTP Basic auth (`wp-user` : `WP_APP_PASSWORD`).
- Body markdown → minimal HTML (`content`). `status` = `publish` (or `draft` with `--draft`).
- **Idempotency:** the adapter first `GET ?slug=` — if a post with that slug exists it's skipped
  (or updated with `--overwrite`). The returned **WP post id is the rollback reference** (delete
  or unpublish to revert).

## 4. Categories (optional)

WordPress categories are referenced by numeric ID. List them via
`GET {wp-url}/wp-json/wp/v2/categories`, then pass `--categories 3,7`. Omit to use the site default.

## Troubleshooting

- **401** — bad Application Password or user; regenerate.
- **403 / REST disabled** — a security plugin may block `/wp-json`; allowlist it or use an app
  password header. If the REST API is hard-blocked, fall back to `proxy-subdir` or `manual`.
- Verify the HTML first with `--dry-run` (no network).
