# Evidence

This file contains observed local acceptance results. It does not claim deployed behavior, real image analysis, external review, or portal acceptance. The vision responses and image references remain synthetic fixtures. The optional embedding run below used the local Ollama `nomic-embed-text` model against synthetic captions and post text.

## Section 6 requirement proofs

| Requirement | Captured proof and status |
|---|---|
| Vision output is schema-validated; invalid output is not trusted | `test_missing_extra_and_bad_confidence_are_rejected ... ok`; printed `ACCEPTANCE_PROOF vision_schema valid=accepted invalid_missing_extra_bool_confidence=3_rejected`. The background job also records and retries the malformed fixture. Schema-boundary behavior is proven; a real vision model is not wired in. |
| Low-confidence classifications are flagged | `ACCEPTANCE_PROOF batch` reports `low_confidence_items: 1` and `low_confidence_image_ids: ["img-strawberry-04"]`; the acceptance assertion checks that image is `review_required`. |
| Images run in a batch with retries | `ACCEPTANCE_PROOF batch` reports `status: completed`, `completed_items: 61`, `failed_items: 0`, `retries: 1`, and `retry_attempts: 2`. |
| Vision and embedding calls have attributed cost rows | `ACCEPTANCE_PROOF batch` reports `vision_calls: 49`, `embedding_calls: 61`, `cost_ledger_rows: 110`, and `cost_usd: 0.0`. Vision calls are mock fixture responses; Ollama embedding calls are local and zero-cost. |
| Budget guard blocks over-budget calls and job failures alert | `test_estimated_cost_over_budget_blocks_the_first_provider_call ... ok`; captured log: `ERROR:image_relevance.jobs:ALERT batch processing failed job_id=job_2e0d9df0f7754d9c target_kind=job error_code=BudgetExceeded`. The same proof reports `job_status: failed`, `failed_items: 1`, and `ledger_calls: 0`. |
| Captions and post text are embedded and ranked | Hash-mode acceptance proof: `red_fox_status: matched`, `red_fox_image: img-red-fox-01`. The Ollama run below persisted both image and post vectors using 768-dimensional model output. |
| Equivalent concepts work | Hash-mode test output: `ACCEPTANCE_PROOF semantic_alias Vulpes_vulpes=red_fox`. The Ollama labeled corpus also scored 12/12, though its fox post includes both the scientific and common names; it is not an isolated synonym test. |
| The fox article rejects a forced wolf with an explanation | Captured: `forced_wolf_status: rejected`; reason: `Animal category mismatch: expected red fox, detected gray wolf (subject mismatch within animal)`. |
| No suitable image returns `no_confident_match` with reasons | Captured: `unsupported_post_status: no_confident_match`; reason: `Similarity 0.046 is below 0.220`. |
| Required database models and indexes exist | `ACCEPTANCE_PROOF batch` lists tables `cost_ledger`, `image_embeddings`, `image_tags`, `post_embeddings`, `reviews`, `suggestions`; indexes `idx_cost_tenant_created`, `idx_images_tenant_status`, `idx_suggestions_tenant_post`. |
| API boundaries return clean errors | `ACCEPTANCE_PROOF boundaries` reports missing key `idempotency_key_required`, non-object JSON `invalid_body`, and invalid review action `invalid_review`; these acceptance assertions verify HTTP 400. |
| Review supports approve/reject, idempotency, and the mismatch guard | `ACCEPTANCE_PROOF review` reports suggestion create 201/replay 200, approval `approve`, review replay 200, and rejected-candidate approval 409. |
| Batch persistence, restart recovery, and idempotency are safe | Batch replay returned 200 with the original job. `ACCEPTANCE_PROOF restart` reports `status: completed`, `completed_items: 2`, `retries: 1`, `image_attempts: 2`, and `ledger_calls: 4`. |
| Tenant partitions are isolated at the data-query layer | `ACCEPTANCE_PROOF boundaries` reports 404 for another tenant's post and job. `X-Tenant-ID` is a partition selector, not authentication. |
| Labeled evaluation measures top-1 precision | Hash fixtures: `12/12 = 1.000`. The actual local Ollama evaluation transcript below also reports all 12 labeled pairs correct. Both scores are limited to this curated synthetic corpus. |
| README, architecture, and submission files are present | Read-only pack check output: `README.md=True`, `capstone.yaml=True`, `EVIDENCE.md=True`, `BUILDLOG.md=True`, `.env.example=True`, `.gitignore=True`, `LICENSE=True`, `DESIGN.md=True`. |

## Existing acceptance suite — observed output

Command: `python -W error::ResourceWarning -m unittest discover -s tests -v`

```text
test_background_job_retries_flags_and_tracks_every_call (test_acceptance.AcceptanceProbeTests.test_background_job_retries_flags_and_tracks_every_call) ... ok
test_eval_precision_and_semantic_alias (test_acceptance.AcceptanceProbeTests.test_eval_precision_and_semantic_alias) ... ok
test_guard_refuses_forced_wolf_and_unknown_post (test_acceptance.AcceptanceProbeTests.test_guard_refuses_forced_wolf_and_unknown_post) ... ok
test_input_errors_and_tenant_isolation_are_clean (test_acceptance.AcceptanceProbeTests.test_input_errors_and_tenant_isolation_are_clean) ... ok
test_review_flow_is_idempotent_and_guarded (test_acceptance.AcceptanceProbeTests.test_review_flow_is_idempotent_and_guarded) ... ok
test_estimated_cost_over_budget_blocks_the_first_provider_call (test_budget.BudgetGuardTests.test_estimated_cost_over_budget_blocks_the_first_provider_call) ... ok
test_running_job_resumes_from_persisted_attempt_count (test_restart.RestartRecoveryTests.test_running_job_resumes_from_persisted_attempt_count) ... ok
test_fixture_corpus_is_bounded_and_labeled (test_schema.VisionSchemaTests.test_fixture_corpus_is_bounded_and_labeled) ... ok
test_known_equivalent_concept_maps_to_canonical_subject (test_schema.VisionSchemaTests.test_known_equivalent_concept_maps_to_canonical_subject) ... ok
test_missing_extra_and_bad_confidence_are_rejected (test_schema.VisionSchemaTests.test_missing_extra_and_bad_confidence_are_rejected) ... ok
test_valid_output_is_typed (test_schema.VisionSchemaTests.test_valid_output_is_typed) ... ok

----------------------------------------------------------------------
Ran 11 tests in 8.270s

OK
ACCEPTANCE_PROOF batch {"completed_items": 61, "cost_ledger_rows": 110, "cost_usd": 0.0, "embedding_calls": 61, "failed_items": 0, "idempotent_replay_status": 200, "image_count": 48, "low_confidence_image_ids": ["img-strawberry-04"], "low_confidence_items": 1, "required_indexes_present": ["idx_cost_tenant_created", "idx_images_tenant_status", "idx_suggestions_tenant_post"], "required_tables_present": ["cost_ledger", "image_embeddings", "image_tags", "post_embeddings", "reviews", "suggestions"], "retries": 1, "retry_attempts": 2, "retry_error_history": "[\"missing required fields: caption\"]", "status": "completed", "vision_calls": 49}
ACCEPTANCE_PROOF matching {"alias": "Vulpes vulpes -> red fox", "red_fox_image": "img-red-fox-01", "red_fox_status": "matched", "top1_correct": "12/12 = 1.000"}
ACCEPTANCE_PROOF mismatch_guard {"forced_wolf_reason": ["Animal category mismatch: expected red fox, detected gray wolf (subject mismatch within animal)", "Similarity 0.000 is below 0.220"], "forced_wolf_status": "rejected", "unsupported_post_reasons": ["Similarity 0.046 is below 0.220"], "unsupported_post_status": "no_confident_match"}
ACCEPTANCE_PROOF boundaries {"cross_tenant_job_status": 404, "cross_tenant_post_error": "post_not_found", "cross_tenant_post_status": 404, "invalid_action": "invalid_review", "missing_idempotency_key": "idempotency_key_required", "non_object_json": "invalid_body", "openapi_auth_security_declared": false, "tenant_header_is_auth": false}
ACCEPTANCE_PROOF review {"rejected_candidate_approval": 409, "review_action": "approve", "review_replay": 200, "suggestion_create": 201, "suggestion_replay": 200}
ACCEPTANCE_PROOF budget_failure {"alert": "ERROR:image_relevance.jobs:ALERT batch processing failed job_id=job_2e0d9df0f7754d9c target_kind=job error_code=BudgetExceeded", "failed_items": 1, "job_status": "failed", "ledger_calls": 0}
ACCEPTANCE_PROOF restart {"completed_items": 2, "image_attempts": 2, "ledger_calls": 4, "retries": 1, "status": "completed"}
ACCEPTANCE_PROOF corpus images=48 categories=4 posts=13 labeled_pairs=12
ACCEPTANCE_PROOF semantic_alias Vulpes_vulpes=red_fox
ACCEPTANCE_PROOF vision_schema valid=accepted invalid_missing_extra_bool_confidence=3_rejected
```

## Local Ollama embedding evaluation — observed output

Ollama's local `/api/tags` response listed `nomic-embed-text:latest` at 274,302,450 bytes. The project adapter sent requests only to `http://127.0.0.1:11434`; the run used a temporary SQLite database, did not call a cloud API, and did not inspect or use a `.env` file. The corpus tags were still the fixed mock vision fixtures.

```json
{
  "provider": "ollama",
  "model": "nomic-embed-text",
  "job_status": "completed",
  "completed_items": 61,
  "failed_items": 0,
  "retries": 1,
  "embedding_calls": 61,
  "embedding_cost_usd": 0.0,
  "image_vector_dimensions": 768,
  "guarded_top1": "12/12 = 1.000",
  "labeled_outcomes": [
    {"post_id": "post-red-fox", "predicted": "img-red-fox-01", "expected": "img-red-fox-01", "correct": true},
    {"post_id": "post-gray-wolf", "predicted": "img-gray-wolf-01", "expected": "img-gray-wolf-01", "correct": true},
    {"post_id": "post-domestic-dog", "predicted": "img-domestic-dog-01", "expected": "img-domestic-dog-01", "correct": true},
    {"post_id": "post-bear", "predicted": "img-bear-01", "expected": "img-bear-01", "correct": true},
    {"post_id": "post-deer", "predicted": "img-deer-01", "expected": "img-deer-01", "correct": true},
    {"post_id": "post-barn-owl", "predicted": "img-barn-owl-01", "expected": "img-barn-owl-01", "correct": true},
    {"post_id": "post-apple", "predicted": "img-apple-01", "expected": "img-apple-01", "correct": true},
    {"post_id": "post-strawberry", "predicted": "img-strawberry-01", "expected": "img-strawberry-01", "correct": true},
    {"post_id": "post-sourdough", "predicted": "img-sourdough-bread-01", "expected": "img-sourdough-bread-01", "correct": true},
    {"post_id": "post-sunflower", "predicted": "img-sunflower-01", "expected": "img-sunflower-01", "correct": true},
    {"post_id": "post-oak", "predicted": "img-oak-tree-01", "expected": "img-oak-tree-01", "correct": true},
    {"post_id": "post-eiffel", "predicted": "img-eiffel-tower-01", "expected": "img-eiffel-tower-01", "correct": true}
  ],
  "ledger_calls": 110
}
```

## Remaining limitations

- The 48 corpus entries are metadata fixtures with `mock://` references, not 48 real licensed images. The vision pipeline validates fixture JSON; it does not send image pixels to a vision model.
- The Ollama result measures embeddings of synthetic captions and post text, not visual understanding or out-of-sample accuracy. The 12/12 score is limited to these curated pairs.
- The public dedicated GitHub repository and public commit history required by the brief have not been created. Nothing has been published or submitted.
- The service remains a loopback demo. `X-Tenant-ID` is not authentication, and there is no public deployment or production URL smoke test.
