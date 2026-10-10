# IBSng A1.24 → ATD Attribute System Parity

## Purpose

The attribute system is a compatibility boundary, not a convenience key/value store. ATD must preserve IBSng attribute behavior and every plugin/consumer while moving the implementation to modern Python.

## Current A1.24 source families

The migration inventory covers these attribute producers and consumers:

- user attributes: `user_attrs`
- group attributes: `group_attrs`
- RAS attributes: `ras_attrs`
- service/policy attributes where supplied by A1.24 service/plugin code
- default/system attributes
- authentication and credential policy
- session/RADIUS attributes
- accounting/bandwidth attributes
- IP allocation attributes
- charging attributes
- plugin-defined/custom attributes

## Attribute catalog

`src/atd_radius/domain/attribute_catalog.py` is the machine-readable catalog for names evidenced by the A1.24 attribute update path. Each entry records the stable IBSng name, conservative value type, multiplicity, operators, source/behavior area, consumer boundary, explicit RADIUS mapping where known, and migration status.

A catalog entry is **not** equivalent to implemented behavior. It may only become `migrated` after its A1.24 consumer behavior is implemented and covered by a compatibility fixture.

## Resolver contract

The ATD resolver preserves:

- scope/provenance
- deterministic precedence
- typed values
- multi-valued attributes
- explicit SET/ADD/REMOVE/REPLACE operations
- explainability for UI and audit

The current resolver scope order is:

`SYSTEM → RAS → SERVICE → GROUP → USER`

This is an implementation baseline, not a final IBSng parity claim. A1.24 plugin-specific precedence and merge rules must be verified from source before affected attributes are marked migrated.

## Compatibility rules

1. Unknown/custom attributes must remain representable.
2. Multi-valued attributes must not be silently collapsed into one scalar.
3. Attribute provenance must remain available for diagnostics and UI.
4. Protocol adapters must consume the resolved policy rather than implement their own precedence.
5. Database mapping must preserve the original attribute name/value semantics.
6. A name is never considered migrated merely because it exists in the catalog.

## Verification workflow

For every attribute family:

```text
A1.24 producer
    ↓
A1.24 storage/defaults
    ↓
A1.24 consumer/plugin
    ↓
ATD repository
    ↓
ATD resolver/policy
    ↓
RADIUS/session/accounting/billing consumer
    ↓
compatibility fixture
```

Only a passing fixture permits `Verified` status.

## Current mutation boundary

ATD now has a source-derived mutation slice for the A1.24 generic comment plugin family: `name`, `comment`, and `phone`. It uses the native `CHANGE USER ATTRIBUTES` permission/owner scope, row-locks the target, preserves `USER_AUDIT_LOG` and `_NOVALUE_` semantics, and rejects all attributes that require specialized handlers. This does not yet provide full `user_attrs` lifecycle parity.

## Next implementation boundary

Continue by implementing specialized user-attribute handlers one family at a time, including each source `checkInput`, persistence/query builder, runtime broadcast or `postUpdate`, and compatibility fixture. Do not expose `multi_login`, `lock`, credentials, caller-ID, IP-pool, charging, expiry, or `radius_attrs` through the generic endpoint until those exact source contracts are implemented. Then extend repository-backed resolution and fixtures to group/RAS attributes.
