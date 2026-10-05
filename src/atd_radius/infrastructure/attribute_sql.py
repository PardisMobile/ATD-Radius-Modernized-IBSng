"""SQL contract for lossless IBSng A1.24 attribute persistence.

Schema is confirmed directly from the user-supplied A1.24 db/tables.sql.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttributeTableSpec:
    table: str
    owner_column: str
    name_column: str
    value_column: str


USER_ATTRS = AttributeTableSpec("user_attrs", "user_id", "attr_name", "attr_value")
GROUP_ATTRS = AttributeTableSpec("group_attrs", "group_id", "attr_name", "attr_value")
RAS_ATTRS = AttributeTableSpec("ras_attrs", "ras_id", "attr_name", "attr_value")


def select_attributes(spec: AttributeTableSpec) -> str:
    return (
        f"SELECT {spec.owner_column}, {spec.name_column}, {spec.value_column} "
        f"FROM {spec.table} WHERE {spec.owner_column} = $1 "
        f"ORDER BY {spec.name_column}"
    )


def upsert_attributes(spec: AttributeTableSpec) -> str:
    return (
        f"INSERT INTO {spec.table} ({spec.owner_column}, {spec.name_column}, {spec.value_column}) "
        f"VALUES ($1, $2, $3) "
        f"ON CONFLICT ({spec.owner_column}, {spec.name_column}) "
        f"DO UPDATE SET {spec.value_column} = EXCLUDED.{spec.value_column}"
    )


def delete_attribute(spec: AttributeTableSpec) -> str:
    return f"DELETE FROM {spec.table} WHERE {spec.owner_column} = $1 AND {spec.name_column} = $2"


def select_user_attributes() -> str:
    return select_attributes(USER_ATTRS)


def select_group_attributes() -> str:
    return select_attributes(GROUP_ATTRS)


def select_ras_attributes() -> str:
    return select_attributes(RAS_ATTRS)
