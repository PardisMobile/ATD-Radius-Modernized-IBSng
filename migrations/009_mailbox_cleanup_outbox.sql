-- Durable post-commit side effects for A1.24-compatible user deletion.
CREATE TABLE IF NOT EXISTS atd_radius_mailbox_cleanup (
    job_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS atd_radius_mailbox_cleanup_pending_idx
    ON atd_radius_mailbox_cleanup (status, updated_at, job_id)
    WHERE status IN ('pending', 'failed', 'running');
