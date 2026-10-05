# IBSng A1.24 Source Inventory Baseline

This baseline is derived from the canonical archive at Source of Truth/IBSng-A1.24.tar.bz2.

| Item | A1.24 baseline |
|---|---:|
| Total archive files | 2,295 |
| Python files | 453 |
| PHP files | 530 |
| Smarty templates | 284 |
| SQL files | 20 |
| PostgreSQL tables | 51 |
| PostgreSQL sequences | 24 |
| Explicit indexes | 19 |

## Database installation order

1. tables.sql
2. functions.sql
3. initial.sql
4. defs.sql

## Compatibility rule

This inventory is a source baseline, not an implementation-completion claim. Every table, sequence, index and runtime consumer must eventually have an ATD disposition in the migration matrix: native, mapped, transformed, or explicitly unsupported with a documented decision.

## Important source-confirmed areas

- Attribute persistence: user_attrs, group_attrs, ras_attrs
- Users: users, normal_users, voip_users, caller_id_users, persistent_lan_users
- RAS/IP pools: ras, ras_ports, ras_attrs, ras_ippools, ippool, ippool_ips
- Accounting/session: connection_log and related accounting structures
- Billing: charges, charge_rules, internet_charge_rules, voip_charge_rule_tariff, tariff_prefix_list, voip_charge_rules
- Bandwidth: bw_interface, bw_node, bw_leaf, bw_leaf_services, bw_static_ip
- Administration: admins, admin_perms, user_audit_log
- IAS/events: ias_event, ias_event_extended

The canonical archive remains authoritative if this summary conflicts with the source.
