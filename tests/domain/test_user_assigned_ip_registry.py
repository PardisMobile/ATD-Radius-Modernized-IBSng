from __future__ import annotations
import pytest
from atd_radius.domain.user_assigned_ip import AssignedIPConflict
from atd_radius.domain.user_assigned_ip_registry import UserAssignedIPRegistry


def test_request_reservation_is_idempotent_and_accounting_consumes_it():
    registry = UserAssignedIPRegistry()
    ip = registry.reserve(12, "192.0.2.10,192.0.2.11", "request-a")
    assert ip == "192.0.2.10"
    assert registry.reserve(12, "192.0.2.10,192.0.2.11", "request-a") == ip
    assert registry.snapshot(12)[1] == ("192.0.2.11",)
    assert registry.consume("request-a", 4, "session-a") == ip
    assert registry.pending("request-a") is None
    assert registry.session_address(12, 4, "session-a") == ip
    assert registry.consume("request-a", 4, "session-a") is None


def test_rejected_request_releases_only_its_pending_address():
    registry = UserAssignedIPRegistry()
    assert registry.reserve(12, "192.0.2.10,192.0.2.11", "a") == "192.0.2.10"
    assert registry.reserve(12, "192.0.2.10,192.0.2.11", "b") == "192.0.2.11"
    assert registry.release_request("a")
    assert not registry.release_request("a")
    assert registry.snapshot(12)[1] == ("192.0.2.10",)


def test_session_release_is_exact_and_idempotent():
    registry = UserAssignedIPRegistry()
    ip = registry.reserve(12, "192.0.2.10", "request-a")
    assert registry.consume("request-a", 4, "session-a") == ip
    assert registry.release_session(12, 4, "session-a") == ip
    assert registry.release_session(12, 4, "session-a") is None
    assert registry.snapshot(12)[1] == (ip,)


def test_request_key_cannot_be_reused_for_another_user():
    registry = UserAssignedIPRegistry()
    assert registry.reserve(12, "192.0.2.10", "same") == "192.0.2.10"
    with pytest.raises(AssignedIPConflict):
        registry.reserve(13, "192.0.2.20", "same")


def test_empty_pool_and_exhaustion_return_none():
    registry = UserAssignedIPRegistry()
    assert registry.allocate(12, None) is None
    assert registry.reserve(12, "", "empty") is None
    assert registry.snapshot(12) == ((), (), ())
