# Usage Metering & Billing Engine

A local-first backend capstone that records usage durably, enforces monthly tenant quotas, prevents duplicate metering under retries, calculates integer-only cost estimates, and produces invoice summaries. Stripe Checkout is optional and test-mode-only; the default checkout and signed webhook flow is an offline mock, so no Stripe account, API key, card, or payment is needed.

> **Status:** local acceptance probes pass. No real Stripe Checkout, Stripe CLI delivery, or payment has been performed. The repository was created after local implementation, rather than public from day one.

## Architecture

```text
Client --X-Tenant-ID + X-Tenant-Key--> FastAPI
  POST /generate ---------------------> MeteringService
  POST /usage/events ---------------->   ├─ idempotency lookup
  GET /usage ------------------------>   ├─ quota check + atomic event insert
  GET /invoices/preview ------------->   └─ integer pricing rollup
                                           ↓
                              SQLite + versioned migration

Checkout -> Mock or Stripe test adapter -> signed /webhooks/stripe
                                                   ↓ verify + deduplicate
                                             subscription mirror

POST /invoice-jobs -> durable queue -> invoice worker -> stored summary
                                      └─ retries -> ops alert on exhaustion
```

Routes and domain services are separate from SQLite persistence. Every tenant-facing query is scoped to the authenticated demo tenant. One `/generate` action persists exactly one event row containing both its API-call and token quantities. A stable idempotency key is scoped to that tenant; a repeated key and identical request returns the original status and response, while the same key with a different request returns `409`.

## Plans and pinned rates

| Plan | API calls/month | AI tokens/month | Subscription amount |
|---|---:|---:|---:|
| Free | 1,000 | 100,000 | $0.00 |
| Pro | 50,000 | 5,000,000 | $29.99 |

Usage is checked before the dummy action is accepted. Equality with a quota is allowed; the next unit is rejected with `429` and `Retry-After`. An inactive/past-due subscription returns `402`. These are demo plan values, not commercial recommendations.

Cost rates are deliberately pinned example assumptions: one API call = 1 cent; each fresh input token = 15 micro-cents; cached input = 5 micro-cents; output and reasoning = 60 micro-cents each. One cent is 1,000,000 micro-cents. Cached input is a separate category, and reasoning is priced at the output rate; the request schema requires disjoint categories so they are not double-counted. Token cost is rounded half-up to cents after the monthly total is aggregated. Usage estimates are informational; included usage is not charged again. An invoice summary's amount due is the plan fee only, with metered cost estimates shown separately. No overages are billed.

## Run locally

Prerequisites: Python 3.11+ and [uv](https://docs.astral.sh/uv/). SQLite is included with Python; Docker and Postgres are not required.

```powershell
uv sync
Copy-Item .env.example .env
uv run python -m app.seed
uv run python -m app
```

The last command starts the API at `http://127.0.0.1:8000`. Open `/docs` for Swagger UI and `/openapi.json` for the generated OpenAPI schema. The database is created at `data/usage_metering.sqlite3`; the first startup applies `app/migrations/001_initial.sql`.

Seed creates two fictional demo tenants without printing their keys:

| Tenant header | Local demo key |
|---|---|
| `X-Tenant-ID: demo-free` | `local-free-demo-key` |
| `X-Tenant-ID: demo-pro` | `local-pro-demo-key` |

These public sample keys are only for local learning. Never use them as production credentials. The database stores only a SHA-256 digest of each key. `.env` is ignored by Git; `.env.example` contains safe placeholders.

Example (PowerShell):

```powershell
$headers = @{
  "X-Tenant-ID" = "demo-free"
  "X-Tenant-Key" = "local-free-demo-key"
  "Idempotency-Key" = "demo-generate-001"
}
$body = '{"tokens":{"input_tokens":1200,"cached_input_tokens":200,"output_tokens":300,"reasoning_tokens":100}}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/generate -Headers $headers -ContentType application/json -Body $body
```

## Stripe behavior

`PAYMENT_MODE=mock` uses a local Checkout-session record and an HMAC-signed Stripe-shaped event. The mock exercises signature verification, event deduplication, and plan synchronization but **does not prove a Stripe account, hosted Checkout, or real Stripe CLI delivery**. The mock secret defaults to a local-only placeholder and must not be used outside local learning.

An optional `PAYMENT_MODE=stripe_test` path uses the Stripe Python SDK and requires `STRIPE_SECRET_KEY=sk_test_…` plus the endpoint-specific `STRIPE_WEBHOOK_SECRET=whsec_…` from Stripe CLI. The app rejects keys without the `sk_test_` prefix. No credentials are required for the mock path, and this optional path has not been exercised here. Never configure a live key. Stripe expects webhook verification to use the unmodified request body and endpoint secret; see the [official signature guidance](https://docs.stripe.com/webhooks/signature) and [Checkout Session API](https://docs.stripe.com/api/checkout/sessions/create).

## API map

- `GET /health`, `GET /plans`
- `POST /generate` — one API call plus simulated token usage, atomically checked and recorded
- `POST /usage/events` — explicit API-call or token-usage meter event for quota demonstrations
- `GET /usage?period=YYYY-MM` — usage, quota, and cost rollup
- `GET /invoices/preview?period=YYYY-MM` — no-charge monthly summary
- `POST /invoice-jobs?period=YYYY-MM`, `GET /invoice-jobs/{job_id}` — durable async invoice snapshot job
- `POST /billing/checkout` — start Pro Checkout in mock or test mode
- `GET /billing/success`, `GET /billing/cancel` — local return pages that do not change plan state
- `POST /mock-checkout/{session_id}/complete` — complete the local mock only
- `POST /webhooks/stripe` — signature verification, event dedupe, subscription sync

## Limitations

This is a single-process educational service. SQLite is durable local persistence, but the in-process worker is not horizontally scalable. Demo API keys are public sample credentials. The mock signature is not a substitute for Stripe's SDK verification; only `stripe_test` uses the SDK's verifier. The Stripe test-mode path requires user-provided test credentials and a locally configured webhook secret and has not been run. Cost rates are synthetic pinned examples, invoice summaries are estimates, and no real invoice is issued or payment collected. The project was implemented locally before its separate public repository existed; it does not meet the brief's public-from-day-one sequence.

## Design and evidence

- [Design decision and data flow](DESIGN.md)
- [Learning guide and explain-back prompts](LEARNING_GUIDE.md)
- [Acceptance-probe evidence and known gaps](EVIDENCE.md)
- [AI usage and review log](BUILDLOG.md)

No automated test suite is shipped; the specific manual acceptance probes run for this local build are recorded in `EVIDENCE.md`.

FastAPI generates OpenAPI and Swagger UI from the request/response models; see its [first steps](https://fastapi.tiangolo.com/tutorial/first-steps/) and [metadata/OpenAPI guide](https://fastapi.tiangolo.com/tutorial/metadata/).
