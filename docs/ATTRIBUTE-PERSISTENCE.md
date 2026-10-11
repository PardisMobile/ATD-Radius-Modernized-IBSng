# Attribute Persistence Boundary

ATD keeps the IBSng attribute system independent from fixed domain columns.

The repository contract supports:

- arbitrary attribute names
- string-preserving source values
- multiple values for one attribute
- stable owner type/id
- deterministic position for ordered values

This is the first persistence boundary, not the final PostgreSQL adapter. The PostgreSQL implementation must map the real A1.24 `user_attrs`, `group_attrs` and `ras_attrs` structures without losing fields or changing multiplicity.

## Rule

Do not replace this with a generic JSON blob. The compatibility adapter must retain enough structure to reproduce A1.24 lookup, inheritance, update and delete behavior and must remain auditable during migration.
