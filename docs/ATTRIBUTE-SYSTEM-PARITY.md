# IBSng A1.24 → ATD Attribute System Parity

## Purpose

The attribute system is a compatibility boundary, not a convenience key/value store. ATD must preserve the behavior of IBSng attributes and the plugins that consume them while moving the implementation to Python 3.

## Source evidence mapped in this milestone

The A1.24 interface attribute update path explicitly references the following groups of behavior:

- expiration: `rel_exp`, `abs_exp`
- login policy: `multi_login`
- charging: `normal_charge`, `voip_charge`
- IP allocation: `ippool`, `assign_ip`
- RADIUS attributes: `radius_attrs`
- identity/group ownership: `group_id`, `group_name`, `owner_name`, `name`, `phone`, `comment`
- normal-user credentials: `normal_username`, `normal_save_usernames`, `generate_password`, `password_character`, `password_digit`, `normal_username_from_file`
- VoIP credentials: `voip_username`, `voip_save_usernames`, `voip_generate_password`, `voip_password_character`, `voip_password_digit`, `voip_username_from_file`, `voip_preferred_language`
- caller identity: `caller_id`, `limit_caller_id`, `limit_caller_id_allow_not_defined`
- access restrictions: `lock`, `limit_mac`, `limit_station_ip`
- session policy: `session_timeout`, `idle_timeout`
- usage/accounting: `save_bw_usage`
- persistent LAN: `persistent_lan_mac`, `persistent_lan_ip`, `persistent_lan_ras_ip`
- messaging/telephony: `mail_quota`, `email_address`, `fast_dial`

These names are corroborated by the A1.24 `attrs.php` update flow in the project source inventory. See the Library extraction for the exact source references. fileciteturn295file0 fileciteturn295file1 fileciteturn295file2

## ATD representation

Each attribute has:

- a stable name
- a declared value type
- multiplicity
- allowed operators
- scope
- precedence
- source/provenance
- enabled state

The resolver produces an effective set and retains the source chain so the Admin UI can answer **why this value won**.

Current default scope order:

`SYSTEM → RAS → SERVICE → GROUP → USER`

This is the initial deterministic model. It is **not yet declared final IBSng parity**; exact plugin-specific precedence and merge semantics must be extracted before the compatibility matrix marks an attribute as migrated.

## Important non-goals

The catalog does not pretend that naming an attribute implements its behavior. For example, `session_timeout` is only fully migrated when the value is consumed by the session/RADIUS path with IBSng-compatible semantics.

The same rule applies to IP pools, credit, multilogin, bandwidth accounting, caller-ID restrictions and VoIP attributes.

## Next parity work

1. Map each catalog entry to its A1.24 producer(s).
2. Map each entry to every A1.24 consumer/plugin.
3. Record storage representation and defaults.
4. Record inheritance and override behavior.
5. Record RADIUS attribute translation where applicable.
6. Implement behavior in ATD policy/session/protocol services.
7. Add fixture-based compatibility tests.
8. Only then mark the attribute as `migrated` in the master compatibility matrix.
