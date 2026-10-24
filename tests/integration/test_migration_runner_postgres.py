"""Real PostgreSQL acceptance test for the clean-install migration runner."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from atd_radius.infrastructure.migration_runner import MigrationError, run_migrations


@pytest.fixture
def isolated_migration_database(tmp_path):
    base_dsn = os.environ.get("ATD_TEST_DATABASE_URL")
    if not base_dsn:
        pytest.skip("ATD_TEST_DATABASE_URL is required for PostgreSQL migration acceptance")
    database_name = "atd_migrate_" + uuid.uuid4().hex[:16]
    admin_dsn = make_conninfo(base_dsn, dbname="postgres")
    target_dsn = make_conninfo(base_dsn, dbname=database_name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        yield target_dsn, tmp_path
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name)))


def test_real_postgres_clean_install_is_idempotent_and_failed_migration_rolls_back(
    isolated_migration_database,
):
    target_dsn, tmp_path = isolated_migration_database
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"

    with psycopg.connect(target_dsn) as conn:
        first = run_migrations(conn, migrations_dir, apply=True)
        assert len(first.applied) == 8
        assert first.pending == ()
        assert conn.execute(
            "SELECT count(*) FROM public.atd_schema_migrations"
        ).fetchone()[0] == 8
        assert conn.execute("SELECT to_regclass('public.admins')").fetchone()[0] is not None
        assert conn.execute("SELECT to_regclass('public.operational_audit_events')").fetchone()[0] is not None
        assert conn.execute("SELECT to_regclass('public.atd_radius_live_sessions')").fetchone()[0] is not None

        second = run_migrations(conn, migrations_dir, apply=True)
        assert second.applied == first.applied
        assert second.pending == ()

        changed_migrations = tmp_path / "changed-migrations"
        shutil.copytree(migrations_dir, changed_migrations)
        (changed_migrations / "009_test_rollback.sql").write_text(
            "CREATE TABLE public.should_rollback (id INTEGER);\n"
            "SELECT * FROM public.atd_migration_table_that_does_not_exist;\n",
            encoding="utf-8",
        )
        with pytest.raises(psycopg.Error):
            run_migrations(conn, changed_migrations, apply=True)

        assert conn.execute("SELECT to_regclass('public.should_rollback')").fetchone()[0] is None
        assert conn.execute(
            "SELECT count(*) FROM public.atd_schema_migrations"
        ).fetchone()[0] == 8



def test_real_postgres_gapped_ledger_refuses_to_replay_missing_migration(
    isolated_migration_database,
):
    target_dsn, _ = isolated_migration_database
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"

    with psycopg.connect(target_dsn) as conn:
        run_migrations(conn, migrations_dir, apply=True)
        conn.execute("DELETE FROM public.atd_schema_migrations WHERE version = 4")

        with pytest.raises(MigrationError, match="not a contiguous prefix"):
            run_migrations(conn, migrations_dir, apply=True)

        # The migration SQL was not replayed and the existing schema remains intact.
        assert conn.execute(
            "SELECT count(*) FROM public.atd_schema_migrations"
        ).fetchone()[0] == 7
        assert conn.execute("SELECT to_regclass('public.admins')").fetchone()[0] is not None
        assert conn.execute("SELECT to_regclass('public.atd_radius_live_sessions')").fetchone()[0] is not None



def test_real_postgres_empty_ledger_on_populated_schema_refuses_clean_install(
    isolated_migration_database,
):
    target_dsn, _ = isolated_migration_database
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"

    with psycopg.connect(target_dsn) as conn:
        run_migrations(conn, migrations_dir, apply=True)
        conn.execute("DELETE FROM public.atd_schema_migrations")

        with pytest.raises(MigrationError, match="ledger exists but is empty"):
            run_migrations(conn, migrations_dir, apply=True)

        assert conn.execute(
            "SELECT count(*) FROM public.atd_schema_migrations"
        ).fetchone()[0] == 0
        assert conn.execute("SELECT to_regclass('public.admins')").fetchone()[0] is not None
"""Real PostgreSQL acceptance test for the clean-install migration runner."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from atd_radius.infrastructure.migration_runner import run_migrations


@pytest.fixture
def isolated_migration_database(tmp_path):
    base_dsn = os.environ.get("ATD_TEST_DATABASE_URL")
    if not base_dsn:
        pytest.skip("ATD_TEST_DATABASE_URL is required for PostgreSQL migration acceptance")
    database_name = "atd_migrate_" + uuid.uuid4().hex[:16]
    admin_dsn = make_conninfo(base_dsn, dbname="postgres")
    target_dsn = make_conninfo(base_dsn, dbname=database_name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    try:
        yield target_dsn, tmp_path
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database_name)))


def test_real_postgres_clean_install_is_idempotent_and_failed_migration_rolls_back(
    isolated_migration_database,
):
    target_dsn, tmp_path = isolated_migration_database
    migrations_dir = Path(__file__).resolve().parents[2] / "migrations"

    with psycopg.connect(target_dsn) as conn:
        first = run_migrations(conn, migrations_dir, apply=True)
        assert len(first.applied) == 9
        assert first.pending == ()
        assert conn.execute(
            "SELECT count(*) FROM public.atd_schema_migrations"
        ).fetchone()[0] == 9
        assert conn.execute("SELECT to_regclass('public.admins')").fetchone()[0] is not None
        assert conn.execute("SELECT to_regclass('public.operational_audit_events')").fetchone()[0] is not None
        assert conn.execute("SELECT to_regclass('public.atd_radius_live_sessions')").fetchone()[0] is not None
        assert conn.execute("SELECT to_regclass('public.atd_radius_mailbox_cleanup')").fetchone()[0] is not None

        from atd_radius.infrastructure.mailbox_cleanup import MailboxCleanupRepository

        mailbox = MailboxCleanupRepository(conn)
        job_id = mailbox.enqueue(987654, "integration@example.test")
        conn.commit()
        claimed = mailbox.claim_batch(limit=1)
        assert len(claimed) == 1
        assert claimed[0].job_id == job_id
        assert claimed[0].attempts == 1
        mailbox.finish(job_id, success=False, error="simulated retry")
        conn.commit()
        status, attempts = conn.execute(
            "SELECT status, attempts FROM atd_radius_mailbox_cleanup WHERE job_id=%s", (job_id,)
        ).fetchone()
        assert (status, attempts) == ("failed", 1)
        retry = mailbox.claim_batch(limit=1)
        assert len(retry) == 1
        assert retry[0].job_id == job_id
        assert retry[0].attempts == 2
        mailbox.finish(job_id, success=True)
        conn.commit()
        status, attempts = conn.execute(
            "SELECT status, attempts FROM atd_radius_mailbox_cleanup WHERE job_id=%s", (job_id,)
        ).fetchone()
        assert (status, attempts) == ("succeeded", 2)


        second = run_migrations(conn, migrations_dir, apply=True)
        assert second.applied == first.applied
        assert second.pending == ()

        changed_migrations = tmp_path / "changed-migrations"
        shutil.copytree(migrations_dir, changed_migrations)
        (changed_migrations / "010_test_rollback.sql").write_text(
            "CREATE TABLE public.should_rollback (id INTEGER);\n"
            "SELECT * FROM public.atd_migration_table_that_does_not_exist;\n",
            encoding="utf-8",
        )
        with pytest.raises(psycopg.Error):
            run_migrations(conn, changed_migrations, apply=True)

        assert conn.execute("SELECT to_regclass('public.should_rollback')").fetchone()[0] is None
        assert conn.execute(
            "SELECT count(*) FROM public.atd_schema_migrations"
        ).fetchone()[0] == 9
