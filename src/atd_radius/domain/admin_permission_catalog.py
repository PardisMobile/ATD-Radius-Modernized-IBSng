"""Source-derived IBSng A1.24 permission metadata for safe native permission edits."""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class PermissionKind(str, Enum):
    NO_VALUE = "NOVALUE"
    SINGLE_VALUE = "SINGLEVALUE"
    MULTI_VALUE = "MULTIVALUE"


@dataclass(frozen=True)
class PermissionDefinition:
    name: str
    kind: PermissionKind
    dependencies: tuple[str, ...] = ()


# Inventory and dependencies are derived from core/admin/perms/*.py in A1.24.
# The only SingleValue permissions in this source inherit AllRestrictedSingleValuePermission.
_NO_VALUE = """
ACCESS ALL CHARGES
ACCESS ALL GROUPS
ADD NEW ADMIN
ADD NEW GROUP
ADD NEW USER
CHANGE ADMIN DEPOSIT
CHANGE ADMIN INFO
CHANGE ADMIN PASSWORD
CHANGE ADMIN PERMISSIONS
CHANGE BANDWIDTH MANAGER
CHANGE CHARGE
CHANGE IBS DEFINITIONS
CHANGE IPPOOL
CHANGE MAILBOX
CHANGE RAS
CHANGE USERS OWNER
CHANGE VOIP TARIFF
DELETE ADMIN
DELETE REPORTS
GET RAS INFORMATION
GOD
LIST IPPOOL
LIST RAS
NO DEPOSIT LIMIT
POST MESSAGES
SEE ADMIN INFO
SEE ADMIN PERMISSIONS
SEE ONLINE SNAPSHOTS
SEE REALTIME SNAPSHOTS
SEE VOIP TARIFF
VIEW MESSAGES
""".splitlines()

_SINGLE_VALUE = """
CHANGE GROUP
CHANGE NORMAL USER ATTRIBUTES
CHANGE USER ATTRIBUTES
CHANGE USER CREDIT
CHANGE VOIP USER ATTRIBUTES
CLEAR USER
DELETE USER
GET USER INFORMATION
KILL USER
SEE BW SNAPSHOTS
SEE CONNECTION LOGS
SEE CREDIT CHANGES
SEE ONLINE USERS
SEE SAVED USERNAME PASSWORDS
SEE USER AUDIT LOGS
SEE WEB ANALYZER LOGS
""".splitlines()

_MULTI_VALUE = """
CHARGE ACCESS
GROUP ACCESS
LIMIT LOGIN ADDR
LIMIT MAIL DOMAIN
""".splitlines()

_DEPENDENCIES = {
    "CHANGE ADMIN DEPOSIT": ("CHANGE ADMIN INFO",),
    "CHANGE ADMIN INFO": ("SEE ADMIN INFO",),
    "CHANGE ADMIN PASSWORD": ("SEE ADMIN INFO",),
    "CHANGE ADMIN PERMISSIONS": ("SEE ADMIN INFO", "SEE ADMIN PERMISSIONS"),
    "CHANGE BANDWIDTH MANAGER": ("CHANGE CHARGE",),
    "CHANGE CHARGE": ("ACCESS ALL CHARGES",),
    "CHANGE GROUP": ("ADD NEW GROUP",),
    "CHANGE IPPOOL": ("LIST IPPOOL",),
    "CHANGE MAILBOX": ("CHANGE NORMAL USER ATTRIBUTES",),
    "CHANGE NORMAL USER ATTRIBUTES": ("CHANGE USER ATTRIBUTES",),
    "CHANGE RAS": ("LIST RAS", "GET RAS INFORMATION"),
    "CHANGE USER ATTRIBUTES": ("GET USER INFORMATION",),
    "CHANGE USER CREDIT": ("GET USER INFORMATION",),
    "CHANGE VOIP TARIFF": ("CHANGE CHARGE",),
    "CHANGE VOIP USER ATTRIBUTES": ("CHANGE USER ATTRIBUTES",),
    "CLEAR USER": ("SEE ONLINE USERS",),
    "DELETE ADMIN": ("SEE ADMIN INFO",),
    "DELETE USER": ("GET USER INFORMATION",),
    "GET RAS INFORMATION": ("LIST RAS",),
    "KILL USER": ("SEE ONLINE USERS",),
    "LIMIT MAIL DOMAIN": ("CHANGE MAILBOX",),
    "SEE ADMIN PERMISSIONS": ("SEE ADMIN INFO",),
    "SEE SAVED USERNAME PASSWORDS": ("GET USER INFORMATION",),
    "SEE VOIP TARIFF": ("CHANGE CHARGE",),
}

_DEFINITIONS = {
    name: PermissionDefinition(name, kind, _DEPENDENCIES.get(name, ()))
    for names, kind in (
        (_NO_VALUE, PermissionKind.NO_VALUE),
        (_SINGLE_VALUE, PermissionKind.SINGLE_VALUE),
        (_MULTI_VALUE, PermissionKind.MULTI_VALUE),
    )
    for name in names if name
}


def permission_definition(name: str) -> PermissionDefinition | None:
    return _DEFINITIONS.get(name)


def all_permission_definitions() -> tuple[PermissionDefinition, ...]:
    return tuple(_DEFINITIONS[name] for name in sorted(_DEFINITIONS))


def validate_permission_value(
    name: str,
    value: str,
    *,
    group_exists: Callable[[str], bool],
    charge_exists: Callable[[str], bool],
) -> None:
    """Mirror A1.24 checkNewValue behavior for registered permission classes."""
    definition = permission_definition(name)
    if definition is None:
        raise ValueError("unknown permission")

    if definition.kind is PermissionKind.SINGLE_VALUE and value not in {"All", "Restricted"}:
        raise ValueError("value must be All or Restricted")

    # A1.24 GROUP ACCESS and CHARGE ACCESS validate the named resource.
    if name == "GROUP ACCESS" and not group_exists(value):
        raise ValueError("group does not exist")
    if name == "CHARGE ACCESS" and not charge_exists(value):
        raise ValueError("charge does not exist")

    # A1.24 IPy accepts a single IP or IP/network with a valid mask.
    if name == "LIMIT LOGIN ADDR":
        try:
            if "/" in value:
                ipaddress.ip_network(value, strict=False)
            else:
                ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("invalid IP address or network") from exc
