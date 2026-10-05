BEGIN;

-- IBSng A1.24 domain parity layer. The first migration stays intentionally
-- small; this migration adds the relationships required by authentication,
-- policy inheritance, RAS/IP-pool assignment and administration.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'normal'
        CHECK (kind IN ('normal','voip','persistent_lan')),
    ADD COLUMN IF NOT EXISTS password_hash TEXT,
    ADD COLUMN IF NOT EXISTS first_login_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

ALTER TABLE groups
    ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
ALTER TABLE services
    ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS user_groups (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id BIGINT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, group_id)
);

CREATE TABLE IF NOT EXISTS user_services (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service_id BIGINT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, service_id)
);

CREATE TABLE IF NOT EXISTS ras_attributes (
    ras_id BIGINT NOT NULL REFERENCES ras(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (ras_id, name)
);

CREATE TABLE IF NOT EXISTS service_ras (
    service_id BIGINT NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    ras_id BIGINT NOT NULL REFERENCES ras(id) ON DELETE CASCADE,
    PRIMARY KEY (service_id, ras_id)
);

CREATE TABLE IF NOT EXISTS ras_ip_pools (
    ras_id BIGINT NOT NULL REFERENCES ras(id) ON DELETE CASCADE,
    ip_pool_id BIGINT NOT NULL REFERENCES ip_pools(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (ras_id, ip_pool_id)
);

CREATE TABLE IF NOT EXISTS ip_pool_addresses (
    id BIGSERIAL PRIMARY KEY,
    ip_pool_id BIGINT NOT NULL REFERENCES ip_pools(id) ON DELETE CASCADE,
    address INET NOT NULL,
    state TEXT NOT NULL DEFAULT 'available'
        CHECK (state IN ('available','reserved','allocated','disabled')),
    allocated_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    allocated_session_id TEXT REFERENCES sessions(id) ON DELETE SET NULL,
    UNIQUE (ip_pool_id, address)
);
CREATE INDEX IF NOT EXISTS ip_pool_addresses_available_idx
    ON ip_pool_addresses(ip_pool_id, address) WHERE state = 'available';

CREATE TABLE IF NOT EXISTS charges (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('flat','time','traffic','service')),
    unit_price NUMERIC(20,6) NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'IRR',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admins (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS permissions (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS admin_permissions (
    admin_id BIGINT NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (admin_id, permission_id)
);

COMMIT;
