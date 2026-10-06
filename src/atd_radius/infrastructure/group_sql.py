"""Exact A1.24 group persistence SQL contracts."""
from __future__ import annotations

GROUP = """SELECT group_id, group_name, owner_id, comment FROM groups WHERE group_id=%s"""
LIST_GROUPS = """SELECT group_id, group_name, owner_id, comment FROM groups ORDER BY group_id"""
INSERT_GROUP = """INSERT INTO groups (group_id, group_name, owner_id, comment) VALUES (%s,%s,%s,%s)"""
UPDATE_GROUP = """UPDATE groups SET group_name=%s, owner_id=%s, comment=%s WHERE group_id=%s"""
DELETE_GROUP = """DELETE FROM groups WHERE group_id=%s"""

GROUP_ATTRS = """SELECT group_id, attr_name, attr_value FROM group_attrs WHERE group_id=%s ORDER BY attr_name"""
UPSERT_GROUP_ATTR = """INSERT INTO group_attrs (group_id, attr_name, attr_value) VALUES (%s,%s,%s)
ON CONFLICT (group_id, attr_name) DO UPDATE SET attr_value=EXCLUDED.attr_value"""
DELETE_GROUP_ATTR = """DELETE FROM group_attrs WHERE group_id=%s AND attr_name=%s"""
