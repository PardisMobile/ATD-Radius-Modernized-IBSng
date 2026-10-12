from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.bandwidth_manager as api
from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.infrastructure.bandwidth_manager import PostgresBandwidthLeafRepository


def principal(perms):
    return AdminPrincipal(7, "operator", None, AdminPermissionSet(perms))


def test_bandwidth_manager_permission_follows_native_charge_dependency():
    require = require_admin_permission("CHANGE BANDWIDTH MANAGER")
    assert require(principal({
        "ACCESS ALL CHARGES": "", "CHANGE CHARGE": "", "CHANGE BANDWIDTH MANAGER": ""
    })).username == "operator"
    with pytest.raises(HTTPException) as denied:
        require(principal({"CHANGE BANDWIDTH MANAGER": ""}))
    assert denied.value.status_code == 403


class Result:
    def __init__(self, rows):
        self.rows = rows
    def fetchall(self):
        return self.rows


class Conn:
    def __init__(self):
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return Result([
            (4, "gold", 2, 3, 128, 256, 1024, 2048),
            (5, "silver", 2, 3, None, None, None, None),
        ])


def test_bandwidth_leaf_repository_maps_native_schema_and_sorts_in_sql():
    conn = Conn()
    leaves = PostgresBandwidthLeafRepository(conn).list()
    assert [leaf.leaf_name for leaf in leaves] == ["gold", "silver"]
    assert leaves[0].default_rate_kbits == 128
    assert leaves[0].total_ceil_kbits == 2048
    assert leaves[1].default_rate_kbits is None
    assert "FROM bw_leaf" in conn.calls[0][0]
    assert "ORDER BY leaf_name, leaf_id" in conn.calls[0][0]


def test_bandwidth_leaf_api_returns_native_leaf_fields(monkeypatch):
    @contextmanager
    def fake_connection():
        yield object()
    class Repository:
        def __init__(self, _conn): pass
        def list(self):
            return [SimpleNamespace(
                leaf_id=4, leaf_name="gold", interface_id=2, parent_id=3,
                default_rate_kbits=128, default_ceil_kbits=256,
                total_rate_kbits=1024, total_ceil_kbits=2048,
            )]
    monkeypatch.setattr(api, "connection", fake_connection)
    monkeypatch.setattr(api, "PostgresBandwidthLeafRepository", Repository)
    result = api.list_bandwidth_leaves(principal({
        "ACCESS ALL CHARGES": "", "CHANGE CHARGE": "", "CHANGE BANDWIDTH MANAGER": ""
    }))
    assert result[0].leaf_name == "gold"
    assert result[0].total_rate_kbits == 1024
