"""A1.24 attribute catalog extracted from the IBSng interface/plugin surface.

This is deliberately a catalog, not a claim that every entry has already been
implemented by the policy engine. Runtime behavior is added only after its
producer/consumer path has been mapped.
"""
from __future__ import annotations

from .attributes import AttributeDefinition, AttributeOperator


def _d(name: str, value_type: str = "string", *, multi: bool = False,
       operators: tuple[AttributeOperator, ...] = (AttributeOperator.SET,),
       description: str = "") -> AttributeDefinition:
    return AttributeDefinition(name, value_type, multi, operators, description)


# Names directly evidenced by A1.24 attrs.php and its attribute-update path.
IBSNG_ATTRIBUTE_DEFINITIONS: dict[str, AttributeDefinition] = {
    "rel_exp": _d("rel_exp", "integer", description="Relative expiration policy."),
    "abs_exp": _d("abs_exp", "integer", description="Absolute expiration policy."),
    "multi_login": _d("multi_login", "integer", description="Simultaneous/multiple login policy."),
    "normal_charge": _d("normal_charge", "string", description="Normal-user charging policy."),
    "voip_charge": _d("voip_charge", "string", description="VoIP charging policy."),
    "ippool": _d("ippool", "string", description="Assigned IP pool."),
    "assign_ip": _d("assign_ip", "string", description="Explicit IP assignment."),
    "radius_attrs": _d("radius_attrs", "string", multi=True,
                         operators=(AttributeOperator.SET, AttributeOperator.ADD, AttributeOperator.REMOVE),
                         description="Additional RADIUS attributes."),
    "group_id": _d("group_id", "string"),
    "group_name": _d("group_name", "string"),
    "owner_name": _d("owner_name", "string"),
    "normal_username": _d("normal_username", "string"),
    "normal_save_usernames": _d("normal_save_usernames", "boolean"),
    "generate_password": _d("generate_password", "boolean"),
    "password_character": _d("password_character", "boolean"),
    "password_digit": _d("password_digit", "boolean"),
    "normal_username_from_file": _d("normal_username_from_file", "string"),
    "voip_username": _d("voip_username", "string"),
    "voip_save_usernames": _d("voip_save_usernames", "boolean"),
    "voip_generate_password": _d("voip_generate_password", "boolean"),
    "voip_password_character": _d("voip_password_character", "boolean"),
    "voip_password_digit": _d("voip_password_digit", "boolean"),
    "voip_username_from_file": _d("voip_username_from_file", "string"),
    "caller_id": _d("caller_id", "string", multi=True,
                     operators=(AttributeOperator.SET, AttributeOperator.ADD, AttributeOperator.REMOVE)),
    "lock": _d("lock", "boolean"),
    "save_bw_usage": _d("save_bw_usage", "boolean"),
    "persistent_lan_mac": _d("persistent_lan_mac", "string"),
    "persistent_lan_ip": _d("persistent_lan_ip", "string"),
    "persistent_lan_ras_ip": _d("persistent_lan_ras_ip", "string"),
    "comment": _d("comment", "string"),
    "name": _d("name", "string"),
    "phone": _d("phone", "string"),
    "limit_mac": _d("limit_mac", "boolean"),
    "limit_station_ip": _d("limit_station_ip", "boolean"),
    "session_timeout": _d("session_timeout", "integer"),
    "idle_timeout": _d("idle_timeout", "integer"),
    "limit_caller_id": _d("limit_caller_id", "boolean"),
    "limit_caller_id_allow_not_defined": _d("limit_caller_id_allow_not_defined", "boolean"),
    "mail_quota": _d("mail_quota", "integer"),
    "email_address": _d("email_address", "string"),
    "fast_dial": _d("fast_dial", "string", multi=True,
                     operators=(AttributeOperator.SET, AttributeOperator.ADD, AttributeOperator.REMOVE)),
    "voip_preferred_language": _d("voip_preferred_language", "string"),
}


def get_ibsng_attribute_definitions() -> dict[str, AttributeDefinition]:
    """Return a copy of the catalog for use by the resolver."""
    return dict(IBSNG_ATTRIBUTE_DEFINITIONS)
