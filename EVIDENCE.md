# Evidence

All outputs below were observed locally on 2026-09-26. The API probes used the `mock_x` adapter and an isolated `mock_linkedin` run. No external message was sent.

## Campaign, review, and idempotency

Command: `python scripts/acceptance_probe.py http://127.0.0.1:8001`

```text
PASS one-command service starts and health responds
PASS Markdown source is stored
PASS one stored post generates valid variants
PASS each variant passes its configured profile
PASS invalid variant is blocked with a named length rule
PASS tone constraints are enforced before review
PASS unapproved variant cannot be scheduled
PASS human review approval changes status
PASS approved variant can be scheduled
PASS repeated publish is idempotent
PASS publish history records the result
NOTE Discord was selected as the live adapter, but no webhook was configured; no real post was sent.
```

The service on port 8001 was started with `uvicorn app:app --host 127.0.0.1 --port 8001`. Port 8000 was already occupied, so the probe targeted the free local port.

## Durable restart recovery

Command: `python scripts/durability_probe.py`

```text
PASS service starts against a fresh temporary database
Simulated worker stopping after it claimed one local job, after a mock side effect, and during an external send.
PASS uncompleted mock job resumes after application restart
PASS completed mock side effect is recovered without a duplicate
PASS ambiguous Discord delivery is held for manual reconciliation
PASS restarted work appears once in publish history
PASS recovery probe used a temporary database and sent no external messages
```

This is a controlled restart-state simulation against a temporary SQLite database. It does not claim a live Discord retry was exercised.

## Adapter configuration swap

Command: `python scripts/adapter_swap_probe.py`

```text
PASS service starts with a different configured adapter
PASS adapter changes through configuration with no workflow code change
PASS adapter swap probe used an isolated temporary database and sent no external messages
```

## Limits

- Docker Desktop's Linux engine was unavailable on this machine, so `docker compose up --build` and a real container restart were not run. The same app was started locally with its Python server command.
- The Discord adapter is implemented, but its live send, channel message URL, and owner-side reconciliation remain unverified because no webhook was configured.
