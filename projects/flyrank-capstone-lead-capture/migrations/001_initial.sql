CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_tokens (
    token_hash TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_api_tokens_tenant ON api_tokens(tenant_id);

CREATE TABLE IF NOT EXISTS widgets (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('signup', 'contact', 'cta')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    fields_json TEXT NOT NULL,
    button_text TEXT NOT NULL,
    display_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_widgets_tenant_updated ON widgets(tenant_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    widget_id TEXT NOT NULL REFERENCES widgets(id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    fields_json TEXT NOT NULL,
    origin TEXT,
    ip_digest TEXT NOT NULL,
    country TEXT,
    country_code TEXT,
    city TEXT,
    geo_provider TEXT,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_submissions_idempotency
    ON submissions(tenant_id, widget_id, idempotency_key);
CREATE INDEX IF NOT EXISTS idx_submissions_tenant_created
    ON submissions(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_submissions_widget_created
    ON submissions(widget_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_submissions_tenant_country
    ON submissions(tenant_id, country);

CREATE TABLE IF NOT EXISTS notification_jobs (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    submission_id TEXT NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    dedupe_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'processing', 'sent', 'dead')),
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at REAL NOT NULL,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notification_jobs_ready
    ON notification_jobs(status, available_at);

INSERT OR IGNORE INTO schema_migrations(version, applied_at)
VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
