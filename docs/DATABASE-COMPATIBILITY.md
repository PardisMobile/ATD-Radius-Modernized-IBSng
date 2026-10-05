# Database Compatibility Strategy

ATD must preserve the operational semantics **and PostgreSQL schema of IBSng A1.24**. Database modernization is compatibility-first, not redesign-first.

## Compatibility levels

1. **Native** — the A1.24 table/column is retained directly.
2. **Mapped** — permitted only at an adapter/application boundary while the persisted PostgreSQL schema remains A1.24-compatible.
3. **Transformed** — permitted only for migration of external data; the resulting persisted representation must remain compatible with A1.24 semantics.
4. **Unsupported** — prohibited until an explicit compatibility decision is documented.

No IBSng table is considered compatible until its rows, relationships, defaults, constraints, indexes and behavioral consumers are verified against the A1.24 source.

## Restore workflow

```text
IBSng PostgreSQL backup
        |
        v
schema inventory
        |
        +--> native tables ----------+
        |                             |
        +--> mapped tables ----------+--> ATD import transaction
        |                             |
        +--> transformed data -------+
                                      |
                                      v
                              parity verification
                                      |
                                      v
                              imported ATD state
```

## Required parity checks

- row counts by logical entity
- primary-key/reference integrity
- usernames and credential records
- group/service relationships
- all user/group/service/RAS attributes
- IP pool membership and assignments
- session/accounting history
- charge/credit state
- administrative users and permissions
- indexes and uniqueness assumptions that affect behavior

## Current status

The migration layer now contains the native A1.24 schema: 51 tables, 24 sequences and 19 explicit indexes, followed by the A1.24 stored functions, initial data and definitions. Existing A1.24 tables, columns, constraints and relationships remain the database source of truth.

Runtime consumers are being refactored away from the previous parallel schema. No new replacement table is permitted. The next database milestone must be based on the actual A1.24 schema and backup/restore code, not inferred table names.

## Rule

A successful SQL restore is not sufficient evidence of compatibility. ATD must produce a parity report after import and identify every source field that has no consumer.
