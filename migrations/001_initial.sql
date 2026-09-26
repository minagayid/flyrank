CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE leads (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    project_description TEXT NOT NULL,
    budget_range TEXT NOT NULL DEFAULT '',
    timeline TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE triage_jobs (
    id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts > 0),
    next_run_at TEXT NOT NULL,
    result_json TEXT,
    error_code TEXT,
    cache_hit INTEGER NOT NULL DEFAULT 0 CHECK (cache_hit IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, lead_id, idempotency_key)
);

CREATE TABLE triage_results (
    lead_id TEXT PRIMARY KEY REFERENCES leads(id) ON DELETE CASCADE,
    source_job_id TEXT NOT NULL REFERENCES triage_jobs(id),
    result_json TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    cache_hit INTEGER NOT NULL DEFAULT 0 CHECK (cache_hit IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE triage_cache (
    cache_key TEXT PRIMARY KEY,
    result_json TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE ai_call_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lead_id TEXT NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0 CHECK (prompt_tokens >= 0),
    completion_tokens INTEGER NOT NULL DEFAULT 0 CHECK (completion_tokens >= 0),
    cost_microusd INTEGER NOT NULL DEFAULT 0 CHECK (cost_microusd >= 0),
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_sessions_user_expiry ON sessions(user_id, expires_at);
CREATE INDEX idx_leads_owner_created ON leads(user_id, created_at);
CREATE INDEX idx_jobs_status_next_run ON triage_jobs(status, next_run_at);
CREATE INDEX idx_jobs_owner_created ON triage_jobs(user_id, created_at);
CREATE INDEX idx_ai_ledger_owner_day ON ai_call_ledger(user_id, created_at);
