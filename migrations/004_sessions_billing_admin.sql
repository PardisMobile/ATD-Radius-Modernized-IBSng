CREATE TABLE IF NOT EXISTS sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_key text NOT NULL UNIQUE,
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    ras_id uuid REFERENCES ras(id) ON DELETE SET NULL,
    framed_ip inet,
    started_at timestamptz,
    last_interim_at timestamptz,
    stopped_at timestamptz,
    input_octets bigint NOT NULL DEFAULT 0,
    output_octets bigint NOT NULL DEFAULT 0,
    terminate_cause text
);

CREATE TABLE IF NOT EXISTS accounting_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid REFERENCES sessions(id) ON DELETE CASCADE,
    event_type text NOT NULL CHECK (event_type IN ('start','interim','stop')),
    event_key text NOT NULL UNIQUE,
    received_at timestamptz NOT NULL DEFAULT now(),
    event_at timestamptz,
    input_octets bigint,
    output_octets bigint,
    raw_attributes jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS radius_request_cache (
    request_key text PRIMARY KEY,
    code integer NOT NULL,
    response_bytes bytea,
    expires_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS disconnect_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid REFERENCES sessions(id) ON DELETE CASCADE,
    requested_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'pending',
    reason text
);

CREATE TABLE IF NOT EXISTS plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    duration_seconds bigint NOT NULL DEFAULT 0,
    quota_bytes bigint NOT NULL DEFAULT 0,
    price numeric(20,4) NOT NULL DEFAULT 0,
    currency text NOT NULL DEFAULT 'IRR',
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS charges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    kind text NOT NULL,
    unit_price numeric(20,4) NOT NULL DEFAULT 0,
    currency text NOT NULL DEFAULT 'IRR',
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id uuid NOT NULL REFERENCES plans(id),
    starts_at timestamptz NOT NULL,
    expires_at timestamptz,
    status text NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount numeric(20,4) NOT NULL,
    currency text NOT NULL DEFAULT 'IRR',
    kind text NOT NULL,
    reference text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admins (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    enabled boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS permissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS admin_permissions (
    admin_id uuid NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    permission_id uuid NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (admin_id, permission_id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id uuid REFERENCES admins(id) ON DELETE SET NULL,
    action text NOT NULL,
    object_type text,
    object_id uuid,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
