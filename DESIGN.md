# Design — Signal Desk 10x Solution

## Problem and claim

Small creative studios receive incomplete requests through email and web forms. A studio owner must find the useful facts, identify missing details, and decide what to do next. Signal Desk packages the first-pass review into a private, repeatable API flow.

The 10x claim is a hypothesis: make routine first-pass review take under one minute rather than an assumed ten minutes, with the same human decision point. The acceptance probe does not measure manual review time, so no measured 10x result is claimed.

## Five features

1. Authenticated lead intake and scoped read routes.
2. Durable lead, session, job, result, model-call, and cache storage.
3. Asynchronous triage with bounded retries and observable job status.
4. Grounded model output, reusable content cache, and local call budget.
5. Account-scoped daily PDF report with contact details omitted.

## Data flow

    POST /auth/login → PBKDF2 verify → opaque random token → SHA-256 token digest in SQLite
    POST /leads → strict boundary validation → owner-scoped lead row
    POST /leads/{id}/triage + Idempotency-Key → unique job row → HTTP 202
    worker → content/model cache → mock or Ollama adapter → schema/evidence validation
           → model-call ledger + triage result + terminal job status
    GET /jobs/{id} → owner-scoped progress/result
    GET /reports/daily.pdf → filtered, contact-free result snapshot

Job claiming and state changes use short SQLite BEGIN IMMEDIATE transactions. A failed provider call is retried with a short bounded delay; only three attempts are allowed. Repeating the same key for one lead returns the original job. Content-equivalent requests reuse a cached result for the configured time-to-live.

## Data ownership and model limits

All lead, job, session, and report queries include the authenticated account ID. Passwords use PBKDF2-HMAC-SHA256 with per-user random salt; bearer tokens are random and only their SHA-256 digests are stored. The default model mode is an offline deterministic fixture. Optional Ollama output is untrusted until strict field and evidence-substring checks pass; the adapter refuses non-loopback URLs. The score is neither calibrated nor used to reject a person. No names/emails are sent to the local model; PDF snapshots include IDs and review hints only.

## Core concepts and non-goal

Implemented core concepts: API, persistent database, authentication, background jobs, PDF reporting, cache, and LLM integration. No swaps are used. Explicit non-goal: automatically reject leads or send any outbound message. Production identity, remote hosting, and live user-data processing are out of scope.
