# Operational audit event contract

This is an ATD-specific extension. It intentionally does not change the canonical IBSng A1.24 `user_audit_log`, which records attribute changes and is not a generic operational-event journal.

## Storage and transaction contract

Apply `migrations/004_operational_audit.sql` after the base A1.24 schema. The repository writes an append-only event with the authenticated administrator ID and username snapshot, action, outcome, optional target, remote address, request ID, and structured JSON details. Database constraints validate the outcome and bound the indexed/text fields.

The caller owns the transaction. For a privileged database mutation, insert the audit event in the same transaction and commit only after both statements succeed. If the external side effect is performed against a RAS, database atomicity cannot cover that device operation; record a truthful attempted/result outcome and do not imply cross-system atomicity.

## Safety boundary

- This repository is a persistence primitive, not administrator authentication or authorization.
- Do not pass a shared API bearer token as an administrator identity.
- Never include passwords, API tokens, RADIUS secrets, or other credentials in `details`.
- Privileged RAS disconnect routes remain unmounted until native admin identity, A1.24 permission evaluation/dependencies, trusted online-session resolution, and end-to-end audit sequencing are implemented.
- The migration and repository have unit-level coverage; they have not yet been validated against a live PostgreSQL deployment.
