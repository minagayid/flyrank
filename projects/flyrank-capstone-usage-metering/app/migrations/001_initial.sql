CREATE TABLE tenants (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  api_key_hash TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE plans (
  id TEXT PRIMARY KEY CHECK (id IN ('free', 'pro')),
  name TEXT NOT NULL,
  api_calls_limit INTEGER NOT NULL CHECK (api_calls_limit >= 0),
  ai_tokens_limit INTEGER NOT NULL CHECK (ai_tokens_limit >= 0),
  monthly_price_cents INTEGER NOT NULL CHECK (monthly_price_cents >= 0),
  api_call_microcents INTEGER NOT NULL CHECK (api_call_microcents >= 0),
  input_microcents_per_token INTEGER NOT NULL CHECK (input_microcents_per_token >= 0),
  cached_input_microcents_per_token INTEGER NOT NULL CHECK (cached_input_microcents_per_token >= 0),
  output_microcents_per_token INTEGER NOT NULL CHECK (output_microcents_per_token >= 0),
  reasoning_microcents_per_token INTEGER NOT NULL CHECK (reasoning_microcents_per_token >= 0),
  updated_at TEXT NOT NULL
);

CREATE TABLE subscriptions (
  tenant_id TEXT PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
  plan_id TEXT NOT NULL REFERENCES plans(id),
  status TEXT NOT NULL CHECK (status IN ('active', 'past_due', 'canceled', 'incomplete')),
  stripe_customer_id TEXT,
  stripe_subscription_id TEXT,
  updated_at TEXT NOT NULL
);

CREATE TABLE idempotency_records (
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  http_status INTEGER NOT NULL,
  response_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, idempotency_key)
);

CREATE TABLE usage_events (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL CHECK (event_type IN ('api_calls', 'ai_tokens')),
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
  cached_input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (cached_input_tokens >= 0),
  output_tokens INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
  reasoning_tokens INTEGER NOT NULL DEFAULT 0 CHECK (reasoning_tokens >= 0),
  cost_microcents INTEGER NOT NULL CHECK (cost_microcents >= 0),
  idempotency_key TEXT NOT NULL,
  period TEXT NOT NULL CHECK (length(period) = 7),
  occurred_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);

CREATE TABLE stripe_events (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  tenant_id TEXT REFERENCES tenants(id) ON DELETE SET NULL,
  processed_at TEXT NOT NULL,
  result_json TEXT NOT NULL
);

CREATE TABLE checkout_sessions (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  plan_id TEXT NOT NULL REFERENCES plans(id),
  provider TEXT NOT NULL CHECK (provider IN ('mock', 'stripe_test')),
  provider_session_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('open', 'completed', 'expired')),
  checkout_url TEXT NOT NULL,
  created_at TEXT NOT NULL,
  completed_at TEXT
);

CREATE TABLE invoice_summaries (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  period TEXT NOT NULL CHECK (length(period) = 7),
  summary_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (tenant_id, period)
);

CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind = 'invoice_summary'),
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  period TEXT NOT NULL CHECK (length(period) = 7),
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'retry', 'completed', 'failed')),
  attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
  next_attempt_at TEXT NOT NULL,
  lease_until TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE ops_alerts (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  level TEXT NOT NULL CHECK (level IN ('warning', 'critical')),
  message TEXT NOT NULL,
  created_at TEXT NOT NULL,
  acknowledged_at TEXT
);

CREATE INDEX idx_usage_tenant_period_type ON usage_events(tenant_id, period, event_type);
CREATE INDEX idx_usage_tenant_idempotency ON usage_events(tenant_id, idempotency_key);
CREATE INDEX idx_idempotency_created_at ON idempotency_records(created_at);
CREATE INDEX idx_stripe_events_tenant ON stripe_events(tenant_id, processed_at);
CREATE INDEX idx_jobs_due ON jobs(status, next_attempt_at, created_at);
CREATE INDEX idx_alerts_unacknowledged ON ops_alerts(acknowledged_at, created_at);
