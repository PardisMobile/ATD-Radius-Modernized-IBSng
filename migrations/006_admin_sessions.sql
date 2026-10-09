-- ATD extension: revocable server-side admin sessions.
-- Only a SHA-256 digest of the random bearer secret is stored.
CREATE TABLE IF NOT EXISTS admin_sessions (
    session_id BIGSERIAL PRIMARY KEY,
    admin_id INTEGER NOT NULL REFERENCES admins(admin_id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    remote_addr INET,
    CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS admin_sessions_admin_active_idx
    ON admin_sessions (admin_id, expires_at DESC)
    WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS admin_sessions_expiry_idx
    ON admin_sessions (expires_at)
    WHERE revoked_at IS NULL;
