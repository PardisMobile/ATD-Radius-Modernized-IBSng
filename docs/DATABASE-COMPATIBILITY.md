# Database Compatibility Strategy

ATD must preserve the operational semantics of IBSng A1.24 data. Database modernization is **lossless-first**, not redesign-first.

## Compatibility levels

1. **Native** — an IBSng table/column can remain structurally compatible.
2. **Mapped** — ATD uses a modern table/model but every source field has an explicit mapping.
3. **Transformed** — a transformation is required; it must be deterministic and reversible where practical.
4. **Unsupported** — prohibited until an explicit compatibility decision is documented.

No IBSng table is considered safely migrated until its rows, relationships, defaults, constraints and behavioral consumers are mapped.

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

The domain layer already contains `User`, `Group`, `Service`, `Ras`, `IPPool`, `Session` and `AccountingEvent` concepts, but this document deliberately does **not** claim database migration is complete. The next database milestone must be based on the actual A1.24 schema and backup/restore code, not inferred table names.

## Rule

A successful SQL restore is not sufficient evidence of compatibility. ATD must produce a parity report after import and identify every source field that has no consumer.
