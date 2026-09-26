# Learning notes

Use this page to explain the design in your own words before calling the project finished.

## 1. Validate model output at the boundary

The vision fixture is untrusted JSON. `schema.py` checks required fields, rejects extras and wrong types, and bounds confidence and text length before anything is stored. A confidence score below `0.70` is retained for review but cannot pass the recommendation guard. This separates “the model returned something” from “the application may rely on it.”

## 2. Compare meaning with vectors, then apply rules

`embeddings.py` turns captions and posts into normalized 512-number vectors. Cosine similarity ranks candidates. The local demo maps the declared alias `Vulpes vulpes` to `red fox`, then uses weighted words, adjacent pairs, and known subject phrases. `matching.py` applies separate subject, category, confidence, and similarity checks after ranking. The guard can reject the highest-scoring image; similarity alone is not a safety decision.

## 3. Keep slow work off the request path

`POST /jobs` stores a job and returns while a worker handles images and posts. Each item has a durable state, attempt count, error history, and completion status. The job exposes totals and percentage so a caller can poll without waiting for all work. An idempotency key prevents a retried request from creating duplicate work, and incomplete items resume after a process restart.

## 4. Attribute cost and enforce a budget

Each mock vision or embedding call writes one cost-ledger row with its provider, model, target, attempt and amount. The demo costs zero, but the worker checks an estimate against the job budget before making a call. `test_budget.py` injects a non-zero estimate to prove that over-budget work stops before a call is logged.

## 5. Measure a decision system with labeled examples

`fixtures/eval.json` labels the one correct image for each of 12 posts. Top-1 precision is correct first accepted recommendations divided by labeled posts. It measures this curated fixture corpus only; it does not prove general vision quality. The separate probes ask whether a fox/wolf mismatch and an unsupported article are refused.

## 6. Treat tenant scope and review as application rules

Repository queries include `tenant_id`, and the API returns 404 when a record belongs to another tenant. The header is only a partition key, not authentication. Suggestions preserve the guard decision; reviewers can approve a passing pairing or reject it, but cannot approve a guard-rejected candidate.

## Try these changes

- Add an alias for a new scientific/common-name pair and a labeled post; rerun the evaluation.
- Raise the similarity threshold and note which candidates become “no confident match.”
- Remove a required key from a mock vision response and inspect the job retry and cost ledger.
- Increase the injected provider estimate above the budget and explain why no call row was written.
- Explain why 12/12 on these synthetic labels is not evidence of 100% accuracy on real photographs.
