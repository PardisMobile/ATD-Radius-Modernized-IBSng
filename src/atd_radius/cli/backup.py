"""Operator-controlled PostgreSQL backup, verification, and guarded restore."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from psycopg.conninfo import conninfo_to_dict

from atd_radius.config import settings


class BackupError(RuntimeError):
    pass


def _tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise BackupError(f"required PostgreSQL utility not found: {name}")
    return path


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise BackupError(f"{Path(args[0]).name} failed" + (f": {detail}" if detail else "")) from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _connection_args() -> list[str]:
    info = conninfo_to_dict(settings.database_url)
    args: list[str] = []
    # Avoid exposing credentials in process arguments: use libpq environment variables.
    mapping = {"host": "PGHOST", "port": "PGPORT", "user": "PGUSER",
               "password": "PGPASSWORD", "dbname": "PGDATABASE", "sslmode": "PGSSLMODE"}
    for key, env_name in mapping.items():
        if info.get(key) is not None:
            os.environ[env_name] = info[key]
    if info.get("connect_timeout") is not None:
        os.environ["PGCONNECT_TIMEOUT"] = info["connect_timeout"]
    return args


def create_backup(output: Path) -> dict[str, object]:
    if output.exists():
        raise BackupError(f"refusing to overwrite existing backup: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    _connection_args()
    pg_dump = _tool("pg_dump")
    pg_restore = _tool("pg_restore")
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        _run([pg_dump, "--format=custom", "--no-owner", "--no-privileges", "--file", str(temp_path)])
        _run([pg_restore, "--list", str(temp_path)])
        digest = _sha256(temp_path)
        os.replace(temp_path, output)
        manifest = {
            "format": "postgresql-custom",
            "sha256": digest,
            "size_bytes": output.stat().st_size,
            "backup_file": output.name,
            "verified_archive_listing": True,
        }
        manifest_path = output.with_suffix(output.suffix + ".json")
        manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
        if manifest_path.exists():
            raise BackupError(f"refusing to overwrite backup manifest: {manifest_path}")
        manifest_tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        os.replace(manifest_tmp, manifest_path)
        return manifest
    finally:
        temp_path.unlink(missing_ok=True)


def verify_backup(backup: Path) -> dict[str, object]:
    manifest_path = backup.with_suffix(backup.suffix + ".json")
    if not backup.is_file() or not manifest_path.is_file():
        raise BackupError("backup and its .json manifest must both exist")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError(f"invalid backup manifest: {exc}") from exc
    actual = _sha256(backup)
    if manifest.get("format") != "postgresql-custom" or manifest.get("sha256") != actual:
        raise BackupError("backup checksum/format does not match its manifest")
    _run([_tool("pg_restore"), "--list", str(backup)])
    return {"verified": True, "sha256": actual, "size_bytes": backup.stat().st_size}


def restore_backup(backup: Path, confirmed_database: str) -> dict[str, object]:
    """Restore only after the operator explicitly names the target database."""
    info = conninfo_to_dict(settings.database_url)
    target = info.get("dbname", "")
    if not target or confirmed_database != target:
        raise BackupError("restore refused: --confirm-target must exactly match the configured database name")
    if not target.replace("_", "").replace("-", "").isalnum():
        raise BackupError("restore refused: configured database name is not a safe confirmation token")
    verify_backup(backup)
    _connection_args()
    _run([
        _tool("pg_restore"), "--exit-on-error", "--no-owner", "--no-privileges",
        "--clean", "--if-exists", "--dbname", target, str(backup),
    ])
    return {"restored": True, "target_database": target, "sha256": _sha256(backup)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atd-radius-backup")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create and verify a custom-format database backup")
    create.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify", help="verify backup checksum and PostgreSQL archive structure")
    verify.add_argument("backup", type=Path)
    restore = commands.add_parser("restore", help="destructively restore after explicit target confirmation")
    restore.add_argument("backup", type=Path)
    restore.add_argument("--confirm-target", required=True, help="must exactly equal the configured database name")
    args = parser.parse_args(argv)
    try:
        result = create_backup(args.output) if args.command == "create" else (
            verify_backup(args.backup) if args.command == "verify"
            else restore_backup(args.backup, args.confirm_target)
        )
    except (BackupError, OSError, ValueError) as exc:
        print(f"backup error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
