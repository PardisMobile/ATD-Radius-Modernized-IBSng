"""A1.24 attribute catalog used as the compatibility contract.

The catalog records what the A1.24 source exposes and where that behavior is
expected to be consumed. It intentionally does not mark behavior as migrated
until the producer/consumer path has an implementation and a compatibility
fixture.
"""
from __future__ import annotations

from dataclasses import dataclass

from .attributes import AttributeDefinition, AttributeOperator


@dataclass(frozen=True, slots=True)
class IBSngAttributeSpec:
    definition: AttributeDefinition
    source_area: str
    consumers: tuple[str, ...]
    radius_name: str | None = None
    migration_status: str = "catalogued"


def _s(
    name: str,
    *,
    value_type: str = "string",
    multi: bool = False,
    operators: tuple[AttributeOperator, ...] = (AttributeOperator.SET,),
    source_area: str,
    consumers: tuple[str, ...],
    radius_name: str | None = None,
) -> IBSngAttributeSpec:
    return IBSngAttributeSpec(
        definition=AttributeDefinition(
            name=name,
            value_type=value_type,
            multi=multi,
            operators=operators,
        ),
        source_area=source_area,
        consumers=consumers,
        radius_name=radius_name,
    )


# Names evidenced by the A1.24 attrs.php update path and plugin inventory.
# Values remain conservative (string) where the source semantics still need
# consumer-level inspection; guessing a numeric/boolean type would create a
# false compatibility guarantee.
IBSNG_A124_ATTRIBUTES: tuple[IBSngAttributeSpec, ...] = (
    _s("rel_exp", source_area="user/expiration", consumers=("expiration",)),
    _s("abs_exp", source_area="user/expiration", consumers=("expiration",)),
    _s("multi_login", source_area="user/login", consumers=("session", "radius")),
    _s("normal_charge", source_area="user/charge", consumers=("charging",)),
    _s("voip_charge", source_area="user/charge", consumers=("charging", "voip")),
    _s("ippool", source_area="user/network", consumers=("ippool", "radius")),
    _s("assign_ip", source_area="user/network", consumers=("ippool", "radius")),
    _s("radius_attrs", multi=True, operators=(AttributeOperator.SET, AttributeOperator.ADD, AttributeOperator.REMOVE, AttributeOperator.REPLACE), source_area="user/radius", consumers=("radius",)),
    _s("group_id", source_area="identity/group", consumers=("group",)),
    _s("group_name", source_area="identity/group", consumers=("group",)),
    _s("owner_name", source_area="identity", consumers=("identity",)),
    _s("name", source_area="identity", consumers=("identity",)),
    _s("phone", source_area="identity", consumers=("identity",)),
    _s("comment", source_area="identity", consumers=("identity",)),
    _s("normal_username", source_area="credentials/normal", consumers=("authentication",)),
    _s("normal_save_usernames", source_area="credentials/normal", consumers=("authentication",)),
    _s("generate_password", source_area="credentials/normal", consumers=("password-policy",)),
    _s("password_character", source_area="credentials/normal", consumers=("password-policy",)),
    _s("password_digit", source_area="credentials/normal", consumers=("password-policy",)),
    _s("normal_username_from_file", source_area="credentials/normal", consumers=("authentication",)),
    _s("voip_username", source_area="credentials/voip", consumers=("authentication", "voip")),
    _s("voip_save_usernames", source_area="credentials/voip", consumers=("authentication", "voip")),
    _s("voip_generate_password", source_area="credentials/voip", consumers=("password-policy", "voip")),
    _s("voip_password_character", source_area="credentials/voip", consumers=("password-policy", "voip")),
    _s("voip_password_digit", source_area="credentials/voip", consumers=("password-policy", "voip")),
    _s("voip_username_from_file", source_area="credentials/voip", consumers=("authentication", "voip")),
    _s("voip_preferred_language", source_area="credentials/voip", consumers=("voip",)),
    _s("caller_id", multi=True, operators=(AttributeOperator.SET, AttributeOperator.ADD, AttributeOperator.REMOVE), source_area="access/caller-id", consumers=("caller-id",)),
    _s("limit_caller_id", source_area="access/caller-id", consumers=("caller-id", "authorization")),
    _s("limit_caller_id_allow_not_defined", source_area="access/caller-id", consumers=("caller-id", "authorization")),
    _s("lock", source_area="access/restrictions", consumers=("authorization",)),
    _s("limit_mac", source_area="access/restrictions", consumers=("authorization", "session")),
    _s("limit_station_ip", source_area="access/restrictions", consumers=("authorization", "session")),
    _s("session_timeout", value_type="integer", source_area="session", consumers=("session", "radius"), radius_name="Session-Timeout"),
    _s("idle_timeout", value_type="integer", source_area="session", consumers=("session", "radius"), radius_name="Idle-Timeout"),
    _s("save_bw_usage", source_area="accounting", consumers=("accounting",)),
    _s("persistent_lan_mac", source_area="persistent-lan", consumers=("persistent-lan",)),
    _s("persistent_lan_ip", source_area="persistent-lan", consumers=("persistent-lan", "ippool")),
    _s("persistent_lan_ras_ip", source_area="persistent-lan", consumers=("persistent-lan", "ras")),
    _s("mail_quota", source_area="messaging", consumers=("mail",)),
    _s("email_address", source_area="messaging", consumers=("mail",)),
    _s("fast_dial", multi=True, operators=(AttributeOperator.SET, AttributeOperator.ADD, AttributeOperator.REMOVE), source_area="telephony", consumers=("voip",)),
)

ATTRIBUTE_SPECS = {item.definition.name: item for item in IBSNG_A124_ATTRIBUTES}
ATTRIBUTE_DEFINITIONS = {name: spec.definition for name, spec in ATTRIBUTE_SPECS.items()}


def get_ibsng_attribute_definitions() -> dict[str, AttributeDefinition]:
    """Return a copy of the typed definitions for resolver integration."""
    return dict(ATTRIBUTE_DEFINITIONS)


def get_attribute_spec(name: str) -> IBSngAttributeSpec:
    """Fail loudly for an attribute that has not entered the parity catalog."""
    try:
        return ATTRIBUTE_SPECS[name]
    except KeyError as exc:
        raise KeyError(f"IBSng A1.24 attribute is not catalogued: {name}") from exc
