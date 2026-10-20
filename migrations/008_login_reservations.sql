-- ATD operational extension for A1.24 online_flag/login-in-progress semantics.
-- Access-Request admission and Accounting-Start handoff serialize on a per-user
-- advisory lock; the reservation remains until one matching session is accounted.
CREATE TABLE IF NOT EXISTS atd_radius_login_reservations (
    reservation_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    ras_id INTEGER NOT NULL,
    request_key CHAR(64) NOT NULL UNIQUE,
    username TEXT NOT NULL,
    ras_multi_login_allowed BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS atd_radius_login_reservations_user_idx
    ON atd_radius_login_reservations (user_id, created_at, reservation_id);
CREATE INDEX IF NOT EXISTS atd_radius_login_reservations_ras_idx
    ON atd_radius_login_reservations (user_id, ras_id, created_at, reservation_id);
