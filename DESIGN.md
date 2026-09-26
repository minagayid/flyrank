# Design — Usage Metering & Billing Engine

## Problem and scope

Record billable work once, enforce a tenant's monthly Free or Pro allowance before work is accepted, and return a transparent monthly usage and cost summary. The service also models subscription updates from verified Stripe-shaped events. It is a local portfolio demo, not a production payment system.

## Data model

- `tenants`: tenant identity and a demo API-key hash.
- `plans`: pinned quota, subscription-price, and token-cost configuration.
- `subscriptions`: one current plan/status row per tenant; only a verified webhook changes it.
- `usage_events`: append-only records with separate API-call/token quantities, monthly period, token breakdown, and integer micro-cent costs. One `/generate` action is one row.
- `idempotency_records`: `(tenant_id, key)` unique replay record with request hash and original response.
- `stripe_events`: provider event IDs already handled.
- `checkout_sessions`: local or Stripe test Checkout session references.
- `invoice_summaries`: durable monthly snapshots.
- `jobs` / `ops_alerts`: durable invoice-summary work, retry state, and exhausted-retry alerts.

## API surface

`POST /generate` atomically meters one API call plus simulated token usage. `POST /usage/events` supports explicit meter quantities for boundary demonstrations. `GET /usage` and `GET /invoices/preview` are tenant-scoped read paths. Checkout/webhooks sync plan state; invoice jobs produce persistent snapshots off the request path.

## Layer sketch

```text
FastAPI routes and request schemas
        ↓
metering / pricing / quota / subscription services
        ↓
SQLite repository (versioned SQL migration, transactions, indexes)
        ↑
durable invoice-summary worker (retry + operations alert)
```

## Explicit non-goals

No real charges, live-mode Stripe, overage billing, proration, production authentication, model calls, or public deployment. Mock payment is the default; optional Stripe mode refuses any API key that is not `sk_test_`.
