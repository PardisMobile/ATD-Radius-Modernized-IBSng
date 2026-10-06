from atd_radius.infrastructure.ras_sql import (
    select_active_ras_ids, select_ras, select_ras_ippools, select_ras_ports,
    upsert_ras_port, delete_ras_port, insert_ras_ippool, delete_ras_ippool,
)

def test_ras_queries_match_a124_table_boundaries():
    assert "FROM ras WHERE ras_id = %s" in select_ras(1)
    assert select_active_ras_ids().endswith("ORDER BY ras_id")
    assert "FROM ras_ports" in select_ras_ports(1)
    assert "FROM ras_ippools" in select_ras_ippools(1)

def test_ras_port_upsert_uses_a124_primary_key():
    sql = upsert_ras_port()
    assert "ON CONFLICT (ras_id, port_name)" in sql


def test_ras_parameterized_queries_use_psycopg_placeholders():
    assert "%s" in select_ras(1)
    assert "%s" in select_ras_ports(1)
    assert "%s" in select_ras_ippools(1)


def test_ras_mutation_queries_use_psycopg_placeholders_everywhere():
    sql = upsert_ras_port() + delete_ras_port() + insert_ras_ippool() + delete_ras_ippool()
    assert "$" not in sql
    assert sql.count("%s") >= 5
