-- ATD extension: durable operational events, separate from A1.24 user_audit_log.
-- The native user_audit_log is an attribute-change log and is not a generic event journal.
CREATE TABLE IF NOT EXISTS operational_audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actor_admin_id INTEGER NOT NULL,
    actor_username TEXT NOT NULL,
    action TEXT NOT NULL CHECK (length(action) BETWEEN 1 AND 160),
    outcome TEXT NOT NULL CHECK (outcome IN ('success', 'denied', 'failed')),
    target_type TEXT CHECK (target_type IS NULL OR length(target_type) <= 80),
    target_id TEXT CHECK (target_id IS NULL OR length(target_id) <= 255),
    remote_addr INET,
    request_id TEXT CHECK (request_id IS NULL OR length(request_id) <= 128),
    details JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object')
);

CREATE INDEX IF NOT EXISTS operational_audit_events_time_idx
    ON operational_audit_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS operational_audit_events_actor_time_idx
    ON operational_audit_events (actor_admin_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS operational_audit_events_action_time_idx
    ON operational_audit_events (action, occurred_at DESC);
