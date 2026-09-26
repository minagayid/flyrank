# Design — Image Relevance & Auto-Tagging

## Problem

Given a small image library and blog posts, suggest images by meaning and reject unsafe or weak matches. A wolf should never be recommended for a red-fox article merely because both descriptions mention wildlife or forest.

## Data model

All records are scoped by `tenant_id`. Images have a source reference, untrusted mock vision fixture, validated tag payload, confidence/review state, and one vector. Posts have title/body and one vector. Jobs and job items record asynchronous progress, attempts and failures. The cost ledger records every vision/embedding call. Suggestion runs persist ranked decisions; review rows store approve/reject actions and an idempotency key.

## API surface

`POST /jobs` starts the bounded batch with an idempotency key. `GET /jobs/{id}` exposes progress, retries, failure state and costs. `GET /posts/{id}/images` returns a ranked confident suggestion or an explicit no-match explanation; `candidate_id` forces one image through the guard for inspection. `POST /posts/{id}/suggestions` persists a run. `POST /suggestions/{id}/review` stores a human decision; guard-rejected candidates cannot be approved.

## Layers

```text
HTTP boundary → application/service logic → domain validation + matching → tenant-scoped SQLite repository
                         │
                         └── background job runner → fixture vision / local embedding adapters
```

Each JSON input is checked before it reaches the service. Vision results pass a strict schema validator before persistence. Similarity uses normalized alias, token, bigram, and subject-phrase features hashed into 512 dimensions. The guard checks schema, known subject, inferred category, confidence, and a tuned similarity floor independently of rank.

## Failure and cost policy

Invalid vision output is recorded as a failed attempt and retried up to the configured retry count. Persistent per-item failure is visible in job state; successful low-confidence output remains available for review but cannot pass the guard. Job progress is persisted item-by-item and incomplete work resumes after restart. Each model-like call has provider, model, item, attempt and cost fields. The local mock provider quotes zero dollars, and a per-job budget check blocks a call whose estimate would exceed the configured limit.

## Evaluation and non-goal

The committed synthetic corpus contains 48 images in four categories, 13 posts, 12 exact-image labels, a forced fox/wolf probe, a no-match probe, a transient schema failure, and one low-confidence tag. The measured top-1 score is reported in README and EVIDENCE. The non-goal is a real vision product: this build does not fetch licensed photographs, call a cloud/local vision model, or claim general semantic retrieval quality.
