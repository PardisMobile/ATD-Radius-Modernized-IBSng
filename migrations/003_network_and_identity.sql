CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','expired','locked')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_credentials (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    auth_type text NOT NULL DEFAULT 'password',
    password_hash text,
    enabled boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    description text,
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS services (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    description text,
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS user_groups (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    group_id uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, group_id)
);

CREATE TABLE IF NOT EXISTS user_services (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service_id uuid NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    starts_at timestamptz,
    expires_at timestamptz,
    enabled boolean NOT NULL DEFAULT true,
    PRIMARY KEY (user_id, service_id)
);

CREATE TABLE IF NOT EXISTS attributes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    value text NOT NULL,
    value_type text NOT NULL DEFAULT 'string',
    operator text NOT NULL DEFAULT ':=',
    UNIQUE (name, value, operator)
);

CREATE TABLE IF NOT EXISTS attribute_bindings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    attribute_id uuid NOT NULL REFERENCES attributes(id) ON DELETE CASCADE,
    scope_type text NOT NULL CHECK (scope_type IN ('ras','group','service','user')),
    scope_id uuid NOT NULL,
    precedence integer NOT NULL DEFAULT 100,
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS ras (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    kind text NOT NULL,
    address inet,
    enabled boolean NOT NULL DEFAULT true,
    secret_ref text
);

CREATE TABLE IF NOT EXISTS ip_pools (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    network cidr NOT NULL,
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS ip_pool_addresses (
    pool_id uuid NOT NULL REFERENCES ip_pools(id) ON DELETE CASCADE,
    address inet NOT NULL,
    state text NOT NULL DEFAULT 'available' CHECK (state IN ('available','reserved','allocated','disabled')),
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (pool_id, address)
);

CREATE TABLE IF NOT EXISTS ip_allocations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id uuid NOT NULL REFERENCES ip_pools(id),
    address inet NOT NULL,
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    allocated_at timestamptz NOT NULL DEFAULT now(),
    released_at timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_ip_allocation ON ip_allocations(address) WHERE released_at IS NULL;
