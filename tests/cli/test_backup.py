from __future__ import annotations

import hashlib
import json

import pytest

from atd_radius.cli import backup


def test_verify_backup_checks_manifest_digest_and_archive_listing(tmp_path, monkeypatch):
    archive = tmp_path / "db.dump"
    archive.write_bytes(b"valid fixture archive")
    (tmp_path / "db.dump.json").write_text(json.dumps({
        "format": "postgresql-custom",
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
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
        "format": "postgresql-custom", "sha256": "0" * 64,
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
