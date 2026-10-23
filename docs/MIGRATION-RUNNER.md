# Database migration runner

The numbered SQL files in `migrations/` are the only automatically applied schema history. The runner is explicit and is **not** called from API or RADIUS startup.

## Commands

After installing the package and configuring `ATD_DATABASE_URL`:

- `atd-radius-migrate --check` verifies the migration ledger and SHA-256 checksums; exits 1 if work is pending.
- `atd-radius-migrate --dry-run` prints applied and pending migrations without changing the database.
- `atd-radius-migrate` applies every pending migration in order.

The default path is the package checkout's `migrations/` directory. `--migrations-dir` can select a reviewed alternate directory. Keep migration SQL immutable after it has been applied; create a new numbered migration for changes.

## Safety behavior

- Acquires a PostgreSQL transaction-scoped advisory lock so two operators cannot apply the same migration set concurrently.
- Uses a ledger with migration version, filename, SHA-256 checksum and timestamp.
- Verifies all recorded checksums before running pending migrations; changed or removed applied migrations fail closed.
- Requires the recorded versions to be a contiguous prefix beginning at `001`. A damaged ledger such as `001, 003` is rejected instead of replaying migration `002` against a later schema.
- Applies pending SQL and ledger entries in one transaction. Any failure rolls back the entire batch, including the ledger.
- Refuses to initialize an untracked database that already has public tables. This prevents accidentally running the clean-install schema on an existing IBSng installation.
- Refuses an empty migration ledger if application tables already exist, and rejects a ledger with missing middle versions. Neither state is treated as a clean install.
- Does not automatically migrate or adopt a production A1.24 database. That requires the separately reviewed lossless import/adoption workflow and a verified backup/restore.

## Operational sequence

1. Take and verify a restorable PostgreSQL backup.
2. Review the target database name and `ATD_DATABASE_URL`.
3. Run `atd-radius-migrate --check` and `atd-radius-migrate --dry-run`.
4. Apply during a controlled maintenance window.
5. Run the full PostgreSQL-backed test suite and the A1.24 schema parity audit.
6. Verify application startup, RADIUS authentication/accounting, admin login and rollback/restore procedure before production traffic.

The runner is a safe, explicit migration mechanism for clean installs; it is not a claim that data import, A1.24 adoption, rollback automation, or production restore parity is complete.
