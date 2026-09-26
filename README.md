# Image Relevance & Auto-Tagging

A small backend reference project for matching a blog post to a suitable image while refusing unsafe matches. The API is runnable locally with Python’s standard library; it needs no API key, account, database server, or third-party package.

**Demo scope:** 48 synthetic image metadata fixtures across four categories, 13 posts, and 12 labeled post-to-image pairs. The image references use `mock://` URIs: there are no real photos. A mock vision provider returns schema-checked fixtures. The default deterministic hash embedder keeps tests offline; an optional local Ollama adapter uses `nomic-embed-text` for semantic embeddings. The fixture vision provider is not a live vision product.

## Run it

Use Python 3.11 or later. The project was verified with CPython 3.14.6. From this directory:

```text
python -m image_relevance.seed
python -m image_relevance.api
```

The service listens on `http://127.0.0.1:8000` and creates `var/image_relevance.sqlite3`. In another terminal, start the asynchronous batch with a stable idempotency key:

```powershell
curl.exe -X POST http://127.0.0.1:8000/jobs `
  -H "Content-Type: application/json" `
  -H "Idempotency-Key: demo-batch-1" `
  -d '{"kind":"process-corpus"}'
```

Poll the returned job ID until `status` is `completed`:

```text
curl.exe http://127.0.0.1:8000/jobs/JOB_ID
```

Then run the labeled evaluation from the project directory:

```text
python -m image_relevance.evaluate
```

Expected demo result: `Guarded top-1 precision: 12/12 = 1.000`. This is a score on the synthetic fixture set, not an estimate of real-world vision or retrieval quality.

Run the tests:

```text
python -m unittest discover -s tests -v
```

`requirements.txt` is intentionally empty: all runtime and test code uses the Python standard library. `.env.example` documents the supported environment variables; export them in the process environment if you want to change defaults. No `.env` or secret is needed.

## Optional local Ollama embeddings

The default `EMBEDDING_PROVIDER=hash` makes the seed, tests, and demo work without a model server. To use the local `nomic-embed-text` model, install Ollama, pull the model, and point the app at Ollama's loopback HTTP endpoint:

```powershell
ollama pull nomic-embed-text
$env:EMBEDDING_PROVIDER = "ollama"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
$env:DATABASE_PATH = "var/image_relevance_ollama.sqlite3"
python -m image_relevance.seed
python -m image_relevance.api
```

In another terminal, submit the batch and run `python -m image_relevance.evaluate` as shown above. Use a fresh database path when changing embedding models so stored image and post vectors use the same model. `OLLAMA_BASE_URL` accepts only plain HTTP loopback addresses (`127.0.0.1`, `localhost`, or `::1`); the adapter has a request timeout and response-size limit. The Ollama provider makes no cloud calls and requires no API key. Vision tags remain deterministic fixtures, so this option evaluates real local text embeddings over synthetic captions and posts, not image pixels.

## Architecture

```text
                         ┌──────────────────────────────┐
POST /jobs ─────────────▶│ Threaded batch worker        │
                         │ validate mock vision output  │
                         │ retry → embed → log each call│
                         └───────────┬──────────────────┘
                                     │
                  ┌──────────────────▼─────────────────┐
                  │ SQLite repository + migrations      │
                  │ tenant-scoped tags, vectors, jobs,  │
                  │ cost ledger, suggestions, reviews   │
                  └──────────────────┬─────────────────┘
                                     │
GET /posts/{id}/images ──▶ vector ranking ──▶ mismatch guard
                                     │                 ├─ confident suggestion
                                     │                 └─ refusal + reasons
                                     ▼
                         POST review: approve / reject
```

The layers are separated into HTTP (`image_relevance/api.py`), application decisions (`service.py`, `matching.py`, `jobs.py`), persistence (`repository.py`, `database.py`), and schema/embedding logic (`schema.py`, `embeddings.py`). SQLite migrations and indexes are in `migrations/`.

## Match safety

The default query and candidate vectors use deterministic 512-dimensional feature hashing; the optional Ollama mode uses `nomic-embed-text` vectors. The hash embedder normalizes a small declared alias list—such as `Vulpes vulpes` → `red fox`—then hashes weighted words, adjacent word pairs, and known subject phrases. The decision guard independently validates the tags and checks known subject, category, confidence, and similarity. A strong similarity score cannot override a fox/wolf subject mismatch.

The default cutoffs are `SIMILARITY_THRESHOLD=0.22` and `CONFIDENCE_THRESHOLD=0.70`. They are explicit demo settings chosen against the included synthetic evaluation corpus. Change them only with a re-run of the labeled evaluation and adversarial probes.

## API

All data routes are scoped by `X-Tenant-ID` (default `demo`). This header selects a data partition; **it is not authentication or authorization**. The server binds to loopback by default. Do not expose this sample service to the public internet.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/openapi.json` | Compact OpenAPI route inventory |
| `GET` | `/images` or `/images/{image_id}` | Inspect tags, state, and confidence flag |
| `GET` | `/posts` | List posts and embedding state |
| `POST` | `/jobs` | Start the asynchronous corpus job; requires `Idempotency-Key` and `{"kind":"process-corpus"}` |
| `GET` | `/jobs` or `/jobs/{job_id}` | Inspect state, progress, retries, failures, and costs |
| `GET` | `/costs` | Read per-call ledger entries and total cost |
| `GET` | `/posts/{post_id}/images` | Return ranked candidates, a safe match, or `no_confident_match` |
| `GET` | `/posts/{post_id}/images?candidate_id=img-gray-wolf-01` | Force-inspect a candidate through the same guard |
| `POST` | `/posts/{post_id}/suggestions` | Persist a ranked suggestion run; requires `Idempotency-Key` |
| `GET` | `/posts/{post_id}/suggestions` | Inspect saved decisions |
| `GET` | `/suggestions/{suggestion_id}` | Inspect one pairing and its review history |
| `POST` | `/suggestions/{suggestion_id}/review` | Approve or reject; requires an idempotency key |

Bad JSON, wrong content types, invalid actions, and malformed tenant or idempotency headers return a 4xx response with a stable error code. An item rejected by the guard cannot be approved through the review endpoint.

## Storage and resilience

The first migration creates tenant-scoped image/post metadata, schema-validated tags, image/post vectors, batch jobs and items, a per-call cost ledger, suggestion runs, suggestions, and reviews. Indexes cover tenant/status job queries, tag review flags, cost history, and post suggestions. SQLite foreign keys and `X-Tenant-ID` filters keep demo records separated.

The corpus batch runs on a background thread. Its one deliberately malformed mock vision response is rejected by the validator, recorded, and retried; one valid low-confidence tag is stored as `review_required`. Job progress counts completed and failed items. Every fixture vision attempt and embedding request gets an attributed cost row before the call; both local embedding options report `$0.00` per call. The configured budget check runs before each call. Exhausted retries and fatal job failures emit a sanitized `ALERT` log line without request text or provider response bodies.

The batch endpoint is idempotent: repeating a request with the same tenant and key returns the existing job. Suggestion runs and reviews use the same pattern. SQLite data survives process restarts; pending/running job items resume when the service starts again.

## Evaluation and limitations

`fixtures/eval.json` has 12 labeled exact-image pairs and three named probes: a forced wolf candidate for a fox article, an unsupported no-match post, and a low-confidence image. Tests verify the synonym case, top-1 result, refusal explanations, schema retry, progress, cost attribution, review idempotency, boundary errors, tenant isolation, migrations, and indexes.

The observed optional Ollama run scored `12/12 = 1.000` on the same 12 synthetic labels; the full run output is in EVIDENCE.md. This does not establish general semantic quality: the corpus is small, synthetic, and curated. There is no real photo ingestion or vision model, authentication, public deployment, or live endpoint. `X-Tenant-ID` only selects a data partition and is not an authentication boundary; the service must stay on loopback unless authenticated tenant identity is added. A production system needs licensed images, a real vision model, authenticated tenant identity, and a deployment smoke test before making recommendations.

## Capstone pack

- [Design](DESIGN.md)
- [Evidence](EVIDENCE.md)
- [AI build log](BUILDLOG.md)
- [Learning notes](LEARNING_NOTES.md)
- [Manifest](capstone.yaml)
- [Schema](schemas/vision-output.schema.json)
- [Synthetic corpus generator](fixtures/build_fixtures.py)
