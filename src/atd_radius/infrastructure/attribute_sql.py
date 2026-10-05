"""SQL contract for lossless IBSng attribute persistence.

The adapter intentionally exposes SQL generation separately from execution so
schema verification can be tested before a live PostgreSQL connection exists.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttributeTableSpec:
    table: str
    owner_column: str
    name_column: str
    value_column: str


# These are compatibility targets; exact A1.24 column names must be confirmed
# from the extracted SQL before enabling live migration.
USER_ATTRS = AttributeTableSpec("user_attrs", "user_id", "attribute", "value")
GROUP_ATTRS = AttributeTableSpec("group_attrs", "group_id", "attribute", "value")
RAS_ATTRS = AttributeTableSpec("ras_attrs", "ras_id", "attribute", "value")


def select_attributes(spec: AttributeTableSpec) -> str:
    return (
        f"SELECT {spec.owner_column}, {spec.name_column}, {spec.value_column} "
        f"FROM {spec.table} WHERE {spec.owner_column} = $1 ORDER BY {spec.name_column}"
    )
