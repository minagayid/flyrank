CREATE TABLE tenants (
    tenant_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL
);

CREATE TABLE images (
    tenant_id TEXT NOT NULL,
    image_id TEXT NOT NULL,
    reference TEXT NOT NULL,
    fixture_json TEXT NOT NULL,
    invalid_first_attempts INTEGER NOT NULL DEFAULT 0,
    tag_status TEXT NOT NULL DEFAULT 'queued' CHECK (tag_status IN ('queued','ready','review_required','failed')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, image_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);
CREATE INDEX idx_images_tenant_status ON images(tenant_id, tag_status, image_id);

CREATE TABLE image_tags (
    tenant_id TEXT NOT NULL,
    image_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    review_required INTEGER NOT NULL CHECK (review_required IN (0,1)),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, image_id),
    FOREIGN KEY (tenant_id, image_id) REFERENCES images(tenant_id, image_id) ON DELETE CASCADE
);
CREATE INDEX idx_image_tags_review ON image_tags(tenant_id, review_required, confidence);

CREATE TABLE image_embeddings (
    tenant_id TEXT NOT NULL,
    image_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    vector_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, image_id),
    FOREIGN KEY (tenant_id, image_id) REFERENCES images(tenant_id, image_id) ON DELETE CASCADE
);

CREATE TABLE posts (
    tenant_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, post_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);
CREATE INDEX idx_posts_tenant_title ON posts(tenant_id, title);

CREATE TABLE post_embeddings (
    tenant_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    vector_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, post_id),
    FOREIGN KEY (tenant_id, post_id) REFERENCES posts(tenant_id, post_id) ON DELETE CASCADE
);

CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','running','completed','completed_with_warnings','failed')),
    total_items INTEGER NOT NULL,
    completed_items INTEGER NOT NULL DEFAULT 0,
    failed_items INTEGER NOT NULL DEFAULT 0,
    retries INTEGER NOT NULL DEFAULT 0,
    low_confidence_items INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    UNIQUE (tenant_id, idempotency_key),
    UNIQUE (tenant_id, job_id),
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);
CREATE INDEX idx_jobs_tenant_status ON jobs(tenant_id, status, created_at DESC);

CREATE TABLE job_items (
    tenant_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('image','post')),
    target_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','running','completed','failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    error_history_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, job_id, target_kind, target_id),
    FOREIGN KEY (tenant_id, job_id) REFERENCES jobs(tenant_id, job_id) ON DELETE CASCADE
);
CREATE INDEX idx_job_items_status ON job_items(tenant_id, job_id, status);

CREATE TABLE cost_ledger (
    call_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    job_id TEXT NOT NULL,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('image','post')),
    target_id TEXT NOT NULL,
    call_kind TEXT NOT NULL CHECK (call_kind IN ('vision','embedding')),
    provider TEXT NOT NULL,
    model_id TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    units INTEGER NOT NULL DEFAULT 1,
    cost_usd REAL NOT NULL CHECK (cost_usd >= 0),
    created_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id, job_id) REFERENCES jobs(tenant_id, job_id) ON DELETE CASCADE
);
CREATE INDEX idx_cost_tenant_created ON cost_ledger(tenant_id, created_at DESC);
CREATE INDEX idx_cost_job_kind ON cost_ledger(tenant_id, job_id, call_kind);

CREATE TABLE suggestion_runs (
    run_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, idempotency_key),
    UNIQUE (tenant_id, run_id),
    FOREIGN KEY (tenant_id, post_id) REFERENCES posts(tenant_id, post_id) ON DELETE CASCADE
);
CREATE TABLE suggestions (
    suggestion_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    post_id TEXT NOT NULL,
    image_id TEXT NOT NULL,
    similarity REAL NOT NULL,
    accepted INTEGER NOT NULL CHECK (accepted IN (0,1)),
    reasons_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, run_id, image_id),
    UNIQUE (tenant_id, suggestion_id),
    FOREIGN KEY (tenant_id, run_id) REFERENCES suggestion_runs(tenant_id, run_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, post_id) REFERENCES posts(tenant_id, post_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, image_id) REFERENCES images(tenant_id, image_id) ON DELETE CASCADE
);
CREATE INDEX idx_suggestions_tenant_post ON suggestions(tenant_id, post_id, created_at DESC);

CREATE TABLE reviews (
    review_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    suggestion_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('approve','reject')),
    note TEXT NOT NULL DEFAULT '',
    idempotency_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (tenant_id, idempotency_key),
    FOREIGN KEY (tenant_id, suggestion_id) REFERENCES suggestions(tenant_id, suggestion_id) ON DELETE CASCADE
);
CREATE INDEX idx_reviews_tenant_suggestion ON reviews(tenant_id, suggestion_id, created_at DESC);
