from atd_radius.infrastructure.user_sql import (
    USERS, NORMAL_CREDENTIAL, UPSERT_NORMAL_CREDENTIAL, USER_ATTRS, PERSISTENT_LAN,
)
from atd_radius.infrastructure.group_sql import GROUP, GROUP_ATTRS, UPSERT_GROUP_ATTR
from atd_radius.infrastructure.ras_sql import select_ras_ippools, insert_ras_ippool

def test_user_sql_uses_native_a124_tables():
    assert "FROM users" in USERS
    assert "FROM normal_users" in NORMAL_CREDENTIAL
    assert "ON CONFLICT (user_id)" in UPSERT_NORMAL_CREDENTIAL
    assert "FROM user_attrs" in USER_ATTRS
    assert "::macaddr" in PERSISTENT_LAN
    assert "::cidr" in PERSISTENT_LAN

def test_group_sql_uses_native_a124_tables():
    assert "FROM groups" in GROUP
    assert "FROM group_attrs" in GROUP_ATTRS
    assert "ON CONFLICT (group_id, attr_name)" in UPSERT_GROUP_ATTR

def test_ras_ippool_uses_database_serial():
    assert "SELECT serial, ras_id, ippool_id" in select_ras_ippools(1)
    assert "RETURNING serial" in insert_ras_ippool()
