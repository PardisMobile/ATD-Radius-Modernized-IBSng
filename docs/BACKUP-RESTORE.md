# INDEX-PARITY IMPORT GATE — 2026-10-26

Before any row writes, `atd-radius-a124-import` now compares every source/target index definition on tables being imported, including ordinary, unique, expression, partial and constraint-backed indexes. A missing, extra or differently defined index refuses the import before target mutation. This complements the existing column/key/constraint/rule/trigger/function/sequence gates; it does not create missing indexes or import DDL. Review and reconcile index drift with a reviewed migration, then rerun the dry-run.

# IMPORT OBJECT-PARITY GATE — 2026-10-25

Before row transfer, `atd-radius-a124-import` now compares source and target constraints, rules, triggers and trigger-function bodies, and checks that every source function/procedure definition has a matching target definition. Any mismatch stops the import. This is a refusal gate, not an object importer: the command does not copy DDL/functions/rules/triggers/roles. Resolve the drift through a reviewed migration before rerunning the import.

# A1.24 ROW IMPORT — 2026-10-25

For a live IBSng A1.24 PostgreSQL database, the new `atd-radius-a124-import` command first runs read-only checks and prints row counts. It does not restore a dump directly; restore an A1.24 backup into an isolated PostgreSQL source database first, then point `--source-dsn` at that restored database.

Dry-run (default), with a persistent audit report:

```sh
atd-radius-a124-import \
  --archive "Source of Truth/IBSng-A1.24.tar.bz2" \
  --source-dsn "$IBSNG_DATABASE_URL" \
  --target-dsn "$ATD_DATABASE_URL" \
  --report-file /secure/reports/a124-dry-run-2026-10-25.json
```

The JSON report records the UTC generation time, source/target database and server identity, canonical archive digest, ordered per-table source/target counts, key columns, and—after a successful apply—verified source rows, target-only rows preserved, inserted/updated counts, and per-sequence source/target high-water and restart values. Report files are created with owner-only permissions and are never overwritten; choose a new path for each run. Keep the report with the backup and change record. A dry-run report is planning evidence only; it is not proof of a completed import.

After reviewing the report, stopping writes to both databases, and taking verified backups of both, apply only with an explicit target name:

```sh
atd-radius-a124-import \
  --archive "Source of Truth/IBSng-A1.24.tar.bz2" \
  --source-dsn "$IBSNG_DATABASE_URL" \
  --target-dsn "$ATD_DATABASE_URL" \
  --apply --confirm-target atd_radius
```

The command transfers rows only. It requires the canonical 51-table A1.24 core to exist in the source, exact source/target column shape, compatible stable keys and sequences, and matching target tables for every source/plugin table. It merges by key, verifies row values after the merge, and preserves the higher source/target sequence high-water mark. It refuses unknown source tables, missing target tables, keyless tables, incompatible schema/sequence ownership, cross-table FK cycles and unorderable self-reference cycles. It does not delete target-only rows or import legacy DDL, functions, rules, triggers, roles or other database objects. This is not yet a full adoption/cutover workflow; a representative real-backup parity and restore drill remains mandatory.

Never point destructive migration tests at production. Stop source writes during the import so the source snapshot represents a planned maintenance window. Do not cut over until the complete parity report and rollback plan have been reviewed.

---

# PostgreSQL backup and restore

`atd-radius-backup` is an operator-invoked backup tool. It uses PostgreSQL's `pg_dump` custom archive format and validates the archive with `pg_restore --list`. It writes a SHA-256 manifest beside the archive and refuses to overwrite an existing backup. Both files are staged with private permissions and published without replacing paths that appear concurrently; a failed sidecar publication removes the archive created by that attempt.

## Create and verify

```sh
atd-radius-backup create --output /secure/backups/atd-radius-$(date +%F-%H%M%S).dump
atd-radius-backup verify /secure/backups/atd-radius-YYYY-MM-DD-HHMMSS.dump
```

Keep both the `.dump` and its `.dump.json` manifest. Verification checks the manifest's JSON structure, recorded filename, format, byte size, SHA-256 digest, and PostgreSQL archive listing. Store backups off-host with restrictive permissions and encryption appropriate to your environment. A successful archive-list check verifies file integrity/structure, **not** that a restore will succeed or the application will behave correctly.

## Restore (destructive)

```sh
atd-radius-backup restore /secure/backups/atd-radius-YYYY-MM-DD-HHMMSS.dump --confirm-target atd_radius
```

Restore drops/replaces objects represented in the archive in the configured database. The confirmation string must exactly match the database name in `ATD_DATABASE_URL`. Stop application traffic first and take a separate backup of the target before restoring. The command does not create a database, restore cluster roles/tablespaces, or provide point-in-time recovery. Test restoration into an isolated database before production use.

The utility never runs automatically at startup. It requires the PostgreSQL client utilities (`pg_dump` and `pg_restore`) to be installed and compatible with the server version. A backup plus successful listing is not a substitute for a scheduled backup policy, off-site retention, or regular restore drills.
