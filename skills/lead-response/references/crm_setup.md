# CRM adapter setup

Lead sync runs on the `manual` adapter by default (no setup — leads append to
`<HERMES_HOME>/lead-response/leads_crm.jsonl` for the operator to import). These notes cover the
real CRM adapters. The platform **augments** the CRM; the CRM stays the source of truth for
customers/jobs/scheduling.

## Manual (default)

Nothing to configure. `sync_lead.py --adapter manual` appends one JSON lead per line to
`leads_crm.jsonl`. The operator imports these into whatever system the client uses. This is the
demo path and the fallback whenever a CRM API isn't wired.

## Jobber (`jobber` adapter)

Jobber exposes a GraphQL API with OAuth2. The adapter creates a **client** record for each lead.

1. Create a Jobber Developer app; note the client id/secret and set the redirect URI.
2. Run the OAuth2 authorization-code flow to obtain an access token (and refresh token).
3. Store it where the adapter reads it — either:
   - `JOBBER_ACCESS_TOKEN` in the profile `.env`, or
   - `<HERMES_HOME>/jobber_token.json` as `{"access_token": "…"}` (override with `--token-path`).
4. Switch the sync command to `--adapter jobber`.

```
python scripts/sync_lead.py --adapter jobber --name "Jane Doe" --phone "+18505551234" --email jane@example.com --source web-form
```

Note: the adapter sends the GraphQL `clientCreate` mutation with
`X-JOBBER-GRAPHQL-VERSION`. Bump the version constant in `adapters/jobber.py` if Jobber requires
a newer date. To also create a *request/job*, extend the adapter with the corresponding mutation.

## ServiceTitan / Housecall Pro (later adapters)

Same pattern — add `adapters/servicetitan.py` / `adapters/housecallpro.py` implementing
`CRMAdapter.sync_lead`, register them in `_common.build_adapter`, and document their OAuth here.
ServiceTitan targets larger/enterprise contractors; Housecall Pro targets small teams. Deferred
until a client needs them.

## Idempotency

Every adapter dedups on `lead.id` (the source-provided id, else a phone|email fingerprint), so a
replayed lead never creates a duplicate CRM record.
