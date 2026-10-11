from contextlib import contextmanager
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import atd_radius.api.voip_tariffs as api
from atd_radius.api.admin_dependencies import AdminPrincipal, require_admin_permission
from atd_radius.domain.admin_permissions import AdminPermissionSet


def principal(perms):
    return AdminPrincipal(7, "operator", None, AdminPermissionSet(perms))


def test_voip_tariff_permission_is_source_backed_and_not_group_fallback():
    require = require_admin_permission("SEE VOIP TARIFF")
    assert require(principal({"SEE VOIP TARIFF": ""})).username == "operator"
    with pytest.raises(HTTPException) as denied:
        require(principal({"LIST RAS": "", "GET RAS INFORMATION": ""}))
    assert denied.value.status_code == 403


def install_connection(monkeypatch):
    class Repository:
        def __init__(self, _conn):
            pass

        def list(self):
            return [
                SimpleNamespace(tariff_id=2, name="Zulu", comment="", prefixes=()),
                SimpleNamespace(tariff_id=1, name="Alpha", comment="A", prefixes=()),
            ]

        def get_by_name(self, name):
            if name != "Alpha":
                return None
            return SimpleNamespace(
                tariff_id=1,
                name="Alpha",
                comment="A",
                prefixes=(
                    SimpleNamespace(
                        prefix_id=9, code="98", name="Iran", cpm=Decimal("60.00"),
                        free_seconds=10, min_duration=3, round_to=30, min_chargeable_duration=20,
                    ),
                    SimpleNamespace(
                        prefix_id=10, code="989", name="Mobile", cpm=Decimal("90.00"),
                        free_seconds=5, min_duration=2, round_to=6, min_chargeable_duration=12,
                    ),
                ),
            )

    @contextmanager
    def fake_connection():
        yield object()

    monkeypatch.setattr(api, "connection", fake_connection)
    monkeypatch.setattr(api, "PostgresVoipTariffRepository", Repository)


def test_list_tariffs_omits_prefixes_and_sorts_by_name(monkeypatch):
    install_connection(monkeypatch)
    result = api.list_voip_tariffs(principal({"SEE VOIP TARIFF": ""}))
    assert [item.tariff_name for item in result] == ["Alpha", "Zulu"]
    assert all(item.prefixes == [] for item in result)


def test_tariff_detail_uses_native_field_names_and_prefix_name_regex(monkeypatch):
    install_connection(monkeypatch)
    result = api.get_voip_tariff(
        "Alpha", True, "^Mobile$", principal({"SEE VOIP TARIFF": ""})
    )
    assert result.tariff_id == 1
    assert [item.prefix_code for item in result.prefixes] == ["989"]
    assert result.prefixes[0].min_chargable_duration == 12


def test_tariff_detail_returns_404_for_unknown_name(monkeypatch):
    install_connection(monkeypatch)
    with pytest.raises(HTTPException) as error:
        api.get_voip_tariff("missing", True, "", principal({"SEE VOIP TARIFF": ""}))
    assert error.value.status_code == 404


def test_tariff_detail_rejects_invalid_regex(monkeypatch):
    install_connection(monkeypatch)
    with pytest.raises(HTTPException) as error:
        api.get_voip_tariff("Alpha", True, "[", principal({"SEE VOIP TARIFF": ""}))
    assert error.value.status_code == 422


def test_tariff_mutation_permission_is_required_separately():
    require = require_admin_permission("CHANGE VOIP TARIFF")
    assert require(principal({"CHANGE VOIP TARIFF": ""})).username == "operator"
    with pytest.raises(HTTPException) as denied:
        require(principal({"SEE VOIP TARIFF": ""}))
    assert denied.value.status_code == 403
