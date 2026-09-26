# Design: Social Media Studio

## Problem and data flow

Teams need to turn one source post into platform-specific copy, review every version, and schedule approved content without duplicate publishes.

```text
Markdown or URL -> stored post -> variants -> constraints -> human review
                                               -> SQLite schedule -> publisher adapter -> publish history
```

## Data model

- `posts`: source text, optional source URL, creation time.
- `variants`: post, platform, body, status (`draft`, `approved`, `rejected`, `published`), validation result.
- `schedules`: variant, UTC slot, adapter, status, unique idempotency key.
- `publish_attempts`: schedule, start/end, outcome, message reference, safe error summary.

## API surface

- `POST /posts`: store Markdown or fetch a public HTTP(S) URL.
- `POST /posts/{id}/generate`: create one validated variant per configured platform.
- `PATCH /variants/{id}`: edit copy, approve, or reject it.
- `POST /variants/{id}/schedule`: queue an approved variant at a UTC time.
- `POST /schedules/{id}/publish`: run a due schedule now (also used for local probes).
- `GET /history`: inspect every attempt and its adapter result.
- `GET /health`: process and storage status.

## Publisher seam

`SocialPublisher.publish(body, idempotency_key)` is implemented by a Discord webhook adapter and two database-backed mocks (`mock_x`, `mock_linkedin`). The active adapter is configuration; route and workflow code do not branch on the platform.

## Non-goals

No image generation, engagement analytics, multi-tenant accounts, or publishing to Instagram, X, or LinkedIn. The Discord adapter is opt-in and no live message is sent by default.

## Delivery semantics

The database enforces one schedule key per variant+slot and one successful mock record per key. External Discord webhooks do not offer an idempotency key, so a timeout after a send is ambiguous. The worker records such a result as `uncertain` and will not retry it automatically; this avoids silently duplicating a public message and requires reconciliation by the owner.
