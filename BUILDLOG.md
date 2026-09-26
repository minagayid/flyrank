# AI build log

## Scope and tools

AI assistance was used to draft the module layout, the deterministic fixture generator, SQLite migration, API routes, test cases, and this documentation. The implementation was reviewed and corrected through local runs. The project uses no external AI provider, and the mock `vision_output` records are not presented as model-generated tags.

## What AI got wrong and what changed

- The first corpus generator built captions by reading three attributes, but the distractor variants intentionally have two. It failed with `IndexError`; the caption builder was changed to join however many attributes a fixture has, then the generator successfully wrote 48 images, 13 posts, and 12 labels.
- The first test run exposed that Python's SQLite connection context manager commits but does not close the connection. Review writes then failed under load and Windows could not clean up the temp database. A closing connection wrapper was added; the suite is now run with `ResourceWarning` treated as an error.
- Review persistence initially declared a composite foreign key to a column tuple that was not uniquely indexed. SQLite rejected the write. The migration now adds a unique `(tenant_id, suggestion_id)` key, and the approval/rejection test exercises the path.
- Code review caught a normalization edge case before it reached the final tests: sequential alias replacements could re-process a canonical phrase such as `red fox`. Normalization now uses a single longest-first regex replacement and an explicit canonical vocabulary.
- A first version of the test assumed the wolf would appear in the ten persisted candidates. Retrieval correctly returns only its highest-ranked slice, so the guard test now forces the wolf directly through the inspection endpoint and separately verifies that a guard-rejected saved candidate cannot be approved.

## Human-owned decisions

- Kept the corpus synthetic and the provider mock to avoid API keys, external uploads, image license ambiguity, and unverified model claims.
- Chose an inspectable 512-dimensional hashing embedder with an explicit alias table. It demonstrates vector ranking and the `Vulpes vulpes` equivalence, but it is not a learned semantic encoder.
- Set local similarity and confidence cutoffs against the included 12-pair fixture evaluation and mismatch probes. The measured 12/12 result is reported with its narrow synthetic scope.
- Bound the server to loopback, scoped every repository query by tenant, and prevented human approval of a rejected suggestion.

## Still outside this build

The source has not been published to a public GitHub repository, no live URL exists, and no real vision provider, authentication, licensed photograph corpus, deployment, or production smoke test was added. Those limitations are stated in README and EVIDENCE.

## 2026-09-26 — reviewer follow-up

- Added sanitized `ALERT` log records for failed jobs, missing job inputs, and retry exhaustion. The alert omits request text and provider response bodies; the stored job error remains available for local inspection.
- Removed the OpenAPI declaration that misrepresented `X-Tenant-ID` as an API key. The document now says that the header selects a partition and provides no authentication.
- Changed the fox/wolf refusal text to identify the animal-category subtype mismatch while retaining both subject names.
- Added an opt-in loopback-only Ollama embedding adapter for `nomic-embed-text`. The deterministic hash embedder remains the offline default and the acceptance suite explicitly selects it.
- On the locally installed Ollama model, the synthetic 48-image/13-post corpus completed 61 embedding requests, with 61/61 job items complete, zero failed items, and observed guarded top-1 precision of 12/12. This result measures text embeddings over synthetic fixture tags/captions; the vision source is still a fixture, not image analysis.
- Captured assertion-backed acceptance output in EVIDENCE.md. No cloud provider, `.env` file, publication, or portal submission was used.

## Packaging checkpoint

- The user authorized a dedicated public GitHub repository and FlyRank submission. The project was built locally before repository creation, so the brief's public-from-day-one and staged-commit sequence was not met. Existing disclosures remain: image tags are fixtures, the corpus is synthetic, and the local embedding evaluation does not prove image analysis or general retrieval quality.
