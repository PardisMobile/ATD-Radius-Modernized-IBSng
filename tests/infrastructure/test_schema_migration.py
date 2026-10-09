from pathlib import Path

SCHEMA = Path("migrations/001_initial.sql").read_text(encoding="utf-8")

def test_migration_is_native_ibsng_schema():
    for table in (
        "admins", "admin_perms", "ippool", "ippool_ips", "ras", "ras_ports",
        "ras_attrs", "ras_ippools", "groups", "group_attrs", "users",
        "normal_users", "voip_users", "user_attrs", "caller_id_users",
        "connection_log", "connection_log_details", "charges", "charge_rules",
        "internet_charge_rules", "voip_charge_rule_tariff", "tariff_prefix_list",
        "voip_charge_rules", "user_audit_log", "internet_onlines_snapshot",
        "voip_onlines_snapshot", "ias_event", "ias_event_extended", "web_analyzer_log",
    ):
        assert f"create table {table}" in SCHEMA.lower()

def test_migration_does_not_create_parallel_modern_schema():
    for table in (
        "user_credentials", "user_groups", "user_services", "services",
        "attribute_bindings", "attributes", "sessions", "credit_ledger",
        "accounting_events", "audit_log", "ip_pools",
    ):
        assert f"create table {table}" not in SCHEMA.lower()


def test_numbered_migrations_have_unique_order_and_audit_runs_after_native_defs():
    from pathlib import Path

    migrations = sorted(Path("migrations").glob("[0-9][0-9][0-9]_*.sql"))
    prefixes = [path.name.split("_", 1)[0] for path in migrations]
    assert len(prefixes) == len(set(prefixes))
    assert next(i for i, path in enumerate(migrations) if path.name.endswith("_defs.sql")) < next(
        i for i, path in enumerate(migrations) if path.name.endswith("_operational_audit.sql")
    )
