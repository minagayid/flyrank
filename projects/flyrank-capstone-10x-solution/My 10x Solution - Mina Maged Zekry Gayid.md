# My 10x Solution — Signal Desk

## What problem am I solving?

Independent creative studios receive project inquiries through email and web forms. An inquiry may omit its budget, timeline, or exact deliverables, so an owner spends time finding the useful facts and deciding what to clarify. Signal Desk turns that first-pass review into a small, reviewable workflow while leaving every business decision with a person.

The intended user is a studio owner or small client-facing team. The 10x claim is a target: reduce a routine first-pass review from an assumed ten minutes to under one minute, without automating acceptance, rejection, or outreach. That baseline is an assumption, not a measured user result. This build tests the software flow on fictional examples; it does not claim a human time study.

## How did I implement the solution?

Signal Desk is a local Python service. A user signs in and sends an inquiry to a validated HTTP API. SQLite stores account-owned leads, hashed session tokens, triage jobs, model-use records, cached results, and final review outputs. A worker handles triage after the API returns, so a slow model call does not keep the request open. The caller can poll the job for its status and result. Repeated requests with the same idempotency key reuse the original job.

The default mock mode keeps the demo offline. An optional adapter calls a local Ollama-compatible service for one narrow job: summarize evidence in the submitted project description, show cautions, and suggest one follow-up question. The service validates the response shape and rejects evidence phrases absent from the input. A human must review the result. Local-model calls record token counts when provided, zero external provider cost, and a daily call ceiling. Content-equivalent requests can reuse a result until its cache expires. The PDF report summarizes review hints and omits names and email addresses.

### Program concepts

| Concept | Implementation |
|---|---|
| API endpoints | signal_desk/api.py validates requests and returns clear status codes |
| Database | SQLite migration in migrations/001_initial.sql; repository operations in signal_desk/database.py |
| Authentication | PBKDF2 password verification and hashed bearer sessions in signal_desk/security.py |
| Background jobs | Durable triage queue, status, and bounded retry in signal_desk/triage.py and signal_desk/worker.py |
| LLM integration | Optional local Ollama adapter, output validation, usage ledger, and call budget in signal_desk/triage.py |
| Caching logic | TTL cache keyed by input and model version in triage_cache |
| Reporting | Account-scoped PDF snapshot in signal_desk/reports.py |

No swaps were used because these concepts fit the problem.

## How to run

Requires Python 3.11 or newer; the app uses only the standard library.

1. From work/capstones/10x-solution, set SIGNAL_DESK_DEMO_USER=demo and choose a local SIGNAL_DESK_DEMO_PASSWORD of at least 12 characters.
2. Run python -m signal_desk.seed to create the demo account and fictional inquiries.
3. Run python -m signal_desk to start the API on http://127.0.0.1:8080.
4. Sign in at POST /auth/login, list example requests at GET /leads, enqueue one at POST /leads/{id}/triage, and inspect its status at GET /jobs/{id}.
5. Download a daily summary from GET /reports/daily.pdf.
6. Run python scripts/acceptance_probe.py for deterministic local acceptance checks.

The acceptance probe uses a fake local Ollama-compatible response and does not prove real model quality. No user time study, hosted deployment, public repository, or external submission is claimed.
