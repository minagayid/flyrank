# Signal Desk — lead triage service

Signal Desk helps a small creative studio review project inquiries, see the request evidence, and choose a useful follow-up question. It keeps the person in control: a score is a sorting hint, never a probability or a decision, and the service never rejects a lead or sends a message.

## The problem and the 10x claim

An owner who receives incomplete project requests can spend several minutes finding the useful details and deciding what to ask next. This build tests the idea that a first-pass review could move from an assumed 10 minutes to under 1 minute, while leaving the decision with a person. That is a design target, not a measured time saving or user-study result. The acceptance probe measures software behavior on fictional data; it does not measure a studio's manual workflow.

The first release has five user-facing features:

1. Accept, validate, and browse inquiries through an authenticated HTTP API.
2. Save leads, sessions, jobs, and review results durably in SQLite.
3. Queue a narrow lead-review task outside the API request and retry transient failures.
4. Reuse identical review results, validate model output against the request, and enforce a daily local-model call limit.
5. Download a daily one-page PDF summary that omits names and email addresses.

## Program concepts implemented

| Concept | Where it lives |
|---|---|
| API endpoints with validation and status codes | signal_desk/api.py, signal_desk/leads.py |
| Database with persistence and indexes | migrations/001_initial.sql, signal_desk/database.py |
| Authentication and protected routes | signal_desk/security.py, signal_desk/api.py |
| Background jobs, retries, progress, and failure state | signal_desk/triage.py, signal_desk/worker.py |
| LLM integration with validation and a cost/usage log | signal_desk/triage.py, schemas/triage.schema.json |
| Caching logic | triage_cache table and cache-key logic in signal_desk/triage.py |
| PDF reporting | signal_desk/reports.py, GET /reports/daily.pdf |

No swaps are used. The LLM path talks only to an optional local Ollama-compatible server. Default mock mode uses a deterministic fixture provider so the API works offline; mock output is not described as a live LLM result. The ledger records provider, model, token counts where available, outcome, and cost in micro-USD. Local Ollama calls have a recorded provider cost of zero and a configurable daily call limit. This does not estimate electricity or hardware costs.

## Architecture

    Client
      ├── POST /auth/login ──> PBKDF2 password check ──> hashed opaque session
      └── Bearer token ──> validated HTTP API
                              ├── leads / SQLite
                              ├── triage request ──> durable job row ──> worker
                              │                       ├── content cache
                              │                       ├── mock or local Ollama adapter
                              │                       └── schema + evidence validation
                              └── daily PDF report <── SQLite review results

## Run locally

Requires Python 3.11 or newer. The project uses only the Python standard library; it needs no API key, account, paid service, or database server. It reads configuration from process environment variables and does not load .env files.

In PowerShell, from this directory, choose a local demo password and seed fictional records:

    $env:SIGNAL_DESK_DEMO_USER = "demo"
    $env:SIGNAL_DESK_DEMO_PASSWORD = Read-Host "Choose a local demo password (12+ characters)"
    python -m signal_desk.seed

Start the service in that same terminal:

    python -m signal_desk

The API binds to http://127.0.0.1:8080. The environment defaults to offline mock mode. Open /health to see readiness; /docs is not included because the server uses only the standard library.

The account password is chosen at seed time and is not printed. Re-running the seed keeps existing records and does not rotate an existing account's password. To use another password, select a different demo username or remove the local database yourself.

## Five-minute demo path

Open a second PowerShell terminal in this directory. Enter the same local password chosen above:

    $password = Read-Host "Local demo password"
    $body = @{ username = "demo"; password = $password } | ConvertTo-Json
    $session = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/auth/login -ContentType "application/json" -Body $body
    $headers = @{ Authorization = "Bearer $($session.access_token)" }

List the three fictional seeded inquiries and request a review of the first:

    $leads = Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8080/leads -Headers $headers
    $lead = $leads.items[0]
    $jobHeaders = @{ Authorization = $headers.Authorization; "Idempotency-Key" = "demo-review-001" }
    $job = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/leads/$($lead.id)/triage" -Headers $jobHeaders
    do {
      Start-Sleep -Milliseconds 100
      $result = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/jobs/$($job.job_id)" -Headers $headers
    } until ($result.job.status -in @("succeeded", "failed"))
    $result.job.result

Review the matched text, cautions, and next question. The service provides no automatic accept/reject action. Save a daily PDF snapshot:

    Invoke-WebRequest -Uri http://127.0.0.1:8080/reports/daily.pdf -Headers $headers -OutFile .\daily-report.pdf

The acceptance probe runs locally in one command:

    python scripts/acceptance_probe.py

## API map

| Method and path | Purpose |
|---|---|
| GET /health | Public database and queue readiness |
| POST /auth/login | Start a password-authenticated session |
| GET /auth/me, POST /auth/logout | Inspect or revoke the current session |
| GET /leads, POST /leads, GET /leads/{id} | Read and create account-owned inquiries |
| POST /leads/{id}/triage | Enqueue review; requires Idempotency-Key |
| GET /jobs/{id} | Read owner-scoped job status, attempts, result, and cache hit |
| GET /reports/daily.pdf?date=YYYY-MM-DD | Download an account-scoped PDF snapshot |

Invalid JSON returns 400, malformed fields return 422, missing/invalid authentication returns 401, and an unknown or cross-account ID returns 404. There is no endpoint for sending emails, rejecting a person, or changing a lead's status automatically.

## Optional local LLM

To exercise the real adapter, run Ollama locally, pull a model you already have access to, then set SIGNAL_DESK_AI_MODE=ollama and optionally SIGNAL_DESK_OLLAMA_URL / SIGNAL_DESK_OLLAMA_MODEL before starting the service. The default probe uses a local fake Ollama-compatible endpoint to validate request/response handling without a model download. No hosted provider or API key is supported by this project.

The adapter accepts only a loopback URL and omits lead name and email from its prompt. It treats project text as untrusted data, asks for a small JSON result, checks exact fields and value bounds, and rejects any claimed evidence phrase that does not occur in the submitted description. A daily request ceiling blocks another local-model call before it is sent. A person must review every result.

## Limitations and future ideas

This is a single-process local learning build. The opaque bearer sessions use SQLite and are not a substitute for a production identity provider; the HTTP server has no TLS, login rate limit, CSRF-protected browser UI, multi-worker queue, or deployment. Local-model behavior depends on the installed model and has not been validated on real customer data. The mock provider demonstrates deterministic behavior, not LLM quality. The PDF writer supports a compact one-page text summary with up to 13 recent results and a count of omitted results. No human time study, production traffic, external model call, or deployed URL is claimed.

Future ideas: a studio-specific service catalog, reviewed interview tasks for model drift, and a browser UI. Automated rejection and automatic outbound messages remain explicit non-goals.

## AI-assisted development

Codex generated most of this implementation and its documentation from the approved Signal Desk concept and the 10x capstone brief. The local acceptance probe records observed behavior; generated code is not evidence of learner understanding. Read LEARNING_NOTES.md, trace the API-to-database path, and be ready to explain retry/idempotency behavior, bearer-token storage, validation, cache keys, and the local-model boundary before presenting the project.

See DESIGN.md, BUILDLOG.md, EVIDENCE.md, and My 10x Solution - Mina Maged Zekry Gayid.md for the design, honest work record, probe results, and submission overview.
