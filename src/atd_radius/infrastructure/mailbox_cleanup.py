"""Durable, shell-free execution of A1.24 post-commit mailbox cleanup."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class MailboxCleanupConnection(Protocol):
    def execute(self, sql: str, params=()): ...
    def transaction(self): ...


@dataclass(frozen=True, slots=True)
class MailboxCleanupJob:
    job_id: int
    user_id: int
    username: str
    attempts: int


class MailboxCleanupRepository:
    """Outbox persistence; does not depend on the deleted user's database row."""

    def __init__(self, conn: MailboxCleanupConnection) -> None:
        self.conn = conn

    def enqueue(self, user_id: int, username: str) -> int:
        row = self.conn.execute(
            """
            INSERT INTO atd_radius_mailbox_cleanup (user_id, username)
            VALUES (%s, %s) RETURNING job_id
            """,
            (int(user_id), username),
        ).fetchone()
        return int(row[0])

    def claim_batch(self, limit: int = 25) -> tuple[MailboxCleanupJob, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("mailbox cleanup batch limit must be between 1 and 500")
        with self.conn.transaction():
            rows = self.conn.execute(
                """
                WITH candidates AS (
                    SELECT job_id FROM atd_radius_mailbox_cleanup
                    WHERE status IN ('pending', 'failed')
                       OR (status='running' AND updated_at < CURRENT_TIMESTAMP - INTERVAL '15 minutes')
                    ORDER BY job_id FOR UPDATE SKIP LOCKED LIMIT %s
                )
                UPDATE atd_radius_mailbox_cleanup AS jobs
                SET status='running', attempts=jobs.attempts+1,
                    updated_at=CURRENT_TIMESTAMP, last_error=NULL
                FROM candidates
                WHERE jobs.job_id=candidates.job_id
                RETURNING jobs.job_id, jobs.user_id, jobs.username, jobs.attempts
                """,
                (limit,),
            ).fetchall()
        return tuple(MailboxCleanupJob(int(r[0]), int(r[1]), str(r[2]), int(r[3])) for r in rows)

    def finish(self, job_id: int, *, success: bool, error: str | None = None) -> None:
        self.conn.execute(
            """
            UPDATE atd_radius_mailbox_cleanup
            SET status=%s, last_error=%s, updated_at=CURRENT_TIMESTAMP,
                finished_at=CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE job_id=%s AND status='running'
            """,
            ("succeeded" if success else "failed", None if success else (error or "cleanup failed")[:500], success, job_id),
        )


def _validate_command(command: str) -> Path:
    if not command.strip():
        raise ValueError("ATD_MAILBOX_CLEANUP_COMMAND is not configured")
    path = Path(command)
    if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("mailbox cleanup command must be an absolute path to an executable file")
    return path


def _safe_username(username: str) -> bool:
    # The legacy shell script interpolates this value into a filesystem path.
    return (
        bool(username)
        and username not in {".", ".."}
        and "/" not in username
        and "\\" not in username
        and ".." not in username.split(".")
        and all(ord(char) >= 33 and ord(char) != 127 for char in username)
    )


def process_pending_mailbox_cleanup(
    conn, command: str, *, limit: int = 25, timeout_seconds: int = 15
) -> tuple[int, int]:
    """Process a bounded batch. Return (succeeded, failed); never invoke a shell."""
    executable = _validate_command(command)
    if not 1 <= timeout_seconds <= 120:
        raise ValueError("mailbox cleanup timeout must be between 1 and 120 seconds")
    repository = MailboxCleanupRepository(conn)
    succeeded = failed = 0
    for job in repository.claim_batch(limit):
        error = None
        ok = False
        if not _safe_username(job.username):
            error = "username rejected by mailbox cleanup safety validation"
        else:
            try:
                result = subprocess.run(
                    [str(executable), job.username],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=timeout_seconds,
                    check=False,
                    shell=False,
                )
                ok = result.returncode == 0
                if not ok:
                    error = f"cleanup command exited with status {result.returncode}"
            except subprocess.TimeoutExpired:
                error = f"cleanup command timed out after {timeout_seconds} seconds"
            except OSError as exc:
                error = f"cleanup command could not be executed: {type(exc).__name__}"
        repository.finish(job.job_id, success=ok, error=error)
        if ok:
            succeeded += 1
        else:
            failed += 1
        conn.commit()
    return succeeded, failed
