# Acceptance evidence

This file contains only observed behavior. At initial verification, the project was local and had not been published or submitted. Later publication and submission status will be recorded after they are verified.

## Probe command

Run from this directory:

    python scripts/acceptance_probe.py

The probe uses a temporary SQLite database, a randomly generated in-memory password, loopback HTTP servers, fictional leads, and a deterministic fake Ollama-compatible response. It makes no hosted-model request and writes no credential file.

## Results

Observed on 2026-09-26 with Python 3.14.6. The compile check, schema JSON parse, and acceptance probe exited with code 0. The probe reported 23/23 checks passed:

    PASS Seed inserts three fictional example leads.
    PASS Health route reports initialized SQLite migration 1.
    PASS Lead API rejects anonymous access with 401.
    PASS Login rejects an incorrect password with 401.
    PASS PBKDF2-backed login creates a bearer session.
    PASS Malformed lead input receives a field-validation 422.
    PASS Authenticated API creates a validated lead.
    PASS Background triage enqueue reuses the same job for the same idempotency key.
    PASS Mock triage completes asynchronously with schema-valid, input-grounded evidence.
    PASS Equivalent triage reuses the content-addressed result cache.
    PASS Cache reuse avoids a second model-ledger call.
    PASS Authenticated daily PDF has a valid cross-reference offset and omits lead contact details.
    PASS A second authenticated account cannot fetch another user's lead.
    PASS Logout revokes the stored bearer session.
    PASS Ollama adapter validates grounded output and omits lead name/email from its prompt.
    PASS Local model usage is attributed to the lead and recorded at zero provider cost.
    PASS Ollama adapter refuses non-loopback or credential-bearing service URLs.
    PASS Daily model-call budget blocks work before a second provider request.
    PASS Transient provider failure returns the durable job to queued with a retry.
    PASS Second transient failure remains bounded and records attempt two.
    PASS Job succeeds on the final allowed retry attempt.
    PASS Evidence that is not a substring of the submitted brief is rejected.
    PASS After service restart, authentication, lead rows, and completed job state persist in SQLite.

The probe summary was `Acceptance result: 23/23 checks passed.` It used a deterministic mock plus a fake loopback Ollama protocol server. No actual Ollama binary/model or hosted provider was called. The database and generated credentials were temporary and removed by the probe. `schemas/triage.schema.json` also parsed as valid JSON.

## Acceptance map

| Brief concept or shared requirement | Probe evidence |
|---|---|
| API validation and status codes | Anonymous access is 401; malformed lead input is 422; health is 200 |
| Database and account isolation | Migration readiness, cross-account 404, and service-restart persistence checks |
| Authentication | Valid and invalid login, protected routes, logout revocation |
| Background job | 202 enqueue and durable status/result polling |
| Bounded retry | Injected transient failures produce attempt counts 1, 2, and success on attempt 3 |
| LLM output validation | Fake local Ollama protocol response; invented evidence is rejected |
| Cost/usage tracking and budget | Token counts are recorded at local provider cost zero; budget blocks before another request |
| Caching | Equivalent input is reused without another ledger call |
| PDF report | PDF header/type and contact-data omission |

The fake local server proves the adapter contract only. No real Ollama binary/model was present or queried. The 10x time reduction remains a target because no manual baseline or user study was performed.
