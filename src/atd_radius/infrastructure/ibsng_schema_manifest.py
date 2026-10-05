"""Machine-readable inventory of the IBSng A1.24 PostgreSQL schema.

This is intentionally an inventory, not a replacement schema. A table cannot be
marked migrated until its columns, constraints, consumers and parity fixtures
are implemented.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IBSngTable:
    name: str
    domain: str
    notes: str = ""


IBSNG_A124_TABLES: tuple[IBSngTable, ...] = (
    IBSngTable("admins", "administration"),
    IBSngTable("admins_extended_attrs", "administration"),
    IBSngTable("admin_locks", "administration"),
    IBSngTable("admin_perms", "administration"),
    IBSngTable("admin_perm_templates", "administration"),
    IBSngTable("admin_perm_templates_detail", "administration"),
    IBSngTable("ippool", "ip_pool"),
    IBSngTable("ippool_ips", "ip_pool"),
    IBSngTable("ras", "ras"),
    IBSngTable("ras_ports", "ras"),
    IBSngTable("ras_attrs", "ras"),
    IBSngTable("ras_ippools", "ras"),
    IBSngTable("groups", "subscriber"),
    IBSngTable("group_attrs", "subscriber"),
    IBSngTable("users", "subscriber"),
    IBSngTable("normal_users", "subscriber"),
    IBSngTable("persistent_lan_users", "subscriber"),
    IBSngTable("add_user_saves", "subscriber"),
    IBSngTable("add_user_save_details", "subscriber"),
    IBSngTable("voip_users", "subscriber"),
    IBSngTable("user_attrs", "subscriber"),
    IBSngTable("caller_id_users", "subscriber"),
    IBSngTable("defs", "configuration"),
    IBSngTable("ibs_states", "configuration"),
    IBSngTable("credit_change", "credit"),
    IBSngTable("credit_change_userid", "credit"),
    IBSngTable("admin_deposit_change", "credit"),
    IBSngTable("connection_log", "session"),
    IBSngTable("connection_log_details", "session"),
    IBSngTable("bw_interface", "bandwidth"),
    IBSngTable("bw_node", "bandwidth"),
    IBSngTable("bw_leaf", "bandwidth"),
    IBSngTable("bw_leaf_services", "bandwidth"),
    IBSngTable("bw_static_ip", "bandwidth"),
    IBSngTable("charges", "billing"),
    IBSngTable("charge_rules", "billing", "Parent table for PostgreSQL inherited charge rules."),
    IBSngTable("internet_charge_rules", "billing", "PostgreSQL child table inheriting charge_rules."),
    IBSngTable("charge_rule_ports", "billing"),
    IBSngTable("charge_rule_day_of_weeks", "billing"),
    IBSngTable("voip_charge_rule_tariff", "billing"),
    IBSngTable("tariff_prefix_list", "billing"),
    IBSngTable("voip_charge_rules", "billing", "PostgreSQL child table inheriting charge_rules."),
    IBSngTable("user_audit_log", "audit"),
    IBSngTable("internet_onlines_snapshot", "snapshot"),
    IBSngTable("voip_onlines_snapshot", "snapshot"),
    IBSngTable("internet_bw_snapshot", "snapshot"),
    IBSngTable("user_messages", "messaging"),
    IBSngTable("admin_messages", "messaging"),
    IBSngTable("ias_event", "ias"),
    IBSngTable("ias_event_extended", "ias"),
    IBSngTable("web_analyzer_log", "web_analyzer"),
)

IBSNG_A124_SEQUENCES: tuple[str, ...] = (
    "admins_id_seq", "admin_locks_lock_id_seq", "admin_perm_template_id",
    "ippool_id_seq", "ras_id_seq", "groups_group_id_seq", "add_user_save_id_seq",
    "users_user_id_seq", "credit_change_id", "admin_deposit_change_id",
    "connection_log_id", "bw_interface_interface_id_seq", "bw_node_node_id_seq",
    "bw_leaf_leaf_id_seq", "bw_leaf_services_leaf_service_id_seq",
    "bw_static_ip_bw_static_ip_id_seq", "charges_id_seq", "charge_rules_id_seq",
    "voip_charge_rule_tariff_tariff_id_seq", "tariff_prefix_list_tariff_id_seq",
    "user_messages_message_id", "admin_messages_message_id", "ias_event_event_id",
    "web_analyzer_log_log_id",
)


def table_names() -> tuple[str, ...]:
    return tuple(table.name for table in IBSNG_A124_TABLES)


def validate_manifest() -> None:
    if len(IBSNG_A124_TABLES) != 51:
        raise AssertionError("IBSng A1.24 table inventory must contain 51 tables")
    if len({table.name for table in IBSNG_A124_TABLES}) != 51:
        raise AssertionError("IBSng A1.24 table inventory contains duplicate names")
    if len(IBSNG_A124_SEQUENCES) != 24:
        raise AssertionError("IBSng A1.24 sequence inventory must contain 24 sequences")
