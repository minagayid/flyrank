# Design: Embeddable Widget & Lead-Capture Platform

## Problem and non-goal

Owners need a small authenticated API to define a form and copy one script tag. Untrusted visitors submit from unrelated origins; the platform validates, limits, enriches, stores, and reports each submission. The proof runs locally for $0. **Non-goal:** a production-hosted SaaS, visual form builder, payment flow, or real email delivery.

## Request paths

```text
Owner --Bearer token--> HTTP API --tenant-scoped queries--> SQLite
                           |  CRUD / embed / dashboard
Customer page --script--> versioned JS --GET config (60s cache)--> widget config
Visitor --CORS POST--> per-IP admission gate -> envelope + schema validation -> per-widget limiter -> honeypot
                       -> provider A -> provider B -> SQLite + notification outbox
                                                                -> retry worker
```

The API and customer test page use different local ports (8000 and 4173). Public CORS is wildcard because this is an embeddable anonymous form; no credentials or cookies are sent. Owner routes do not emit permissive CORS and use opaque local bearer tokens whose SHA-256 digests are stored in SQLite. Every owner query includes `tenant_id`; a cross-tenant widget lookup returns the same 404 as an unknown ID.

## Data model and indexes

- `tenants` owns widgets, owner token digests, submissions, and outbox jobs.
- `widgets` stores strict JSON field/display schemas, enabled state, and a config version. Delete is a soft delete; submission history remains available.
- `submissions` stores normalized field values, the source origin, a salted IP digest (never the raw IP), optional geo result/provider, and an idempotency key plus request fingerprint. Unique `(tenant_id, widget_id, idempotency_key)` prevents duplicate writes.
- `notification_jobs` is a transactional outbox. One unique dedupe key exists per stored submission; the background worker retries and eventually records a dead job plus an alert log.
- Indexes cover owner widget lists, tenant/date dashboards, widget/date submission lists, country aggregation, and ready outbox jobs.

SQLite migrations and WAL are enough for the local proof and avoid a paid database. A horizontally scaled deployment would move the token bucket to a shared store and use Postgres; this implementation deliberately keeps the service single-process.

## Contracts and safety

`POST /api/public/submissions` accepts only JSON fields defined by the stored widget, a bounded honeypot string, and an `Idempotency-Key`. JSON bodies are capped at 16 KiB by default. Type, required, email/phone, unknown-key, and per-field length checks happen before enrichment or storage. Invalid data returns structured 4xx JSON. Rate limiting uses atomic process-local token buckets keyed by both source IP and widget; raw IP is used only for that transient decision and geo lookup. The `Origin` header is recorded as metadata, never treated as authentication.

Geo providers are behind one interface. Local mock mode is deterministic: A returns Ashburn/US; when A is toggled down, B returns Toronto/CA; with both down, the valid lead stores without geo. Live geo is intentionally disabled: the first free provider in the brief is called over plain HTTP, so sending visitor IPs to it is not safe. A future live adapter must use HTTPS. A local-only, owner-authenticated developer control toggles mocks and a failing notification. The outbox worker handles that secondary action after commit, retries with backoff, and logs an alert after the retry budget; it cannot roll back the lead.

## Cache and extension points

The widget bundle URL includes a release version and is served `max-age=31536000, immutable`; bump `WIDGET_BUNDLE_VERSION` whenever the script changes. Config is ETagged and cached for 60 seconds. In production, put only the versioned bundle behind a CDN, add a shared limiter and real owner identity provider, and replace the console notification with an idempotent email/webhook adapter. Those are explicit scale/security follow-ups, not hidden claims about this local demo.
