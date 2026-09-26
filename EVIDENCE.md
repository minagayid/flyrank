# Evidence

Acceptance probes were run manually against the local service on `http://127.0.0.1:8765` on 2026-09-26. Port 8000 was already occupied by another process, which was left untouched. The default manifest/run configuration remains port 8000. No automated test suite was added because the brief makes `test:` optional; the probes below are the brief's named behavioral acceptance checks plus the shared boundary/persistence checks.

## Section 6 requirements

### Metering — one event per action and idempotent replay

`POST /generate` with the same body and `Idempotency-Key` twice returned `201` both times. The second response had `Idempotent-Replayed: true`; the JSON body was byte-for-byte equal to the first response. Each response contained one event ID. A direct SQLite read for that tenant/key returned exactly one `usage_events` row of type `billable_action`.

### Quota enforcement — equality is allowed, the next unit is rejected

Using the seeded Free tenant after one initial API call:

```text
POST /usage/events api_calls quantity=998  -> 201 (999 used)
POST /usage/events api_calls quantity=1    -> 201 (exactly 1,000 used)
POST /usage/events api_calls quantity=1    -> 429
  "The api calls quota would be exceeded: 1000 used + 1 requested > 1000 allowed this month."
  Retry-After: 413318 seconds in the captured run
```

Using the same Free tenant after its initial 10-token event:

```text
POST /usage/events ai_tokens quantity=99990 -> 201 (exactly 100,000 used)
POST /usage/events ai_tokens quantity=1     -> 429
  "The ai tokens quota would be exceeded: 100000 used + 1 requested > 100000 allowed this month."
```

### Cost calculation — pinned example rates and category rules

`POST /generate` for the seeded Pro tenant used 1,000,000 fresh input, 500,000 cached input, 250,000 output, and 250,000 reasoning tokens. The response contained one event row. `GET /usage` reported 1,000,000 API-call micro-cents, 47,500,000 token micro-cents, and 49 total rounded cents. `GET /invoices/preview` reported a 2,999-cent Pro plan due amount and a separate 49-cent usage-cost estimate.

```text
Fresh input:  1,000,000 × 15 micro-cents = 15,000,000 micro-cents = 15 cents
Cached input:   500,000 ×  5 micro-cents =  2,500,000 micro-cents = 2.5 cents
Output:         250,000 × 60 micro-cents = 15,000,000 micro-cents = 15 cents
Reasoning:      250,000 × 60 micro-cents = 15,000,000 micro-cents = 15 cents
Token total:                                                       47.5 cents → 48 cents
One API call:                                                       1 cent
Usage estimate:                                                    49 cents
```

The cost rates are synthetic pinned assumptions, not a claim about current provider pricing.

### Stripe integration — offline mock verified; real Stripe path not exercised

```text
POST /billing/checkout, same tenant/key twice -> 201; same mock checkout ID returned
POST /mock-checkout/{id}/complete            -> applied=true; Free → Pro
Replay same completion/event                  -> duplicate=true; no second update
GET /usage                                    -> Pro, 50,000 calls / 5,000,000 tokens
Forged signature to POST /webhooks/stripe     -> 400 invalid_webhook_signature
GET /usage before/after forgery                -> plan remained Free
Signed local mock subscription event          -> 200 applied=true
Replay same signed event ID                    -> 200 duplicate=true
Signed past_due event then POST /generate     -> 402 subscription_inactive
Signed active event                            -> 200; subscription restored to active
```

The mock events use a local HMAC secret and the same state-update/deduplication path; they are not Stripe-originated events. No Stripe account, API key, Checkout page, card, or payment was used. The optional `stripe_test` adapter requires user-provided `sk_test_` and `whsec_` values and was not run.

## Shared capstone requirements

| Requirement | Observed proof | Limit |
|---|---|---|
| Layered architecture | `DESIGN.md`; HTTP in `app/api.py`, logic in service modules, persistence in `app/db.py` and SQL migrations | Local demo architecture only |
| Boundary validation | Negative token count returned `422 validation_error` rather than `500` | One malformed-input probe |
| Background work, retries, alerting | The normal invoice job completed; `scripts/retry_alert_probe.py` forced attempts 1 and 2 into retry, attempt 3 into failed, and then reopened SQLite to confirm one persisted critical alert | Deterministic injected `RuntimeError`; does not simulate an actual infrastructure outage |
| Real persistence and tenant isolation | SQLite migration versions `[1, 2]`; usage indexes `idx_usage_tenant_period_type` and `idx_usage_tenant_idempotency`; mismatched tenant key returned `401` | Demo keys are public sample credentials, not production auth |
| Idempotency | Same request/key returned the original response; SQLite count for that key is exactly one `billable_action` row | Local single-process SQLite run |
| Secrets clean | `scripts/secret_scan.py` scanned 27 project text files and found 0 credential-pattern matches | Explicitly excludes all `.env`-style files and generated/private data; local pattern scan, not a dedicated vendor scanner |
| AI cost tracking | Simulated token quantities are attributed per tenant and month and priced as integer micro-cents | No model call is made |

## Runtime and persistence checks

- `uv sync` resolved the project lockfile and installed FastAPI 0.141.1, Stripe SDK 15.6.1, and Uvicorn 0.54.0 on Python 3.11.15.
- `uv run python -m compileall -q app` completed without syntax errors.
- FastAPI generated OpenAPI and Swagger UI routes; `GET /health` returned `200` with SQLite and migration readiness.
- A durable invoice-summary job completed and SQLite contained one stored summary for the Pro demo tenant; no failure alert was created.
- After stopping and restarting the service on port 8765, `GET /health` returned `ok` at migration 2; `GET /usage` still showed Pro/active with 1 call and 2,000,000 tokens; the 2,999-cent invoice preview and previously completed invoice job remained available.

## Retry-exhaustion and scoped secret-scan follow-up — 2026-09-26

Runtime: Python 3.11.15. Both commands exited with code 0.

### Persisted retry-exhaustion alert

Command:

    uv run --no-sync python scripts/retry_alert_probe.py

The probe disabled python-dotenv before importing app modules, selected `PAYMENT_MODE=mock`, removed Stripe key variables from its child-process environment, and used a temporary SQLite database. It replaced only the invoice-summary function with a deterministic `RuntimeError` and advanced the job clock across the retry delays. No `.env` file was read, and no payment or provider integration was called.

Observed output:

```text
PASS attempt 1: status=retry, attempts=1/3, alerts=0
PASS attempt 2: status=retry, attempts=2/3, alerts=0
PASS attempt 3: status=failed, attempts=3/3, one critical alert persisted
PASS reopened SQLite: failed job and critical alert match the committed state
PASS retry-exhaustion probe: 4/4 checks passed; no payment/provider call made
```

The terminal job row was `failed` with `attempts=3`, `max_attempts=3`, and the sanitized error `Invoice summary worker failed with RuntimeError.` A fresh SQLite connection after database initialization read exactly one associated alert: level `critical`, message `Invoice summary job exhausted its retry budget.` The temporary database was removed when the probe exited.

### Pattern-based secret scan

Command:

    python scripts/secret_scan.py

Observed output:

```text
Scan scope: project text source/docs/lockfile only.
Excluded before reading: names matching .env, .env.*, *.env (including inside directories); .git, virtualenv, cache, node_modules, build, coverage, data, var, outputs, reports, private, secrets, uploads, artifacts, storage, tmp, and temp directories; database, log, PDF, image, key, certificate, archive files, and symlinks.
Scanned 27 text file(s); excluded 1 .env-style file(s) and 3 generated/private path(s).
Secret scan: 0 findings.
```

Rules covered private-key markers, common AWS/GitHub/Slack/Stripe/Google credential formats, JWT-shaped tokens, and long quoted credential assignments. The scanner reports file and rule only, never a possible value. `.env` files and the listed generated/private paths were excluded before opening any file contents. This bounded local scan is evidence for the included text source, not a guarantee about excluded data or a substitute for a dedicated repository scanner.

## Not performed

- No paid service, real payment, Stripe account, Stripe CLI, or real Stripe test checkout.
- No `.env` file was read; `.env`-style files were excluded before content scanning.
- No deployment, separate public GitHub repository creation, or FlyRank portal submission.
- No claim of production security, production reliability, human-authored code, or mentor acceptance.
