# Learning notes — explain the build

## What to learn from each layer

- **API boundary:** api.py converts HTTP into typed application actions. Validation errors use clear 4xx responses; exception text and request data are not echoed to callers.
- **Authentication:** security.py stores a salted password hash and a digest of each random bearer token. The client sees the token; SQLite does not store it in plaintext. api.py checks the token before account-owned routes.
- **Persistence:** the SQL migration defines ownership foreign keys, unique idempotency keys, and indexes. Every helper opens its own SQLite connection; short write transactions make job transitions durable.
- **Idempotency:** a repeated Idempotency-Key for the same lead reuses its original job. It avoids scheduling duplicate work when a client retries after losing a response.
- **Background work:** the API commits a queued job and immediately returns 202. The worker claims a row, records attempts, retries transient failures, and saves a terminal result.
- **Grounding and schema checks:** an LLM can return malformed JSON or invent a quote. The adapter output is validated, and each evidence phrase must occur in the original project description.
- **Privacy boundary:** the Ollama adapter only accepts loopback URLs and omits lead name and email from its prompt. This is a local learning boundary, not a production privacy certification.
- **Cache and budget:** a stable hash over input and model version selects a TTL cache. A cache hit avoids another provider call. The Ollama adapter has a per-day call ceiling checked before network I/O.
- **PDF reporting:** the report generator uses stored, account-scoped results and omits names and emails. The compact PDF is written by a small standard-library serializer.

## Explain-back prompts

Before calling the work your own, practice answering these without reading the code:

1. Why does the database store a token digest instead of the bearer token?
2. What exactly makes two triage requests idempotent? What happens if the key changes?
3. Which transaction makes a queued job visible to the worker, and when does the API respond?
4. Why is a result with unsupported evidence rejected even if its JSON shape is valid?
5. What fields form the cache key, and why is model version included?
6. Where is the daily model budget checked? What is recorded when the budget blocks work?
7. Why does a low or high fit score never automatically reject or accept a lead?
8. Which claims in the 10x overview are hypotheses rather than measured user outcomes?

## Honest boundary

The default mock provider is a deterministic fixture, not an LLM. The acceptance probe's fake Ollama server validates the HTTP adapter and usage ledger, not model quality. A real local model should be used only after the learner can explain the prompt, validation, privacy boundary, retry behavior, and limitations.
