# IBSng A1.24 → ATD Schema Parity Contract

This is the canonical schema-first contract. Do not invent an ATD replacement for an A1.24 concept until its source table, columns, relationships and consumers have been inspected.

## Core domains extracted from A1.24

| A1.24 area | Source objects | ATD migration rule |
|---|---|---|
| Administration | `admins`, `admin_perms` | preserve identity and permission semantics |
| RAS | `ras`, `ras_ports`, `ras_attrs`, `ras_ippools` | preserve RAS attributes, ports and pool bindings |
| IP allocation | `ippool`, `ippool_ips` | preserve pool state and individual assignments |
| Users | `users`, `normal_users`, `voip_users` | preserve subtype-specific data |
| Attributes | `user_attrs`, `group_attrs`, `ras_attrs` | preserve arbitrary/multi-valued attribute semantics |
| Groups | `groups` and related attribute/state tables | preserve membership and inherited policy |
| Calling identity | `caller_id_users` | preserve caller-ID admission behavior |
| Persistent LAN | `persistent_lan_users` | preserve persistent address/session behavior |
| Accounting | `connection_log`, `ias_event`, `ias_event_extended` | preserve historical records and accounting semantics |
| Bandwidth | `bw_interface`, `bw_node`, `bw_leaf`, `bw_leaf_services`, `bw_static_ip` | preserve hierarchy and usage semantics |
| Billing | `charges`, `charge_rules`, `internet_charge_rules`, `voip_charge_rules`, `voip_charge_rule_tariff`, `tariff_prefix_list` | preserve rule precedence and tariff behavior |
| Audit | `user_audit_log`, `web_analyzer_log` | preserve operational/audit history |

## Hard compatibility rules

1. Every A1.24 table must have a disposition: `native`, `mapped`, `transformed`, or `unsupported-with-decision`.
2. Every source column must have a mapping or an explicit documented reason for intentional omission.
3. Attribute tables are never flattened into a fixed column list without preserving unknown/custom attributes.
4. Billing rule inheritance and precedence must remain observable after migration.
5. Historical accounting data must not be silently discarded.
6. IDs/references used by imported configurations must remain stable or have a deterministic translation map.
7. A migration is incomplete until an imported backup can produce a parity report.

## Current status

This contract records the source domains already extracted. It is **not** a claim that migration is complete. The implementation phase must now fill the per-column mapping from the actual A1.24 SQL definitions and tests.
