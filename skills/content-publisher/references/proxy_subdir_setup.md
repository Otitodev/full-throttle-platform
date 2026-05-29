# proxy-subdir setup (Cloudflare Worker reverse proxy)

Serves content WE host at the client's own `client.com/blog` path, without touching their CMS.
This is the augment wedge for locked/legacy CMSes (e.g. ColdFusion): SEO equity stays on the
client's domain (subdirectory beats subdomain) with **no migration risk**.

## Architecture

```
visitor → client.com/blog/<slug>
           │  (Cloudflare in front of client.com)
           ▼
        Worker route: client.com/blog*  →  fetch from OUR origin (the hosted Astro blog)
           │
           ▼
        our-origin (Vercel/Pages) serving the per-client Astro blog at /blog/*
```

The `proxy-subdir` adapter publishes exactly like `astro-git` but into **our** per-client blog
repo, and reports the public URL as `<public-base>/blog/<slug>` (the client's domain).

## 1. Host the per-client Astro blog (our infra)

Create a per-client Astro repo (same `blog` content collection as the greenfield template),
deploy to our Vercel/Cloudflare Pages project. Note its origin URL (e.g.
`https://mrfence-blog.vercel.app`). The adapter's `--repo` points at this repo.

## 2. Cloudflare Worker (requires the client's DNS on Cloudflare)

`wrangler.toml`:
```toml
name = "client-blog-proxy"
main = "src/worker.js"
compatibility_date = "2026-01-01"
routes = [{ pattern = "client.com/blog*", zone_name = "client.com" }]
```

`src/worker.js`:
```js
const ORIGIN = "https://mrfence-blog.vercel.app"; // our hosted blog origin
export default {
  async fetch(request) {
    const url = new URL(request.url);
    // client.com/blog/<x>  →  ORIGIN/blog/<x>
    const target = ORIGIN + url.pathname + url.search;
    const resp = await fetch(target, request);
    // pass through; optionally rewrite any absolute origin links to client.com
    return new Response(resp.body, resp);
  },
};
```

Deploy with `wrangler deploy`. (Full deploy needs a Cloudflare account + the client's zone on
Cloudflare — that's an onboarding step, not part of the skill code.)

## 3. Publish

```
python scripts/publish.py --adapter proxy-subdir \
  --repo /path/to/our/client-blog --public-base https://client.com --commit \
  --title "…" --category "Guide" --excerpt "…" --body-file post.md
```

Output `url` = `https://client.com/blog/<slug>`; the `.md` is committed to our hosted repo (commit
SHA is the rollback reference); the Worker serves it under the client's domain on the next deploy.

## Notes

- Keep the Worker thin (pure pass-through) to start; add link rewriting only if absolute origin
  URLs leak into the HTML.
- Canonical tags on the blog posts should point at `client.com/blog/<slug>` so Google attributes
  the content to the client's domain.
