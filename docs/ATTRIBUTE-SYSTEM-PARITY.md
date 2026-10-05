# IBSng A1.24 → ATD Attribute System Parity

## Purpose

The attribute system is a compatibility boundary, not a convenience key/value store. ATD must preserve the behavior of IBSng attributes and the plugins that consume them while moving the implementation to Python 3.

## Milestone: producer/consumer catalog

`src/atd_radius/domain/attribute_catalog.py` is now the machine-readable catalog for the attribute names evidenced by the A1.24 attribute update path. Each entry records:

- stable IBSng attribute name
- conservative value type (string until consumer semantics prove a stronger type)
- multiplicity
- allowed policy operators
- source/behavior area
- known consumer boundary
- RADIUS name where the mapping is already explicit
- migration status

This catalog is intentionally **not** treated as completed runtime behavior. A catalogued attribute is not `migrated` until its consumer behavior is implemented and covered by a compatibility fixture.

## A1.24 attribute families currently catalogued

| Family | Examples | ATD consumer boundary | Status |
|---|---|---|---|
| Expiration | `rel_exp`, `abs_exp` | expiration/policy | Catalogued |
| Login | `multi_login` | session/RADIUS | Catalogued |
| Charging | `normal_charge`, `voip_charge` | charging | Catalogued |
| Network | `ippool`, `assign_ip` | IP pool/RADIUS | Catalogued |
| RADIUS | `radius_attrs` | RADIUS mapper | Catalogued |
| Identity | `name`, `phone`, `comment`, ownership/group fields | identity/group | Catalogued |
| Normal credentials | `normal_username`, password-generation controls | authentication/password policy | Catalogued |
| VoIP credentials | `voip_username`, password-generation controls | authentication/VoIP | Catalogued |
| Caller restrictions | `caller_id`, `limit_caller_id*` | authorization/caller-ID | Catalogued |
| Access restrictions | `lock`, `limit_mac`, `limit_station_ip` | authorization/session | Catalogued |
| Session | `session_timeout`, `idle_timeout` | session/RADIUS | Catalogued; RADIUS names explicit |
| Accounting | `save_bw_usage` | accounting | Catalogued |
| Persistent LAN | `persistent_lan_*` | persistent-LAN/IP/RAS | Catalogued |
| Messaging | `mail_quota`, `email_address` | mail | Catalogued |
| Telephony | `fast_dial`, `voip_preferred_language` | VoIP | Catalogued |

## Resolver contract

The typed resolver keeps:

- scope/provenance (system, RAS, service, group, user)
- deterministic precedence
- typed values
- multi-valued attributes
- explicit set/add/remove/replace operations
- explainability for the UI and audit tooling

Current default scope order:

`SYSTEM → RAS → SERVICE → GROUP → USER`

This remains an initial deterministic model, **not a final IBSng parity claim**. Plugin-specific precedence and merge semantics must be extracted from each A1.24 consumer before that attribute is marked migrated.

## Important non-goals

Naming an attribute does not implement its behavior. For example, `session_timeout` is only fully migrated when the value is consumed by the session/RADIUS path with IBSng-compatible semantics.

The same rule applies to IP pools, credit, multilogin, bandwidth accounting, caller-ID restrictions, VoIP attributes, and all charging attributes.

## Next parity work

1. Map every catalog entry to its A1.24 producer(s).
2. Map every entry to every A1.24 consumer/plugin.
3. Record storage representation and defaults.
4. Record inheritance and override behavior.
5. Record RADIUS attribute translation where applicable.
6. Implement behavior in ATD policy/session/protocol services.
7. Add fixture-based compatibility tests.
8. Only then mark the attribute as `migrated` in the master compatibility matrix.
