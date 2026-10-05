"""Exact A1.24 group persistence SQL contracts."""
from __future__ import annotations

GROUP = """SELECT group_id, group_name, owner_id, comment FROM groups WHERE group_id=$1"""
LIST_GROUPS = """SELECT group_id, group_name, owner_id, comment FROM groups ORDER BY group_id"""
INSERT_GROUP = """INSERT INTO groups (group_id, group_name, owner_id, comment) VALUES ($1,$2,$3,$4)"""
UPDATE_GROUP = """UPDATE groups SET group_name=$2, owner_id=$3, comment=$4 WHERE group_id=$1"""
DELETE_GROUP = """DELETE FROM groups WHERE group_id=$1"""

GROUP_ATTRS = """SELECT group_id, attr_name, attr_value FROM group_attrs WHERE group_id=$1 ORDER BY attr_name"""
UPSERT_GROUP_ATTR = """INSERT INTO group_attrs (group_id, attr_name, attr_value) VALUES ($1,$2,$3)
ON CONFLICT (group_id, attr_name) DO UPDATE SET attr_value=EXCLUDED.attr_value"""
DELETE_GROUP_ATTR = """DELETE FROM group_attrs WHERE group_id=$1 AND attr_name=$2"""
