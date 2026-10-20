-- ATD operational extension: durable active-session snapshots.
-- Native connection_log remains the historical accounting source; this table
-- preserves runtime-only billing state and sessions for which A1.24 suppresses
-- connection_log history via no_connection_log.
CREATE TABLE IF NOT EXISTS atd_radius_live_sessions (
    user_id BIGINT NOT NULL,
    ras_id INTEGER NOT NULL,
    unique_id TEXT NOT NULL,
    state JSONB NOT NULL CHECK (jsonb_typeof(state) = 'object'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, ras_id, unique_id)
);
CREATE INDEX IF NOT EXISTS atd_radius_live_sessions_user_idx
    ON atd_radius_live_sessions (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS atd_radius_live_sessions_updated_idx
    ON atd_radius_live_sessions (updated_at);
