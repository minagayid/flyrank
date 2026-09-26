# FlyRank Capstone: Social Media Studio

This public repository is dedicated to the Social Studio capstone. It stores each source post, generates platform-specific variants, enforces constraints before review, schedules approved content durably, and records publish attempts.

The system provides a small browser dashboard and a FastAPI backend. Copy can be generated from pasted Markdown or a public article URL. Templates are used instead of an external AI service, so the core runs for free and its validation stays deterministic.

## Run it

The demo seed creates a sample post and three draft variants automatically. The safe default publisher is `mock_x`.

```sh
docker compose up --build
```

Open <http://localhost:8000>. The SQLite database is stored in a named Docker volume and survives container restarts.

For a local Python run instead:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.lock
uvicorn app:app --reload
```

Interactive API documentation is at <http://localhost:8000/docs>; health is at `/health`.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Storage and configured publisher status |
| `GET` | `/profiles` | Platform length, tone, and hashtag rules |
| `POST` | `/posts` | Store Markdown or a public article URL |
| `GET` | `/posts` | List stored source posts |
| `POST` | `/posts/{id}/generate` | Generate and validate one variant per platform |
| `POST` | `/posts/{id}/variants` | Add a manually drafted variant (invalid copy returns 422) |
| `GET` | `/variants` | Review the generated variants |
| `PATCH` | `/variants/{id}` | Edit, approve, or reject a variant |
| `POST` | `/variants/{id}/schedule` | Schedule an approved variant in a timezone-aware slot |
| `GET` | `/schedules` | Inspect scheduled and completed work |
| `GET` | `/history` | Visible record of every publish attempt |

The live publisher is selected with `PUBLISHER=discord`; the alternatives are `mock_x` and `mock_linkedin`. For Discord, copy `.env.example` to `.env`, set `DISCORD_WEBHOOK_URL` to a webhook in a server/channel you own, and set `PUBLISHER=discord`. With Docker Compose, those values are read from `.env`. For a local Python server, start Uvicorn with `uvicorn app:app --reload --env-file .env`. Keep `.env` local. The repository has no webhook value, and no live post has been sent.

## Design

See [`DESIGN.md`](DESIGN.md) for the data model, API surface, adapter seam, non-goals, and the external-delivery limitation. Discord messages disable mass mentions. A delivery timeout is marked `uncertain` and is not retried automatically because Discord webhooks do not accept an idempotency key; check the channel before reconciling that record.

## Learning checkpoints

- A **constraint profile** turns a platform's text limits into executable validation.
- An **adapter** lets business logic call one interface while platform-specific code changes independently.
- An **idempotency key** makes a repeated request for the same variant and slot safe.
- A durable schedule stores due work in SQLite so a restarted worker can resume it.
- A dependency lock file records exact package versions so a clean install starts from the same direct and transitive dependencies.

## Acceptance evidence

After starting the service, run `python scripts/acceptance_probe.py` for the API/review/idempotency checks. Run `python scripts/durability_probe.py` for a local restart-recovery simulation and `python scripts/adapter_swap_probe.py` to start the app under a different publisher configuration. Outputs actually observed are recorded in [`EVIDENCE.md`](EVIDENCE.md).

## Known limits

- Variant text comes from deterministic templates, not a generative AI service.
- The live Discord adapter is implemented but remains opt-in. A user-owned webhook is required for an actual public test.
- SQLite enforces one publish per local variant+slot. Discord has no webhook idempotency contract; ambiguous network outcomes are held for manual reconciliation instead of blindly retried.
- URL ingestion rejects local/private destinations and redirects, and caps the fetched response at 1 MB. The accepted host is resolved before the request; this is a learning project, not a hardened general-purpose fetch proxy.
