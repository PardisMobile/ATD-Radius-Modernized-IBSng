"""Command-line entry point for explicit ATD database migrations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import psycopg

from atd_radius.config import settings
from atd_radius.infrastructure.migration_runner import MigrationError, run_migrations


def _default_migrations_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "migrations"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="atd-radius-migrate",
        description="Check or apply the numbered ATD PostgreSQL migrations.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check ledger/checksums; exit 1 if migrations are pending")
    mode.add_argument("--dry-run", action="store_true", help="show pending migrations without changing the database")
    parser.add_argument(
        "--migrations-dir", type=Path, default=_default_migrations_dir(),
        help="directory containing numbered SQL migration files",
    )
    args = parser.parse_args(argv)

    try:
        with psycopg.connect(settings.database_url) as conn:
            result = run_migrations(conn, args.migrations_dir, apply=not (args.check or args.dry_run))
    except (MigrationError, psycopg.Error, OSError) as exc:
        print(f"migration error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "applied": list(result.applied),
        "pending": list(result.pending),
        "mode": "check" if args.check else "dry-run" if args.dry_run else "apply",
    }, indent=2))
    if args.check and result.pending:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
