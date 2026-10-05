CREATE INDEX IF NOT EXISTS ix_attribute_bindings_scope ON attribute_bindings(scope_type, scope_id, precedence);
CREATE INDEX IF NOT EXISTS ix_user_groups_group ON user_groups(group_id, user_id);
CREATE INDEX IF NOT EXISTS ix_user_services_service ON user_services(service_id, user_id);

CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_user_credentials_updated_at ON user_credentials;
CREATE TRIGGER trg_user_credentials_updated_at BEFORE UPDATE ON user_credentials
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
