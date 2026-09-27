# Learning guide

This guide is a map for explaining the design in your own words. The code is AI-assisted; reading it is part of the work.

## 1. Idempotency and exactly-once recording

Read `app/metering.py` → `record_usage` and `app/migrations/001_initial.sql` → `idempotency_records`. A write starts with `BEGIN IMMEDIATE`, checks the tenant-scoped key, then either returns the stored response or commits the usage row and response together. The request fingerprint prevents one key from being reused for a different payload. Why must the event insert and idempotency response share one transaction?

## 2. Quota boundaries

Read the projected-usage comparison in `record_usage`: `used + requested > limit` blocks; equality is allowed. The transaction serializes concurrent writes before this check, so two simultaneous requests cannot both spend the same final unit. What changes if the comparison uses `>=`? What does `Retry-After` tell the client?

## 3. Integer money and token categories

Read `app/pricing.py` and `app/config.py`. One cent is represented as 1,000,000 micro-cents. For the pinned example rates, 1,000,000 fresh input tokens cost 15 cents; 500,000 cached input tokens cost 2.5 cents; 250,000 output plus 250,000 reasoning tokens cost 30 cents. The combined 47.5-cent token estimate rounds half-up to 48 cents. Reasoning uses the output rate; categories are disjoint and are never added twice.

## 4. Webhook trust and replay protection

Read `app/billing.py` → `_verified_event`, `receive_webhook`, and `apply_verified_event`. The test-mode branch asks the Stripe SDK to construct the event from the untouched request bytes, signature header, and endpoint secret. The offline mock has its own clearly labeled local HMAC scheme. Only a verified event may update a subscription, and `stripe_events.event_id` makes a replay a no-op. Why must a browser redirect from Checkout never be treated as proof of payment?

## 5. Persistence and background work

Read `app/db.py`, `app/migrations/`, and `app/jobs.py`. SQLite is durable local storage; versioned SQL creates tenant foreign keys and tenant/period and due-job indexes. The invoice worker claims a leased job, stores the summary, retries a failed attempt with backoff, and records an operations alert after the retry budget is exhausted. What happens to a job if the process stops while its lease is active?

## Explain-back prompts

Before presenting this capstone, answer these without looking at the code:

1. Why does a duplicate request return the original status and body?
2. Why is the quota comparison made inside a write transaction?
3. How do cached and reasoning tokens affect the monthly estimate?
4. Which exact evidence proves that a webhook is allowed to change the plan?
5. What is durable in this SQLite demo, and what limitation remains in its background worker?
