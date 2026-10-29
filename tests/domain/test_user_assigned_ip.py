from __future__ import annotations

import pytest

from atd_radius.domain.user_assigned_ip import (
    AssignedIPConflict,
    AssignedIPNotInUse,
    UserAssignedIPContainer,
)


def test_assign_ip_allocates_in_configured_order_and_returns_none_on_exhaustion():
    pool = UserAssignedIPContainer.from_attribute("192.0.2.9,192.0.2.3")
    assert pool.allocate() == "192.0.2.9"
    assert pool.allocate() == "192.0.2.3"
    assert pool.allocate() is None
    assert pool.used_ips == ("192.0.2.9", "192.0.2.3")


def test_reonline_claim_only_reserves_an_address_from_the_users_attribute():
    pool = UserAssignedIPContainer.from_attribute("192.0.2.9,192.0.2.3")
    assert pool.claim("198.51.100.1") is False
    assert pool.claim("192.0.2.3") is True
    assert pool.free_ips == ("192.0.2.9",)
    with pytest.raises(AssignedIPConflict):
        pool.claim("192.0.2.3")


def test_logout_releases_address_to_end_of_free_order_and_rejects_double_release():
    pool = UserAssignedIPContainer.from_attribute("192.0.2.9,192.0.2.3")
    first = pool.allocate()
    assert first == "192.0.2.9"
    pool.release(first)
    assert pool.free_ips == ("192.0.2.3", "192.0.2.9")
    with pytest.raises(AssignedIPNotInUse):
        pool.release(first)


def test_reload_preserves_used_addresses_still_in_attribute_and_drops_removed_ones():
    pool = UserAssignedIPContainer.from_attribute("192.0.2.9,192.0.2.3")
    assert pool.allocate() == "192.0.2.9"
    assert pool.allocate() == "192.0.2.3"
    pool.reload(["192.0.2.3", "192.0.2.8"])

    assert pool.all_ips == ("192.0.2.3", "192.0.2.8")
    assert pool.used_ips == ("192.0.2.3",)
    assert pool.free_ips == ("192.0.2.8",)


def test_attribute_parser_ignores_empty_values_and_duplicate_ips_preserving_order():
    pool = UserAssignedIPContainer.from_attribute(",192.0.2.9,,192.0.2.3,192.0.2.9,")
    assert pool.all_ips == ("192.0.2.9", "192.0.2.3")
    assert pool.free_ips == pool.all_ips
