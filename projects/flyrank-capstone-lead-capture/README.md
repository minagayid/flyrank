# FlyRank Capstone: Embeddable Widget & Lead-Capture Platform

A local-first service that lets an owner define a signup/contact widget, copy one script tag, render it on another origin, and receive protected, validated, optionally enriched leads. It uses only Python's standard library and SQLite. The demo uses synthetic data, deterministic mock geo providers, and a console notification; no account, API key, credit card, or external service is needed.

## Architecture

```text
Owner (Bearer token) -> API -> tenant-scoped widget CRUD / dashboard -> SQLite
Customer page :4173 -> immutable /widget.v1.js :8000 -> cached public config
Visitor -> CORS + IP admission gate -> bounded validation -> per-widget token bucket -> honeypot
        -> geo A/B fallback -> SQLite transaction + outbox -> retry worker
```

The separation is deliberate: authenticated owner routes never share the public wildcard-CORS policy; public config and submissions are anonymous and never rely on the `Origin` header as identity. The complete short design is in [docs/DESIGN.md](docs/DESIGN.md).

## Run locally (free)

Requires Python 3.11 or later; this implementation was built with Python 3.14 and has no pip dependencies.

1. Copy `.env.example` to `.env`. The checked-in values are public local-demo tokens, not production credentials. Change the owner tokens and IP hash salt before exposing the service; keep `.env` private.
2. Seed the demo database once:

   ```powershell
   Copy-Item .env.example .env
   python -m lead_capture.seed
   ```

   On macOS/Linux, use `cp .env.example .env` for the copy step. The seed creates two tenants and one signup widget (`widget_demo_signup`) so tenant isolation is easy to demonstrate.
3. Start the API, background notification worker, and second-origin test site with one command:

   ```powershell
   python -m lead_capture.app
   ```

4. Open `http://127.0.0.1:4173/` for the customer page. The widget JavaScript and API run at `http://127.0.0.1:8000/`; the owner dashboard is `http://127.0.0.1:8000/dashboard`. Stop the process with Ctrl+C.

The app binds to loopback by default. Keep it there for the demo. `DB_PATH` may point to a different local SQLite file. `API_PORT` and `DEMO_PORT` can be changed together with `PUBLIC_BASE_URL` and the script URL in `demo/index.html` if those ports are unavailable.

## Local demo owners

Tokens are synthetic, local-only examples from `.env.example`; the app stores only SHA-256 token digests. Do not deploy the example tokens. Use these for the seeded workspaces:

```text
Workspace A: local-demo-tenant-a-only-change-before-hosting-123
Workspace B: local-demo-tenant-b-only-change-before-hosting-456
```

Paste one into the local owner dashboard, or use it in an API header. Never put a real token into a URL or browser history.

```powershell
$ownerToken = "local-demo-tenant-a-only-change-before-hosting-123"
Invoke-RestMethod -Headers @{ Authorization = "Bearer $ownerToken" } `
  http://127.0.0.1:8000/api/widgets/widget_demo_signup/embed
```

The response's `snippet` value is one line of HTML. The demo page contains the same generated snippet.

## API

Owner endpoints require `Authorization: Bearer <token>`; the owner token selects a tenant. IDs owned by another tenant return 404.

| Route | Purpose | Typical responses |
|---|---|---|
| `GET /health` | Process health | `200` |
| `GET /api/widgets` | List current tenant's widgets | `200`, `401` |
| `POST /api/widgets` | Create a widget | `201`, `401`, `422` |
| `GET /api/widgets/{id}` | Read one owned widget | `200`, `401`, `404` |
| `PUT /api/widgets/{id}` | Replace its validated definition; increments config version | `200`, `401`, `404`, `422` |
| `DELETE /api/widgets/{id}` | Soft-delete; preserves leads | `200`, `401`, `404` |
| `GET /api/widgets/{id}/embed` | Generate the one-line script | `200`, `401`, `404` |
| `GET /api/widgets/{id}/submissions?limit=50` | List own leads, 1–100 | `200`, `400`, `401`, `404` |
| `GET /api/dashboard/summary` | Counts by day, widget, and country | `200`, `401` |
| `GET /api/dashboard/jobs` | Own notification job status | `200`, `401` |
| `GET /api/public/widgets/{id}/config` | Public validated form config; 60-second cache + ETag | `200`, `304`, `404` |
| `GET /widget.v1.js?widget_id={id}` | Immutable, versioned widget bundle | `200`, `400`, `404` |
| `POST /api/public/submissions` | Public cross-origin form submit | `201`, `200` replay, `400`, `404`, `409`, `413`, `415`, `422`, `429` |

Example public body:

```json
{
  "widget_id": "widget_demo_signup",
  "fields": {"name": "Ada Example", "email": "ada@example.test"},
  "company_website": ""
}
```

Send JSON and an `Idempotency-Key` header (8–100 safe characters). The browser script keeps the same key and exact body after a network or server failure, reuses them when the visitor retries that payload, and discards the key only after a successful response. A changed payload gets a new key. Replaying the same key and payload returns the original submission; reusing that key with different fields returns `409`. The script sends `Origin` cross-origin; public responses allow `GET, POST, OPTIONS` and `Content-Type, Idempotency-Key`, without credentials. A bad or oversized request gets a JSON error, not an HTML server traceback.

## Validation, abuse controls, and resilience

- Only 1–6 configured fields are accepted. Names are schema-bound; required, type, email/phone, and length rules are enforced at the API boundary. Unknown values, control characters, malformed JSON, non-JSON bodies, and bodies above `MAX_REQUEST_BYTES` are rejected.
- A process-local IP admission bucket runs before body parsing or database lookups (defaults: 20 tokens, refilling at 10/second). After a valid widget is resolved, a separate per-widget token bucket limits new submissions (defaults: 3 tokens, refilling at 2/second); `429` includes `Retry-After`. These local buckets would need shared storage in a multi-process deployment.
- The visually hidden `company_website` honeypot stores no lead or notification job. It returns the same generic success-shaped response as a real lead, so a bot is not told it was detected.
- Raw visitor IP is neither stored nor logged. It is used transiently for the admission/rate-limit decision, then represented by a salted SHA-256 digest in storage. Geo enrichment is mock-only, so no visitor IP is sent to an external provider.
- Mock geo provider A returns US/Ashburn; provider B returns CA/Toronto. Owner-authenticated local dev controls at `POST /api/dev/geo` can toggle either provider down. Both failing leaves a valid submission successful and without geo.
- A successful submission and a notification outbox row are committed together. The worker logs a simulated notification, retries failures with backoff, then logs an `ALERT`; a notification failure never undoes a stored lead. No real email or webhook is sent.
- Developer controls default to off. For local fallback/retry proof only, set `ALLOW_DEV_CONTROLS=true` while the API and public base URL remain on loopback. Startup rejects non-loopback use while either known demo owner token remains or developer controls are enabled. Replace both demo tokens and keep controls off before exposing the API.
- Geo providers are mock-only. A future live provider adapter must use HTTPS before it can receive visitor IPs.

## Cache behavior

`/widget.v1.js` returns `Cache-Control: public, max-age=31536000, immutable`; change `WIDGET_BUNDLE_VERSION` when shipping a new JS bundle. Widget config returns `Cache-Control: public, max-age=60, stale-while-revalidate=30` plus an ETag and `304` support. No real CDN or public host is needed to prove the contract.

## Required capstone files and evidence

- [capstone.yaml](capstone.yaml): run, seed, base URL, and probe endpoints.
- [EVIDENCE.md](EVIDENCE.md): acceptance-probe proof for each contract item.
- [BUILDLOG.md](BUILDLOG.md): honest AI-use and correction log.
- [.env.example](.env.example) and [.gitignore](.gitignore): safe local configuration and ignored data.
- [docs/DESIGN.md](docs/DESIGN.md): the one-page model, API paths, and explicit non-goal.

This project was implemented locally before its dedicated public repository was created. That does not follow the brief's “public from day one” sequence or staged-commit history expectation; the repository history is not represented as if it did.

## Limitations

This is a local educational implementation, not a hosted production service. Rate limiting is in-memory and per process; demo bearer tokens are fixed examples; notifications are console-only; geo is deterministic mock-only; SQLite is single-node; there is no real CDN, user-registration flow, CSRF cookie auth, or legal consent workflow. Before real traffic, add durable shared rate limiting, managed identity/secrets, security review, consent/retention policy, abuse monitoring, and a vetted HTTPS geo adapter.
