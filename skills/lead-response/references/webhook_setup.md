# Lead webhook setup (gateway `webhook` adapter)

Leads arrive as an HTTP POST to the Hermes gateway's built-in `webhook` adapter
(`gateway/platforms/webhook.py`). No custom server — this is configuration in the client's
profile `config.yaml` + a secret in `.env`. The onboarding script (story O1) sets this per client.

## 1. Route config (profile `config.yaml`)

```yaml
platforms:
  webhook:
    extra:
      # host/port default to 0.0.0.0:8644
      routes:
        lead:
          secret_env: WEBHOOK_LEAD_SECRET      # HMAC secret (store value in .env)
          skills: ["lead-response"]
          prompt: |
            A new sales lead arrived. Handle it with the lead-response skill:
            name={name} phone={phone} email={email} source={source}
            message={message}
            Run intake.py with these fields, send the first-touch via send_message,
            then sync_lead.py and notify the owner.
          deliver: "log"     # the agent itself sends the customer reply via send_message
```

The adapter renders `prompt` from the POSTed JSON, loads `skills`, and runs an agent turn. It
returns **202 immediately** and runs the agent async, so the HTTP caller isn't blocked.

## 2. Secret (profile `.env`)

```
WEBHOOK_LEAD_SECRET=<random-hmac-secret>
```

## 3. Built-in guarantees (no code needed)

- **Auth**: HMAC-SHA256 over the body. Generic `X-Webhook-Signature`, or GitHub/GitLab/Svix
  headers. Missing/empty secret fails closed.
- **Idempotency**: a `delivery_id` (from headers or request id) is de-duplicated for 1h — replays
  don't re-run the agent. `intake.py` adds a second dedup layer on phone/email.
- **Rate limit**: per-route fixed window (default 30/min).

## 4. Sample lead payload

```json
{ "name": "Jane Doe", "phone": "+18505551234", "email": "jane@example.com",
  "source": "web-form", "message": "6ft vinyl privacy fence quote in Lynn Haven" }
```

Phone should be **E.164** (`+1…`) so the SMS first-touch delivers.

## 5. Test (running gateway)

```
BODY='{"name":"Jane Doe","phone":"+18505551234","email":"jane@example.com","source":"web-form","message":"vinyl privacy fence"}'
SIG=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_LEAD_SECRET" | sed 's/^.* //')
curl -X POST http://<host>:8644/webhooks/lead \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: sha256=$SIG" \
  -d "$BODY"
```

Expect HTTP 202, then a first-touch SMS to the customer within seconds. POST the same body again
→ no second reply (idempotent).

## Where leads come from

- **Web forms**: point the form's submit/webhook at `/webhooks/lead` (or have the site backend
  POST it). Many form tools (Formspree, Netlify Forms, WP plugins) support outbound webhooks.
- **Google Local Services Ads**: export/forward LSA leads (via Zapier/email-parser/partner feed)
  as a POST to the same route.
- **Inbound SMS / missed-call text-back**: a later add — uses the SMS adapter +
  `SMS_ALLOW_ALL_USERS`/allowlist, and needs the customer lead line separated from the owner's
  control number. Not part of the web-form-first MVP.
