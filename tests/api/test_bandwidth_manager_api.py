from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.bandwidth_manager as api
from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.infrastructure.bandwidth_manager import (
    BandwidthInterface,
    BandwidthNode,
    BandwidthTree,
    BandwidthTreeCorruptError,
    PostgresBandwidthLeafRepository,
    PostgresBandwidthManagerRepository,
)


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


class TreeResult:
    def __init__(self, rows):
        self.rows = rows
    def fetchall(self):
        return self.rows
    def fetchone(self):
        return self.rows[0] if self.rows else None


class TreeConn:
    def __init__(self):
        self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        if "FROM bw_interface ORDER BY" in sql:
            return TreeResult([(1, "eth0", "uplink"), (2, "ppp0", "")])
        if "FROM bw_interface WHERE interface_name" in sql:
            return TreeResult([(1, "eth0", "uplink")])
        if "FROM bw_node WHERE interface_id" in sql:
            return TreeResult([(10,)])
        if "FROM bw_node WHERE parent_id" in sql:
            return TreeResult({10: [(11,), (12,)], 11: [], 12: []}[params[0]])
        if "FROM bw_leaf WHERE parent_id" in sql:
            return TreeResult({10: [("root-leaf",)], 11: [("gold",)], 12: []}[params[0]])
        if "FROM bw_node WHERE node_id" in sql:
            return TreeResult([(11, 1, 10, 100, 200)])
        raise AssertionError(f"unexpected query: {sql}")


def test_bandwidth_manager_repository_lists_interfaces_and_reconstructs_native_tree():
    conn = TreeConn()
    repo = PostgresBandwidthManagerRepository(conn)
    assert [item.interface_name for item in repo.list_interfaces()] == ["eth0", "ppp0"]
    interface = repo.get_interface_by_name("eth0")
    assert interface == BandwidthInterface(1, "eth0", "uplink")
    tree = repo.get_tree(interface.interface_id)
    assert tree == BandwidthTree(
        10,
        (
            BandwidthTree(11, (), ("gold",)),
            BandwidthTree(12, (), ()),
        ),
        ("root-leaf",),
    )
    assert repo.get_node(11) == BandwidthNode(11, 1, 10, 100, 200)


def test_bandwidth_manager_repository_rejects_cyclic_parent_links():
    class CyclicConn:
        def execute(self, sql, params=()):
            if "FROM bw_node WHERE interface_id" in sql:
                return TreeResult([(10,)])
            if "FROM bw_node WHERE parent_id" in sql:
                return TreeResult([(10,)])
            if "FROM bw_leaf WHERE parent_id" in sql:
                return TreeResult([])
            raise AssertionError(f"unexpected query: {sql}")
    with pytest.raises(BandwidthTreeCorruptError, match="cycle"):
        PostgresBandwidthManagerRepository(CyclicConn()).get_tree(1)


def test_bandwidth_manager_api_exposes_interfaces_tree_and_node(monkeypatch):
    @contextmanager
    def fake_connection():
        yield object()

    class Repository:
        def __init__(self, _conn): pass
        def list_interfaces(self):
            return [BandwidthInterface(1, "eth0", "uplink")]
        def get_interface_by_name(self, name):
            return BandwidthInterface(1, "eth0", "uplink") if name == "eth0" else None
        def get_tree(self, interface_id):
            return BandwidthTree(10, (BandwidthTree(11, (), ("gold",)),), ("root-leaf",))
        def get_node(self, node_id):
            return BandwidthNode(11, 1, 10, 100, 200) if node_id == 11 else None

    monkeypatch.setattr(api, "connection", fake_connection)
    monkeypatch.setattr(api, "PostgresBandwidthManagerRepository", Repository)
    admin = principal({"ACCESS ALL CHARGES": "", "CHANGE CHARGE": "", "CHANGE BANDWIDTH MANAGER": ""})
    interfaces = api.list_bandwidth_interfaces(admin)
    assert interfaces[0].interface_name == "eth0"
    tree = api.get_bandwidth_tree("eth0", admin)
    assert tree.node_id == 10 and tree.children[0].leaves == ["gold"]
    assert api.get_bandwidth_node(11, admin).rate_kbits == 100
    with pytest.raises(HTTPException) as missing:
        api.get_bandwidth_tree("unknown", admin)
    assert missing.value.status_code == 404
