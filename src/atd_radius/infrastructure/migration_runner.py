"""Explicit, checksum-verified PostgreSQL migration runner.

This command is intentionally never invoked at application startup. It is for
operator-controlled clean installs; existing IBSng databases require a reviewed
adoption/import plan and are refused rather than silently initialized over.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Protocol


_MIGRATION_FILE = re.compile(r"^(?P<version>[0-9]{3,})_(?P<name>[a-z0-9_]+)\.sql$")
_LOCK_KEY = 0x4154445241444955  # stable, project-specific PostgreSQL advisory-lock key


class MigrationError(RuntimeError):
    """Raised when the migration set or database state is unsafe."""


class Connection(Protocol):
    def execute(self, query: str, params=()): ...
    def transaction(self): ...


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    checksum: str
    sql: str


@dataclass(frozen=True, slots=True)
class MigrationResult:
    applied: tuple[str, ...]
    pending: tuple[str, ...]
    checksums_ok: bool = True


def discover_migrations(directory: str | Path) -> tuple[Migration, ...]:
    root = Path(directory)
    if not root.is_dir():
        raise MigrationError(f"migration directory does not exist: {root}")
    found: list[Migration] = []
    seen: set[int] = set()
    for path in sorted(root.glob("*.sql")):
        match = _MIGRATION_FILE.fullmatch(path.name)
        if not match:
            raise MigrationError(f"invalid migration filename: {path.name}")
        version = int(match.group("version"))
        if version in seen:
            raise MigrationError(f"duplicate migration version: {version}")
        seen.add(version)
        try:
            sql = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise MigrationError(f"cannot read migration: {path.name}") from exc
        if not sql.strip():
            raise MigrationError(f"empty migration: {path.name}")
        found.append(Migration(
            version=version,
            name=path.name,
            checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
            sql=sql,
        ))
    if not found:
        raise MigrationError(f"no migrations found in {root}")
    versions = [item.version for item in found]
    expected = list(range(versions[0], versions[-1] + 1))
    if versions != expected:
        raise MigrationError(f"migration versions must be contiguous; found {versions}")
    if versions[0] != 1:
        raise MigrationError(f"clean-install migrations must begin at 001; found {versions[0]:03d}")
    return tuple(found)


def run_migrations(
    conn: Connection,
    directory: str | Path,
    *,
    apply: bool = False,
) -> MigrationResult:
    """Inspect migration state and optionally apply all pending migrations atomically.

    The checksum ledger and every migration run in one transaction. A failure
    rolls the whole batch back. An untracked, non-empty database is never
    adopted automatically.
    """
    migrations = discover_migrations(directory)
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
        ledger_exists = conn.execute(
            "SELECT to_regclass('public.atd_schema_migrations')"
        ).fetchone()[0] is not None

        if not ledger_exists:
            has_tables = bool(conn.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_type='BASE TABLE')"
            ).fetchone()[0])
            if has_tables:
                raise MigrationError(
                    "database already contains tables but has no ATD migration ledger; "
                    "refusing automatic adoption. Use the reviewed A1.24 import/adoption workflow."
                )
            if apply:
                conn.execute(
                    "CREATE TABLE public.atd_schema_migrations ("
                    "version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, "
                    "checksum CHAR(64) NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP)"
                )
            existing: dict[int, tuple[str, str]] = {}
        else:
            rows = conn.execute(
                "SELECT version, name, checksum FROM public.atd_schema_migrations ORDER BY version"
            ).fetchall()
            existing = {int(version): (str(name), str(checksum).strip()) for version, name, checksum in rows}

        by_version = {item.version: item for item in migrations}
        unknown = sorted(set(existing) - set(by_version))
        if unknown:
            raise MigrationError(f"database records migrations missing from this release: {unknown}")

        for version, (name, checksum) in existing.items():
            item = by_version[version]
            if name != item.name or checksum != item.checksum:
                raise MigrationError(
                    f"checksum/name drift for migration {version:03d}: "
                    f"database has {name} ({checksum}), release has {item.name} ({item.checksum})"
                )

        pending = tuple(item for item in migrations if item.version not in existing)
        if not apply:
            return MigrationResult(
                applied=tuple(existing[v][0] for v in sorted(existing)),
                pending=tuple(item.name for item in pending),
            )

        for item in pending:
            conn.execute(item.sql)
            conn.execute(
                "INSERT INTO public.atd_schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                (item.version, item.name, item.checksum),
            )
        return MigrationResult(
            applied=tuple([existing[v][0] for v in sorted(existing)] + [item.name for item in pending]),
            pending=(),
        )
