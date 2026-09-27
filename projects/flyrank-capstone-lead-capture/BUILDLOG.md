# Build log

## 2026-09-26 — local capstone build

- AI assistance helped map the capstone brief into request paths, a tenant-scoped SQLite model, API validation boundaries, the embed script, deterministic fallback behavior, and a local acceptance-probe plan.
- AI generated first drafts of the migration, Python HTTP service, worker, widget script, probe helper, and documentation. Codex reviewed and adjusted them against the brief; no human code review is claimed. Runtime evidence comes from the documented probes, not from code generation.
- Corrections made during implementation: the probe's first direct invocation could not import the package, so it now adds the project root to its import path. Its first HTTP helper also assumed a JavaScript bundle response was JSON; the helper now preserves a short non-JSON response summary rather than failing. Validation was hardened so malformed nested JSON becomes a 400, not a 500. Soft-deleted widget leads remain visible to their owner.
- Deliberate choices: Python standard library and SQLite keep the path at $0 with no package install; mock geo is the default; the notification is a console-only outbox job; owner tokens are SHA-256 digests; raw visitor IP is not persisted or logged. No real email, geo API, hosting, or account was used.

## Observed verification

- `python -m compileall -q lead_capture scripts` completed without syntax errors.
- `python -m lead_capture.seed` created the two local demo tenants and `widget_demo_signup` without printing their tokens.
- `python scripts/acceptance_probe.py` returned `acceptance_probes: PASS`. It exercised owner CRUD and tenant isolation, snippet/config/bundle caching, CORS preflight and submission, idempotent replay, malformed/oversized payloads, rate-limit and recovery, honeypot suppression, both geo fallback cases, worker retries, owner stats, and required pack files. Exact observed results are in EVIDENCE.md.
- Chrome opened the actual customer page on port 4173 while the API ran on port 8000. The fetched widget rendered labeled inputs, accepted a synthetic test lead, and announced success; a separate SQLite query confirmed the row was stored.
- The worker emitted two retry messages and an `ALERT` after the configured three attempts while the submission response stayed 201 and the lead remained stored.
- At the end of the local build checkpoint, no deployment, public GitHub repository, or portal submission had been made because the then-active task prohibited them. The later user authorization and verified package status are recorded below.

## 2026-09-26 — reviewer fixes

- A read-only review found that the widget generated a new idempotency key after network failures, the honeypot response disclosed suppression, and malformed requests reached parsing and database lookups before any IP throttle. The widget now retains the same serialized payload/key until success; the honeypot returns a neutral success-shaped response without storing or queuing anything; and an IP admission bucket runs before parsing, with a separate per-widget bucket after widget resolution.
- Developer controls now default off. Startup rejects non-loopback API/public URLs while either known demo owner token remains or developer controls are enabled. `.env.example` keeps controls off; enable them only in a loopback shell for deterministic local probes.
- Removed the live geolocation adapter because provider A was contacted over plain HTTP. Geo is mock-only until a vetted HTTPS adapter is added; no visitor IP is sent to an external provider.
- Updated the existing acceptance probe's honeypot assertion to check for a neutral success-shaped response and unchanged stored lead count. Two initial isolated probe invocations stopped only at the final pack check because their temporary copy lacked documentation files. After copying the expected pack files, the existing probe completed with `acceptance_probes: PASS`; the reused isolated database reported 24 cumulative owner leads, one widget row, and three geo rows. It also confirmed the missing-token `401`, cross-tenant `404`, `429` burst/recovery, neutral honeypot `201` with no stored lead, and worker dead-letter after three attempts.
- That existing probe does not simulate a lost browser response/retry or directly assert the early IP admission gate. Those paths and the non-loopback startup guard were reviewed in code but not dynamically exercised. The run used explicit loopback/mock environment values in a copy that excluded `.env`; no live geo provider was contacted.

## Packaging checkpoint

- The user authorized a dedicated public GitHub repository and FlyRank submission. The project was built locally before repository creation, so the brief's public-from-day-one and staged-commit sequence was not met. The existing AI-use, corrections, evidence, and unverified checks remain disclosed above.
- Published at https://github.com/minagayid/flyrank-capstone-lead-capture (commit `14f9fd2275402af0eafc6e9a2bed41c7cee43495`). FlyRank shows `Submitted`, waiting for review; the mentor's decision is not yet known.
