# Attribute Persistence Boundary

ATD keeps the IBSng attribute system independent from fixed domain columns, but the persisted representation must follow the native A1.24 schema rather than inventing a generic multi-row contract.

## Native A1.24 mapping

- `user_attrs`, `group_attrs` and `ras_attrs` are keyed by owner plus attribute name; the schema does not represent arbitrary repeated values as multiple rows with the same owner/name key.
- Attribute-specific multiplicity or structure must be preserved using the exact A1.24 plugin representation and parsing rules (for example, an attribute value may encode a list), not by assuming repeated generic rows.
- Owner identity and the native attribute name/value semantics must survive lookup, inheritance, update, deletion and migration.
- Native special updaters (such as user group reassignment, caller ID, and other plugin-owned side effects) must not be treated as ordinary writes to generic attribute tables.

## Rule

Do not replace this with a generic JSON blob or a replacement schema. The compatibility adapter must retain enough structure to reproduce A1.24 lookup, inheritance, update and delete behavior and remain auditable during migration.

This describes the storage boundary only; it does not claim that every A1.24 plugin or multi-value encoding is already implemented.
