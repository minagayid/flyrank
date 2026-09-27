DROP INDEX IF EXISTS idx_usage_tenant_period_type;
DROP INDEX IF EXISTS idx_usage_tenant_idempotency;

ALTER TABLE usage_events RENAME TO usage_events_v1;

CREATE TABLE usage_events (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL CHECK (event_type IN ('api_calls', 'ai_tokens', 'billable_action')),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  api_call_quantity INTEGER NOT NULL DEFAULT 0 CHECK (api_call_quantity >= 0),
  input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
  cached_input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (cached_input_tokens >= 0),
  output_tokens INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
  reasoning_tokens INTEGER NOT NULL DEFAULT 0 CHECK (reasoning_tokens >= 0),
  cost_microcents INTEGER NOT NULL CHECK (cost_microcents >= 0),
  api_call_cost_microcents INTEGER NOT NULL DEFAULT 0 CHECK (api_call_cost_microcents >= 0),
  token_cost_microcents INTEGER NOT NULL DEFAULT 0 CHECK (token_cost_microcents >= 0),
  idempotency_key TEXT NOT NULL,
  period TEXT NOT NULL CHECK (length(period) = 7),
  occurred_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);

INSERT INTO usage_events(
  id, tenant_id, event_type, quantity, api_call_quantity,
  input_tokens, cached_input_tokens, output_tokens, reasoning_tokens,
  cost_microcents, api_call_cost_microcents, token_cost_microcents,
  idempotency_key, period, occurred_at, metadata_json
)
SELECT
  id, tenant_id, event_type, quantity,
  CASE WHEN event_type='api_calls' THEN quantity ELSE 0 END,
  input_tokens, cached_input_tokens, output_tokens, reasoning_tokens,
  cost_microcents,
  CASE WHEN event_type='api_calls' THEN cost_microcents ELSE 0 END,
  CASE WHEN event_type='ai_tokens' THEN cost_microcents ELSE 0 END,
  idempotency_key, period, occurred_at, metadata_json
FROM usage_events_v1;

DROP TABLE usage_events_v1;

CREATE INDEX idx_usage_tenant_period_type ON usage_events(tenant_id, period, event_type);
CREATE INDEX idx_usage_tenant_idempotency ON usage_events(tenant_id, idempotency_key);
