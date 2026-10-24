from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from atd_radius.infrastructure.mailbox_cleanup import (
    MailboxCleanupRepository,
    _safe_username,
    _validate_command,
    process_pending_mailbox_cleanup,
)


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.calls = []
        self.commits = 0

    @contextmanager
    def transaction(self):
        yield

    def execute(self, sql, params=()):
        self.calls.append((" ".join(sql.split()), params))
        if "RETURNING jobs.job_id" in sql:
            return Result(self.rows)
        if "RETURNING job_id" in sql:
            return Result([(42,)])
        return Result()

    def commit(self):
        self.commits += 1


def test_enqueue_persists_job_without_requiring_user_row():
    conn = Connection()
    assert MailboxCleanupRepository(conn).enqueue(7, "alice@example.test") == 42
    assert conn.calls[0][1] == (7, "alice@example.test")
    assert "INSERT INTO atd_radius_mailbox_cleanup" in conn.calls[0][0]


def test_worker_invokes_configured_executable_without_shell(tmp_path, monkeypatch):
    executable = tmp_path / "cleanup"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    conn = Connection([(9, 7, "alice@example.test", 1)])
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return Mock(returncode=0)

    monkeypatch.setattr("atd_radius.infrastructure.mailbox_cleanup.subprocess.run", fake_run)
    assert process_pending_mailbox_cleanup(conn, str(executable)) == (1, 0)
    assert calls[0][0] == [str(executable), "alice@example.test"]
    assert calls[0][1]["shell"] is False
    assert conn.commits == 1
    assert any("SET status='running'" in sql for sql, _ in conn.calls)
    assert any("SET status=%s" in sql for sql, _ in conn.calls)


def test_worker_records_failed_exit_and_retries_are_eligible(tmp_path, monkeypatch):
    executable = tmp_path / "cleanup"
    executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    executable.chmod(0o700)
    conn = Connection([(10, 7, "alice", 1)])
    monkeypatch.setattr(
        "atd_radius.infrastructure.mailbox_cleanup.subprocess.run",
        lambda *args, **kwargs: Mock(returncode=1),
    )

    assert process_pending_mailbox_cleanup(conn, str(executable)) == (0, 1)
    failed = [call for call in conn.calls if "SET status=%s" in call[0]][0]
    assert failed[1][0] == "failed"
    assert "status IN ('pending', 'failed')" in next(sql for sql, _ in conn.calls if "WITH candidates" in sql)


def test_worker_refuses_shell_metacharacters_and_missing_configuration(tmp_path, monkeypatch):
    executable = tmp_path / "cleanup"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    conn = Connection([(11, 7, "alice;touch /tmp/pwned", 1)])
    calls = []
    monkeypatch.setattr(
        "atd_radius.infrastructure.mailbox_cleanup.subprocess.run",
        lambda *args, **kwargs: calls.append((args, kwargs)) or Mock(returncode=0),
    )

    assert process_pending_mailbox_cleanup(conn, str(executable)) == (0, 1)
    assert calls == []
    assert "username rejected" in next(params[1] for sql, params in conn.calls if "SET status=%s" in sql)

    with pytest.raises(ValueError, match="not configured"):
        _validate_command("")
    assert not _safe_username("../alice")
    assert not _safe_username("alice;id")
    assert not _safe_username("alice name")
    assert _safe_username("alice@example.test")


def test_command_requires_absolute_executable_path(tmp_path):
    script = tmp_path / "not-executable"
    script.write_text("echo no", encoding="utf-8")
    with pytest.raises(ValueError, match="absolute path"):
        _validate_command(str(script))
