-- Durable cross-worker ownership for A1.24 per-user assign_ip.
CREATE TABLE IF NOT EXISTS atd_radius_user_assigned_ip_leases (
 lease_id BIGSERIAL PRIMARY KEY,
 user_id BIGINT NOT NULL,
 ip_address INET NOT NULL,
 status TEXT NOT NULL CHECK (status IN ('pending','active')),
 request_key CHAR(64), ras_id INTEGER, session_id TEXT,
 created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT atd_radius_user_assigned_ip_request_unique UNIQUE (request_key),
 CONSTRAINT atd_radius_user_assigned_ip_session_unique UNIQUE (user_id,ras_id,session_id),
 CONSTRAINT atd_radius_user_assigned_ip_owner_shape CHECK (
  (status='pending' AND request_key IS NOT NULL AND ras_id IS NULL AND session_id IS NULL)
  OR (status='active' AND request_key IS NULL AND ras_id IS NOT NULL AND session_id IS NOT NULL)
 )
);
CREATE UNIQUE INDEX IF NOT EXISTS atd_radius_user_assigned_ip_address_unique ON atd_radius_user_assigned_ip_leases(ip_address);
CREATE INDEX IF NOT EXISTS atd_radius_user_assigned_ip_user_idx ON atd_radius_user_assigned_ip_leases(user_id,status,lease_id);
