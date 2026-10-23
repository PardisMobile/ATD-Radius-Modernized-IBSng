from contextlib import contextmanager
from pathlib import Path

import pytest

from atd_radius.infrastructure.migration_runner import (
    MigrationError,
    discover_migrations,
    run_migrations,
)


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, *, existing_tables=False, fail_on=None):
        self.ledger_exists = False
        self.ledger = []
        self.existing_tables = existing_tables
        self.executed_sql = []
        self.fail_on = fail_on

    @contextmanager
    def transaction(self):
        before = (
            self.ledger_exists,
            list(self.ledger),
            list(self.executed_sql),
        )
        try:
            yield
        except Exception:
            self.ledger_exists, self.ledger, self.executed_sql = before
            raise

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        if "pg_advisory_xact_lock" in normalized:
            return Result([])
        if "to_regclass('public.atd_schema_migrations')" in normalized:
            return Result([("atd_schema_migrations",)] if self.ledger_exists else [(None,)])
        if "FROM information_schema.tables" in normalized:
            return Result([(self.existing_tables,)])
        if normalized.startswith("CREATE TABLE public.atd_schema_migrations"):
            self.ledger_exists = True
            return Result([])
        if normalized.startswith("SELECT version, name, checksum FROM public.atd_schema_migrations"):
            return Result(sorted(self.ledger, key=lambda row: row[0]))
        if normalized.startswith("INSERT INTO public.atd_schema_migrations"):
            self.ledger.append(tuple(params))
            return Result([])
        if self.fail_on and self.fail_on in query:
            raise RuntimeError("simulated migration failure")
        self.executed_sql.append(query)
        return Result([])


def write_migrations(root: Path, *items: tuple[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name, sql in items:
        (root / name).write_text(sql, encoding="utf-8")
    return root


def test_discovery_hashes_and_orders_migrations(tmp_path):
    root = write_migrations(tmp_path / "migrations",
        ("002_defs.sql", "SELECT 2;"),
        ("001_initial.sql", "SELECT 1;"),
    )
    found = discover_migrations(root)
    assert [item.name for item in found] == ["001_initial.sql", "002_defs.sql"]
    assert len(found[0].checksum) == 64
    assert found[0].checksum != found[1].checksum


def test_discovery_rejects_gaps_duplicate_versions_and_empty_files(tmp_path):
    root = write_migrations(tmp_path / "gap", ("001_initial.sql", "SELECT 1;"), ("003_defs.sql", "SELECT 3;"))
    with pytest.raises(MigrationError, match="contiguous"):
        discover_migrations(root)

    root = write_migrations(tmp_path / "duplicate", ("001_first.sql", "SELECT 1;"), ("001_second.sql", "SELECT 2;"))
    with pytest.raises(MigrationError, match="duplicate migration version"):
        discover_migrations(root)

    root = write_migrations(tmp_path / "empty", ("001_initial.sql", "  "))
    with pytest.raises(MigrationError, match="empty migration"):
        discover_migrations(root)


def test_dry_run_does_not_mutate_an_empty_database(tmp_path):
    root = write_migrations(tmp_path / "migrations", ("001_initial.sql", "SELECT 1;"))
    conn = FakeConnection()
    result = run_migrations(conn, root, apply=False)
    assert result.applied == ()
    assert result.pending == ("001_initial.sql",)
    assert conn.ledger_exists is False
    assert conn.executed_sql == []


def test_apply_records_checksum_and_second_run_is_idempotent(tmp_path):
    root = write_migrations(tmp_path / "migrations",
        ("001_initial.sql", "SELECT 1;"),
        ("002_defs.sql", "SELECT 2;"),
    )
    conn = FakeConnection()
    first = run_migrations(conn, root, apply=True)
    assert first.applied == ("001_initial.sql", "002_defs.sql")
    assert first.pending == ()
    assert [row[1] for row in conn.ledger] == ["001_initial.sql", "002_defs.sql"]
    assert len(conn.executed_sql) == 2

    second = run_migrations(conn, root, apply=True)
    assert second.applied == first.applied
    assert second.pending == ()
    assert len(conn.executed_sql) == 2


def test_checksum_drift_fails_before_running_new_sql(tmp_path):
    root = write_migrations(tmp_path / "migrations", ("001_initial.sql", "SELECT 1;"))
    conn = FakeConnection()
    run_migrations(conn, root, apply=True)
    (root / "001_initial.sql").write_text("SELECT 99;", encoding="utf-8")
    with pytest.raises(MigrationError, match="checksum/name drift"):
        run_migrations(conn, root, apply=True)
    assert len(conn.executed_sql) == 1


def test_untracked_existing_database_is_refused_without_mutation(tmp_path):
    root = write_migrations(tmp_path / "migrations", ("001_initial.sql", "SELECT 1;"))
    conn = FakeConnection(existing_tables=True)
    with pytest.raises(MigrationError, match="refusing automatic adoption"):
        run_migrations(conn, root, apply=True)
    assert conn.ledger_exists is False
    assert conn.executed_sql == []



def test_empty_ledger_with_application_tables_fails_closed(tmp_path):
    root = write_migrations(tmp_path / "migrations", ("001_initial.sql", "SELECT 1;"))
    conn = FakeConnection(existing_tables=True)
    conn.ledger_exists = True
    with pytest.raises(MigrationError, match="ledger exists but is empty"):
        run_migrations(conn, root, apply=True)
    assert conn.executed_sql == []
    assert conn.ledger == []


def test_gapped_ledger_fails_closed_before_replaying_migrations(tmp_path):
    root = write_migrations(tmp_path / "migrations",
        ("001_initial.sql", "SELECT 1;"),
        ("002_defs.sql", "SELECT 2;"),
        ("003_rules.sql", "SELECT 3;"),
    )
    conn = FakeConnection()
    run_migrations(conn, root, apply=True)
    # Simulate ledger damage: migration 003 remains recorded while 002 is missing.
    conn.ledger = [row for row in conn.ledger if row[0] != 2]
    executed_before = list(conn.executed_sql)

    with pytest.raises(MigrationError, match="not a contiguous prefix"):
        run_migrations(conn, root, apply=True)

    assert conn.executed_sql == executed_before
    assert [row[0] for row in conn.ledger] == [1, 3]


def test_failed_migration_rolls_back_ledger_and_earlier_migration(tmp_path):
    root = write_migrations(tmp_path / "migrations",
        ("001_initial.sql", "SELECT 1;"),
        ("002_broken.sql", "SELECT BROKEN;"),
    )
    conn = FakeConnection(fail_on="BROKEN")
    with pytest.raises(RuntimeError, match="simulated migration failure"):
        run_migrations(conn, root, apply=True)
    assert conn.ledger_exists is False
    assert conn.ledger == []
    assert conn.executed_sql == []
