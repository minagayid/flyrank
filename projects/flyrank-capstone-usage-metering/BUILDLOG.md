# AI build log

## 2026-09-26 — initial local implementation

- **AI assistance:** Codex read the full extracted capstone brief, compared the requested scope with the existing workspace, selected FastAPI + SQLite, and is generating the implementation and documentation in this isolated directory.
- **Human input:** The task owner supplied the brief path, feature list, no-credentials/no-payment boundary, local run target, and instruction not to publish or touch the portal. The task owner has not hand-written or reviewed code in this build.
- **Correction:** The first AI draft represented one `/generate` action as separate call and token rows. Review against the brief's “exactly one usage event” rule caught the mismatch; migration `002` now stores one `billable_action` row with separate call/token quantities and cost columns. The recorded acceptance probe verified one row per key.
- **Verification:** The manual acceptance probes showed one durable event row for a repeated `/generate` key, exact call/token quota boundaries, integer pricing totals, valid/forged/replayed local mock webhooks, a `402` for a past-due subscription, `422` for malformed input, and a completed invoice job. After a service restart, usage, invoice preview, migration version, and job status persisted in SQLite.
- **Still unverified:** No real Stripe test credentials or Stripe CLI were used; mock-mode evidence is not evidence of Stripe test Checkout. The repository is local and was not published or submitted.
- **Ownership reminder:** This is AI-assisted work, not a claim of hand-built code. The owner should read the design, rehearse the idempotency transaction, quota boundary, pricing arithmetic, and webhook trust boundary, and review the implementation before describing it as their own work.
- **External actions:** No account, secret, payment, public repository, or portal submission is used by the local mock build.

## 2026-09-26 — evidence follow-up

- **AI assistance:** Codex added a deterministic local retry/alert probe and a scoped source-only secret-pattern scanner at the task owner's request.
- **Retry/alert probe:** `uv run --no-sync python scripts/retry_alert_probe.py` used a temporary SQLite database, disabled python-dotenv before importing the application, selected mock payment mode, removed Stripe key variables from its child-process environment, and injected a deterministic failure in the invoice-summary function. Observed attempts 1 and 2 in `retry`, attempt 3 in `failed`, and one persisted critical alert after reopening SQLite. All 4 assertions passed. No `.env` file, payment, or provider call was used.
- **Secret scan:** `python scripts/secret_scan.py` scanned 27 safe text files and found 0 pattern matches. It explicitly skipped `.env`, `.env.*`, `*.env`, generated/private directories, binary/generated artifacts, and symlinks before opening contents. This is a bounded pattern scan, not a dedicated vendor scanner; excluded private data was not inspected.
- **Still unverified:** Real Stripe test Checkout and Stripe CLI delivery remain untested. No `.env` file, live/test key, paid service, public repo, or portal submission was used.

## Packaging checkpoint

- The user authorized a dedicated public GitHub repository and FlyRank submission. The project was implemented locally before repository creation, so the brief's public-from-day-one and staged-commit sequence was not met. The repository history will not be represented as if it did.
- Published at https://github.com/minagayid/flyrank-capstone-usage-metering (commit `7e07e0dfc603828b981b1b72109add09895c35f0`). FlyRank shows `Submitted`, waiting for review; the mentor's decision is not yet known.
