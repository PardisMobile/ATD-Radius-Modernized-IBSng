# IBSng A1.24 — Database Extraction Baseline

This document records the database facts extracted directly from the supplied `IBSng-A1.24.tar.bz2` source archive. It is the baseline for ATD's lossless migration work.

## Source fingerprint

- Archive: `IBSng-A1.24.tar.bz2`
- SHA-256: `c7117a6a2fd252aa9b8149a1ee6606f9320888da347ee4f839614bb9349d18a8`
- Extracted IBSng files: 2,295
- Python source files: 453
- PHP source files: 530
- Smarty templates: 284
- SQL files: 20
- Main DB schema: `db/tables.sql`
- DB functions: `db/functions.sql`
- Initial data: `db/initial.sql`
- Compiled configuration seed: `db/defs.sql`

## Database platform and installation behavior

The A1.24 installer uses PostgreSQL. `core/db_conf.py` defaults to:

- database: `IBSng`
- username: `ibs`
- password: `ibsdbpass`
- port: `5432`
- host: local Unix socket when unset

The installer creates/imports the database in this order:

1. `tables.sql`
2. `functions.sql`
3. `initial.sql`
4. `defs.sql`

The supplied installation guide also requires PostgreSQL `pg_hba.conf` access and creates the `IBSng` database/user before running `scripts/setup.py`.

## Schema inventory

A1.24 `db/tables.sql` defines **51 tables**, **24 sequences**, and **19 explicit indexes**.

### Administration / permissions

1. `admins`
2. `admins_extended_attrs`
3. `admin_locks`
4. `admin_perms`
5. `admin_perm_templates`
6. `admin_perm_templates_detail`

### IP allocation

7. `ippool`
8. `ippool_ips`

### RAS / NAS

9. `ras`
10. `ras_ports`
11. `ras_attrs`
12. `ras_ippools`

### Subscriber / identity

13. `groups`
14. `group_attrs`
15. `users`
16. `normal_users`
17. `persistent_lan_users`
18. `add_user_saves`
19. `add_user_save_details`
20. `voip_users`
21. `user_attrs`
22. `caller_id_users`

### Configuration / state

23. `defs`
24. `ibs_states`

### Credit / connection history

25. `credit_change`
26. `credit_change_userid`
27. `admin_deposit_change`
28. `connection_log`
29. `connection_log_details`

### Bandwidth manager

30. `bw_interface`
31. `bw_node`
32. `bw_leaf`
33. `bw_leaf_services`
34. `bw_static_ip`

### Charging

35. `charges`
36. `charge_rules`
37. `internet_charge_rules`
38. `charge_rule_ports`
39. `charge_rule_day_of_weeks`
40. `voip_charge_rule_tariff`
41. `tariff_prefix_list`
42. `voip_charge_rules`

`internet_charge_rules` and `voip_charge_rules` use PostgreSQL table inheritance from `charge_rules`; the inherited columns are part of their effective schema and must not be lost by a naive column-only parser.

### Audit / snapshots / messaging

43. `user_audit_log`
44. `internet_onlines_snapshot`
45. `voip_onlines_snapshot`
46. `internet_bw_snapshot`
47. `user_messages`
48. `admin_messages`

### IAS / accounting events

49. `ias_event`
50. `ias_event_extended`

### Web analyzer

51. `web_analyzer_log`

## Important primary entities

### `users`

Core subscriber record. Important fields include:

- `user_id` bigint primary key
- `owner_id` → `admins`
- `credit` numeric(12,2)
- `group_id`
- `creation_date`

Credentials and subscriber policy are deliberately split into related tables:

- `normal_users`
- `voip_users`
- `user_attrs`
- `caller_id_users`
- `persistent_lan_users`

This separation is a critical IBSng behavior and must remain representable in ATD.

### Attribute storage

IBSng uses generic name/value attribute tables at multiple scopes:

- `admins_extended_attrs`
- `ras_attrs`
- `group_attrs`
- `user_attrs`

The attribute system is therefore a first-class database concept, not merely a RADIUS response formatter.

### `ras`

Stores RAS identity and authentication data including:

- IP address
- type
- RADIUS secret
- active state
- comment

RAS-specific attributes and IP-pool associations are stored separately in `ras_attrs` and `ras_ippools`.

### IP pools

`ippool` defines pools and `ippool_ips` stores their concrete IPv4/inet members. The ATD allocator must preserve both pool identity and explicit address membership.

### Charging

Charging is significantly richer than a single unit-price field. The schema includes:

- Internet/VoIP charge definitions
- time windows
- time limits
- RAS restrictions
- RAS port restrictions
- day-of-week restrictions
- Internet CPM/CPK rules
- bandwidth limits
- bandwidth-manager leaf bindings
- VoIP tariffs
- prefix matching
- free seconds
- minimum duration
- rounding rules

A simplified `Charge` model is therefore **not sufficient for parity**.

## Sequences

A1.24 defines these sequences:

`admins_id_seq`, `admin_locks_lock_id_seq`, `admin_perm_template_id`, `ippool_id_seq`, `ras_id_seq`, `groups_group_id_seq`, `add_user_save_id_seq`, `users_user_id_seq`, `credit_change_id`, `admin_deposit_change_id`, `connection_log_id`, `bw_interface_interface_id_seq`, `bw_node_node_id_seq`, `bw_leaf_leaf_id_seq`, `bw_leaf_services_leaf_service_id_seq`, `bw_static_ip_bw_static_ip_id_seq`, `charges_id_seq`, `charge_rules_id_seq`, `voip_charge_rule_tariff_tariff_id_seq`, `tariff_prefix_list_tariff_id_seq`, `user_messages_message_id`, `admin_messages_message_id`, `ias_event_event_id`, `web_analyzer_log_log_id`.

## Functions and initialization

The database installation is not just table creation. `functions.sql`, `initial.sql` and `defs.sql` are required parts of the operational baseline.

`initial.sql` creates the internal system administrator, the `GOD` permission, state flags, and automatic-cleanup defaults.

`defs.sql` contains serialized default configuration values including RADIUS ports, RADIUS enablement/bind address, snapshot intervals, bandwidth commands, IAS state, trusted clients and user-audit settings.

## Upgrade chain

The source includes upgrade SQL files from A1.04 through A1.23. These must be retained as historical compatibility evidence rather than discarded during modernization.

## Backup / restore finding

The A1.24 source installer itself exposes a `Backup/Restore` menu entry marked `notImplemented`. Therefore the source does **not** contain an authoritative custom backup format that ATD should reproduce.

The operationally authoritative migration source is consequently a PostgreSQL database dump/restore plus the schema/initialization semantics above. ATD will support native PostgreSQL backup restoration and a dedicated parity/import path rather than inventing an IBSng-specific backup format.

## ATD migration rule

No table is considered migrated because a similarly named ATD model exists.

For every source table, ATD must record:

1. source columns and types
2. primary/unique keys
3. foreign keys
4. indexes
5. defaults
6. inheritance semantics
7. producer code
8. consumer code
9. migration mapping
10. parity test

Only then can the table be marked `migrated`.

## Next implementation target

The next database implementation milestone is to build the **A1.24 schema manifest and import/parity framework** around these 51 tables, preserving PostgreSQL-native types such as `inet`, `cidr`, `macaddr`, timestamps, numeric credit values, sequences and inherited charge tables.
