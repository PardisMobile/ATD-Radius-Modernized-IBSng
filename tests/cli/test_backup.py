from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from atd_radius.cli import backup


def test_verify_backup_checks_manifest_digest_and_archive_listing(tmp_path, monkeypatch):
    archive = tmp_path / "db.dump"
    archive.write_bytes(b"valid fixture archive")
    (tmp_path / "db.dump.json").write_text(json.dumps({
        "format": "postgresql-custom",
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "size_bytes": archive.stat().st_size,
    }), encoding="utf-8")
    calls = []
    monkeypatch.setattr(backup, "_tool", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(backup, "_run", lambda args, **kwargs: calls.append(args))
    result = backup.verify_backup(archive)
    assert result["verified"] is True
    assert calls == [["/usr/bin/pg_restore", "--list", str(archive)]]


def test_verify_backup_rejects_modified_archive(tmp_path, monkeypatch):
    archive = tmp_path / "db.dump"
    archive.write_bytes(b"changed")
    (tmp_path / "db.dump.json").write_text(json.dumps({
        "format": "postgresql-custom", "sha256": "0" * 64, "size_bytes": archive.stat().st_size,
    }), encoding="utf-8")
    monkeypatch.setattr(backup, "_tool", lambda name: f"/usr/bin/{name}")
    with pytest.raises(backup.BackupError, match="checksum"):
        backup.verify_backup(archive)


def test_restore_requires_exact_configured_database_confirmation(monkeypatch, tmp_path):
    archive = tmp_path / "db.dump"
    archive.write_bytes(b"not used")
    monkeypatch.setattr(backup.settings, "database_url", "postgresql://user:secret@localhost/production_db")
    monkeypatch.setattr(backup, "verify_backup", lambda path: {"verified": True})
    monkeypatch.setattr(backup, "_run", lambda args, **kwargs: pytest.fail("must not invoke pg_restore"))
    with pytest.raises(backup.BackupError, match="exactly match"):
        backup.restore_backup(archive, "production")


def test_create_backup_refuses_overwrite_before_running_tools(tmp_path, monkeypatch):
    archive = tmp_path / "existing.dump"
    archive.write_bytes(b"preserve")
    monkeypatch.setattr(backup, "_run", lambda args, **kwargs: pytest.fail("must not invoke pg_dump"))
    with pytest.raises(backup.BackupError, match="overwrite"):
        backup.create_backup(archive)
    assert archive.read_bytes() == b"preserve"


def test_connection_credentials_are_scoped_to_child_environment(monkeypatch):
    monkeypatch.setattr(
        backup.settings,
        "database_url",
        "postgresql://backup_user:top-secret@db.example:5544/aaa?sslmode=require",
    )
    monkeypatch.delenv("PGPASSWORD", raising=False)
    env = backup._connection_env()
    assert env["PGHOST"] == "db.example"
    assert env["PGPORT"] == "5544"
    assert env["PGUSER"] == "backup_user"
    assert env["PGPASSWORD"] == "top-secret"
    assert env["PGSSLMODE"] == "require"
    import os
    assert "PGPASSWORD" not in os.environ


def test_create_backup_validates_then_atomically_publishes_archive(tmp_path, monkeypatch):
    output = tmp_path / "new.dump"
    invocations = []
    monkeypatch.setattr(backup, "_tool", lambda name: f"/usr/bin/{name}")

    def fake_run(args, *, env=None):
        invocations.append((args, env))
        if args[0].endswith("pg_dump"):
            target = Path(args[args.index("--file") + 1])
            target.write_bytes(b"custom archive fixture")
        return None

    monkeypatch.setattr(backup, "_run", fake_run)
    result = backup.create_backup(output)
    assert output.read_bytes() == b"custom archive fixture"
    assert result["verified_archive_listing"] is True
    assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert output.with_suffix(".dump.json").is_file()
    assert len(invocations) == 2
    assert invocations[0][0][1] == "--format=custom"
    assert invocations[1][0][1] == "--list"


def test_restore_invokes_pg_restore_only_after_verified_confirmation(tmp_path, monkeypatch):
    archive = tmp_path / "backup.dump"
    archive.write_bytes(b"fixture")
    monkeypatch.setattr(backup.settings, "database_url", "postgresql://user:pw@localhost/production_db")
    monkeypatch.setattr(backup, "verify_backup", lambda path: {"verified": True})
    monkeypatch.setattr(backup, "_tool", lambda name: f"/usr/bin/{name}")
    seen = {}
    monkeypatch.setattr(backup, "_run", lambda args, **kwargs: seen.update(args=args, kwargs=kwargs))
    result = backup.restore_backup(archive, "production_db")
    assert result["restored"] is True
    assert seen["args"] == [
        "/usr/bin/pg_restore", "--exit-on-error", "--no-owner", "--no-privileges",
        "--clean", "--if-exists", "--dbname", "production_db", str(archive),
    ]
    assert seen["kwargs"]["env"]["PGPASSWORD"] == "pw"
