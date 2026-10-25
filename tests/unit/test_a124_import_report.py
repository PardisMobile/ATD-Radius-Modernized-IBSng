"""Tests for immutable A1.24 import audit report output."""
from __future__ import annotations

import json
import os

import pytest

from atd_radius.cli.a124_import import A124ImportError, _write_report


def test_report_is_valid_private_json_and_never_overwrites(tmp_path):
    path = tmp_path / "import-audit.json"
    report = {"mode": "dry-run", "source_rows_total": 12, "tables": [{"table": "users", "source_rows": 12}]}

    _write_report(path, report)

    assert json.loads(path.read_text(encoding="utf-8")) == report
    assert os.stat(path).st_mode & 0o777 == 0o600
    with pytest.raises(A124ImportError, match="refusing to overwrite"):
        _write_report(path, {"mode": "apply"})
    assert json.loads(path.read_text(encoding="utf-8")) == report


def test_report_does_not_create_parent_directories(tmp_path):
    path = tmp_path / "missing" / "audit.json"
    with pytest.raises(FileNotFoundError):
        _write_report(path, {"mode": "dry-run"})
    assert not path.exists()
