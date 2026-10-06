"""Exact A1.24 user persistence SQL contracts.

Schema is taken directly from Source of Truth/IBSng-A1.24.tar.bz2,
db/tables.sql. These contracts deliberately keep normal/VoIP credentials,
generic attributes, caller-id and persistent-LAN data in their native tables.
"""
from __future__ import annotations

USERS = """SELECT user_id, owner_id, credit, group_id, creation_date FROM users WHERE user_id = %s"""
LIST_USERS = """SELECT user_id, owner_id, credit, group_id, creation_date FROM users ORDER BY user_id"""
INSERT_USER = """INSERT INTO users (user_id, owner_id, credit, group_id) VALUES (%s,%s,%s,%s)"""
UPDATE_USER = """UPDATE users SET owner_id=%s, credit=%s, group_id=%s WHERE user_id=%s"""
DELETE_USER = """DELETE FROM users WHERE user_id=%s"""

NORMAL_CREDENTIAL = """SELECT user_id, normal_username, normal_password FROM normal_users WHERE user_id=%s"""
UPSERT_NORMAL_CREDENTIAL = """INSERT INTO normal_users (user_id, normal_username, normal_password) VALUES (%s,%s,%s)
ON CONFLICT (user_id) DO UPDATE SET normal_username=EXCLUDED.normal_username, normal_password=EXCLUDED.normal_password"""
DELETE_NORMAL_CREDENTIAL = """DELETE FROM normal_users WHERE user_id=%s"""

VOIP_CREDENTIAL = """SELECT user_id, voip_username, voip_password FROM voip_users WHERE user_id=%s"""
UPSERT_VOIP_CREDENTIAL = """INSERT INTO voip_users (user_id, voip_username, voip_password) VALUES (%s,%s,%s)
ON CONFLICT (user_id) DO UPDATE SET voip_username=EXCLUDED.voip_username, voip_password=EXCLUDED.voip_password"""
DELETE_VOIP_CREDENTIAL = """DELETE FROM voip_users WHERE user_id=%s"""

CALLER_IDS = """SELECT user_id, caller_id FROM caller_id_users WHERE user_id=%s ORDER BY caller_id"""
INSERT_CALLER_ID = """INSERT INTO caller_id_users (user_id, caller_id) VALUES (%s,%s)"""
DELETE_CALLER_ID = """DELETE FROM caller_id_users WHERE user_id=%s AND caller_id=%s"""

PERSISTENT_LAN = """SELECT user_id, persistent_lan_mac::macaddr, persistent_lan_ip::cidr, persistent_lan_ras_id
FROM persistent_lan_users WHERE user_id=%s ORDER BY persistent_lan_mac::text, persistent_lan_ip::text"""
INSERT_PERSISTENT_LAN = """INSERT INTO persistent_lan_users (user_id, persistent_lan_mac, persistent_lan_ip, persistent_lan_ras_id)
VALUES (%s,%s::macaddr,%s::cidr,%s)"""
DELETE_PERSISTENT_LAN = """DELETE FROM persistent_lan_users WHERE user_id=%s AND persistent_lan_mac=%s::macaddr AND persistent_lan_ip=%s::cidr"""

USER_ATTRS = """SELECT user_id, attr_name, attr_value FROM user_attrs WHERE user_id=%s ORDER BY attr_name"""
UPSERT_USER_ATTR = """INSERT INTO user_attrs (user_id, attr_name, attr_value) VALUES (%s,%s,%s)
ON CONFLICT (user_id, attr_name) DO UPDATE SET attr_value=EXCLUDED.attr_value"""
DELETE_USER_ATTR = """DELETE FROM user_attrs WHERE user_id=%s AND attr_name=%s"""
