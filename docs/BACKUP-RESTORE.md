# PostgreSQL backup and restore

`atd-radius-backup` is an operator-invoked backup tool. It uses PostgreSQL's `pg_dump` custom archive format and validates the archive with `pg_restore --list`. It writes a SHA-256 manifest beside the archive and refuses to overwrite an existing backup.

## Create and verify

```sh
atd-radius-backup create --output /secure/backups/atd-radius-$(date +%F-%H%M%S).dump
atd-radius-backup verify /secure/backups/atd-radius-YYYY-MM-DD-HHMMSS.dump
```

Keep both the `.dump` and its `.dump.json` manifest. Store backups off-host with restrictive permissions and encryption appropriate to your environment. A successful archive-list check verifies file integrity/structure, **not** that a restore will succeed or the application will behave correctly.

## Restore (destructive)

```sh
atd-radius-backup restore /secure/backups/atd-radius-YYYY-MM-DD-HHMMSS.dump --confirm-target atd_radius
```

Restore drops/replaces objects represented in the archive in the configured database. The confirmation string must exactly match the database name in `ATD_DATABASE_URL`. Stop application traffic first and take a separate backup of the target before restoring. The command does not create a database, restore cluster roles/tablespaces, or provide point-in-time recovery. Test restoration into an isolated database before production use.

The utility never runs automatically at startup. It requires the PostgreSQL client utilities (`pg_dump` and `pg_restore`) to be installed and compatible with the server version. A backup plus successful listing is not a substitute for a scheduled backup policy, off-site retention, or regular restore drills.
