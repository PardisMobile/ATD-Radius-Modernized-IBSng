"""Real PostgreSQL backup/restore round-trip acceptance test."""
from __future__ import annotations

import os
import shutil
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from atd_radius.cli import backup


@pytest.fixture
def backup_databases():
    base_dsn = os.environ.get("ATD_TEST_DATABASE_URL")
    if not base_dsn:
        pytest.skip("ATD_TEST_DATABASE_URL is required for PostgreSQL backup acceptance")
    if not shutil.which("pg_dump") or not shutil.which("pg_restore"):
        pytest.skip("pg_dump and pg_restore are required for PostgreSQL backup acceptance")
    # Newer PostgreSQL client archives can contain SET commands unsupported by
    # older servers (for example transaction_timeout on PostgreSQL < 17).
    with psycopg.connect(base_dsn) as version_conn:
        server_major = version_conn.execute("SHOW server_version").fetchone()[0].split(".")[0]
    restore_version = shutil.which("pg_restore")
    version_output = __import__("subprocess").run(
        [restore_version, "--version"], check=True, capture_output=True, text=True
    ).stdout
    client_major = version_output.split()[-1].split(".")[0]
    if int(client_major) > int(server_major):
        pytest.skip(
            f"pg_restore {client_major} archive compatibility is not guaranteed on "
            f"PostgreSQL {server_major}; use matching major-version client tools"
        )
    suffix = uuid.uuid4().hex[:10]
    source_name = "atd_bksrc_" + suffix
    target_name = "atd_bktgt_" + suffix
    admin_dsn = make_conninfo(base_dsn, dbname="postgres")
    source_dsn = make_conninfo(base_dsn, dbname=source_name)
    target_dsn = make_conninfo(base_dsn, dbname=target_name)
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(source_name)))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_name)))
    try:
        yield source_name, source_dsn, target_name, target_dsn
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            for name in (source_name, target_name):
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid <> pg_backend_pid()",
                    (name,),
                )
                admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


def test_backup_restore_round_trip_preserves_schema_and_rows(backup_databases, tmp_path, monkeypatch):
    source_name, source_dsn, target_name, target_dsn = backup_databases
    with psycopg.connect(source_dsn) as source:
        source.execute("CREATE TABLE backup_acceptance (id BIGINT PRIMARY KEY, payload TEXT NOT NULL)")
        source.execute("INSERT INTO backup_acceptance VALUES (1, 'one'), (9, 'nine')")
    monkeypatch.setattr(backup.settings, "database_url", source_dsn)
    archive = tmp_path / "acceptance.dump"
    manifest = backup.create_backup(archive)
    assert manifest["verified_archive_listing"] is True
    assert backup.verify_backup(archive)["verified"] is True

    monkeypatch.setattr(backup.settings, "database_url", target_dsn)
    restored = backup.restore_backup(archive, target_name)
    assert restored["restored"] is True
    with psycopg.connect(target_dsn) as target:
        rows = target.execute(
            "SELECT id, payload FROM backup_acceptance ORDER BY id"
        ).fetchall()
        assert rows == [(1, "one"), (9, "nine")]
