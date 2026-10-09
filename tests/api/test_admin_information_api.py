from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.admins as admins_api
from atd_radius.api.admin_dependencies import AdminPrincipal
from atd_radius.domain.admin_permissions import AdminPermissionSet


def principal(perms=None):
    return AdminPrincipal(7, "operator", "192.0.2.20", AdminPermissionSet(perms or {}))


def install_repository(monkeypatch, repo):
    @contextmanager
    def fake_connection():
        yield object()

    monkeypatch.setattr(admins_api, "connection", fake_connection)
    monkeypatch.setattr(admins_api, "AdminInformationRepository", lambda _conn: repo)


def test_admin_username_list_is_self_only_without_see_permission(monkeypatch):
    class Repo:
        def list_usernames(self):
            raise AssertionError("restricted listing must not query all administrators")

    install_repository(monkeypatch, Repo())
    assert admins_api.list_admin_usernames(principal({})) == ["operator"]


def test_admin_username_list_is_sorted_repository_result_with_permission(monkeypatch):
    class Repo:
        def list_usernames(self):
            return ["alpha", "operator", "zeta"]

    install_repository(monkeypatch, Repo())
    assert admins_api.list_admin_usernames(principal({"SEE ADMIN INFO": ""})) == ["alpha", "operator", "zeta"]


def test_admin_detail_allows_self_but_denies_other_admin_without_permission(monkeypatch):
    class Repo:
        def get_by_username(self, username):
            return SimpleNamespace(
                admin_id=7,
                username=username,
                name="Operator",
                comment=None,
                deposit=Decimal("10.00"),
                creator_id=None,
                creator=None,
                locks=(),
            )

    install_repository(monkeypatch, Repo())
    self_view = admins_api.get_admin_information("operator", principal({}))
    assert self_view.deposit == "10.00"

    with pytest.raises(HTTPException) as denied:
        admins_api.get_admin_information("another", principal({}))
    assert denied.value.status_code == 403
