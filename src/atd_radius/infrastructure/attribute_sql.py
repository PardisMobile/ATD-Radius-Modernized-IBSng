"""SQL contract for lossless IBSng A1.24 attribute persistence.

Column names in the confirmed A1.24 user/group attribute tables are preserved
verbatim here. RAS attributes remain intentionally gated until their exact
source definition is verified from A1.24 SQL/source consumers.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttributeTableSpec:
    table: str
    owner_column: str
    name_column: str
    value_column: str


# Confirmed from the A1.24 source consumers/SQL references:
# user_attrs(user_id, attr_name, attr_value)
# group_attrs(group_id, attr_name, attr_value)
USER_ATTRS = AttributeTableSpec("user_attrs", "user_id", "attr_name", "attr_value")
GROUP_ATTRS = AttributeTableSpec("group_attrs", "group_id", "attr_name", "attr_value")


def select_attributes(spec: AttributeTableSpec) -> str:
    return (
        f"SELECT {spec.owner_column}, {spec.name_column}, {spec.value_column} "
        f"FROM {spec.table} WHERE {spec.owner_column} = $1 "
        f"ORDER BY {spec.name_column}"
    )


def select_user_attributes() -> str:
    return select_attributes(USER_ATTRS)


def select_group_attributes() -> str:
    return select_attributes(GROUP_ATTRS)
