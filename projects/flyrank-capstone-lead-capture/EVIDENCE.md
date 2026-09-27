# Evidence

## Acceptance probe run

Command: `python scripts/acceptance_probe.py` (run against a seeded isolated copy on loopback ports 8766/4174, with explicit mock settings and developer controls enabled only for the local probe). The copy did not include or read any workspace `.env` file.

Two earlier invocations in that isolated copy completed the behavioral checks but stopped at the final pack-file check because the temporary harness lacked documentation files. After those files were copied, the existing probe completed with `PASS`. The isolated database was reused, so the dashboard total of 24 below is cumulative across the three invocations.

Observed results from the successful existing probe:

```json
{
  "acceptance_probes": "PASS",
  "results": {
    "health": 200,
    "owner_auth_and_tenant_read": {"missing_token": 401, "cross_tenant_widget": 404},
    "widget_crud": {"create": 201, "read": 200, "update": 200, "delete": 200,
                     "cross_tenant_read_update_submissions": 404, "tenant_b_own_submission": 201},
    "delivery": {"config": 200, "config_bytes": 393,
                 "config_cache": "public, max-age=60, stale-while-revalidate=30", "config_etag": 304,
                 "bundle": 200, "bundle_cache": "public, max-age=31536000, immutable"},
    "public_submit": {"preflight": 204, "origin": "*", "post": 201, "stored": true,
                      "idempotent_replay": 200, "conflicting_replay": 409, "cross_tenant_submissions": 404},
    "validation": {"malformed_json": {"status": 400, "error": "invalid_json"},
                   "missing_required": {"status": 422, "error": "required_field"},
                   "oversized": {"status": 413, "error": "payload_too_large"}},
    "rate_limit": {"burst_statuses": [201, 201, 201, 429, 429, 429],
                   "retry_after_seconds": ["1", "1", "1"], "recovery_after_750ms": 201},
    "honeypot": {"first": 201, "second": 201, "stored": false},
    "geo": {"provider_a_down": {"status": 201, "provider": "provider_b", "country": "Canada"},
            "all_down": {"status": 201, "geo": null}},
    "notification": {"submission_response": 201, "stored": true, "job_status": "dead", "attempts": 3},
    "dashboard": {"status": 200, "total_submissions": 24, "widget_rows": 1, "geo_rows": 3},
    "submission_pack": {"required_files": 7, "missing": []}
  }
}
```

Notification worker output from an earlier build run (the current acceptance result confirms the dead state, three attempts, and stored lead):

```text
WARN notification retry scheduled job_id=job_96ea9c6586a440388112a0d25222d260 attempt=1
WARN notification retry scheduled job_id=job_96ea9c6586a440388112a0d25222d260 attempt=2
ALERT notification job exhausted retries job_id=job_96ea9c6586a440388112a0d25222d260 attempts=3; submission remains stored
```

## Earlier real second-origin browser proof (before reviewer fixes)

Opened `http://127.0.0.1:4173/` in Chrome while the API and bundle ran on port 8000. The accessibility tree showed the fetched title “Get the field guide,” labeled Name and Email fields, and the “Send me the guide” button. After entering synthetic demo values and submitting, the page announced: `Thanks. Your details were received.` The independent SQLite read printed:

```text
{'final_browser_submission_stored': True}
```

The API acceptance probe also confirmed that the owner submissions endpoint contains the returned submission ID and that tenant B receives 404 for tenant A's leads.

The browser flow was not re-run after the reviewer fix that retains an idempotency key across network retries. The existing API probe verifies server-side replay behavior but does not simulate a lost response and browser retry.

## Documentation and submission boundary

The acceptance probe found all seven expected pack files and no missing paths: README, capstone manifest, evidence, build log, environment example, gitignore, and design doc. The README contains run/seed steps, architecture, API contracts, and limitations.

The current run also demonstrates missing-token `401`, cross-tenant widget `404`, and dashboard summary `200` with 24 leads, one widget row, and three geo rows. Honeypot attempts receive generic `201` responses while the stored lead count remains unchanged. The non-loopback startup guard is present in configuration but was not exercised by this loopback-only probe.

The existing probe does not simulate a lost browser response/retry or assert the new pre-parse IP gate directly. The browser idempotency-key retention and non-loopback startup guard were reviewed in code but not dynamically exercised. Geo fallback used only deterministic local mocks; no visitor IP was sent externally.

At the end of the local acceptance run, the project had not yet been published or submitted. The user later authorized publication and portal submission; the verified current packaging state is recorded below. The project was implemented locally before its public repository existed, so it does not meet the brief's public-from-day-one sequence.

## Packaging status — 2026-09-26

- Public repository: https://github.com/minagayid/flyrank-capstone-lead-capture, default branch `main`, commit `14f9fd2275402af0eafc6e9a2bed41c7cee43495`.
- FlyRank capstone record: `Submitted` / waiting for review. The portal notes disclose simulated email and geo, no deployment, and the repository timing.
- This is submission evidence, not a claim of mentor acceptance or deployed behavior.
