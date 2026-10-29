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


def test_specific_reservation_is_idempotent_and_rejects_conflicting_request_key():
    registry = UserAssignedIPRegistry()
    assert registry.reserve_specific(5, "192.0.2.10,192.0.2.11", "req", "192.0.2.11") == "192.0.2.11"
    assert registry.reserve_specific(5, "192.0.2.10,192.0.2.11", "req", "192.0.2.11") == "192.0.2.11"
    with pytest.raises(AssignedIPConflict):
        registry.reserve_specific(5, "192.0.2.10,192.0.2.11", "req", "192.0.2.10")
    assert registry.snapshot(5)[1] == ("192.0.2.10",)


def test_specific_reservation_reports_unconfigured_address_and_conflict_for_used_address():
    registry = UserAssignedIPRegistry()
    assert registry.reserve_specific(5, "192.0.2.10", "outside", "192.0.2.99") is None
    assert registry.reserve_specific(5, "192.0.2.10", "first", "192.0.2.10") == "192.0.2.10"
    with pytest.raises(AssignedIPConflict):
        registry.reserve_specific(5, "192.0.2.10", "second", "192.0.2.10")


def test_accounting_session_claim_is_idempotent_and_never_rebinds():
    registry = UserAssignedIPRegistry()
    assert registry.bind_session(5, 7, "session", "192.0.2.10", "192.0.2.10,192.0.2.11") == "192.0.2.10"
    assert registry.bind_session(5, 7, "session", "192.0.2.10", "192.0.2.10,192.0.2.11") == "192.0.2.10"
    with pytest.raises(AssignedIPConflict):
        registry.bind_session(5, 7, "session", "192.0.2.11", "192.0.2.10,192.0.2.11")
    assert registry.snapshot(5)[1] == ("192.0.2.11",)


def test_consume_conflict_keeps_pending_lease_releasable():
    registry = UserAssignedIPRegistry()
    ip = registry.reserve(5, "192.0.2.10", "req")
    registry.bind_session(5, 7, "session", "192.0.2.11", "192.0.2.10,192.0.2.11")
    with pytest.raises(AssignedIPConflict):
        registry.consume("req", 7, "session")
    assert registry.pending("req") == (5, ip)
    assert registry.release_request("req")
