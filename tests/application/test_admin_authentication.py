import pytest

from atd_radius.application.admin_authentication import (
    AdminAddressDeniedError,
    AdminAuthenticationError,
    AdminAuthenticator,
)
from atd_radius.domain.admin_permissions import AdminPermissionSet
from atd_radius.infrastructure.admin_repository import (
    AdminLockedError,
    NativeAdminRecord,
)


HASH = "$1$salt$qJH7.N4xYta3aEG/dfqo/0"


class FakeAdminRepository:
    def __init__(self, *, permissions=None, locked=False, admin=None):
        self.admin = admin or NativeAdminRecord(7, "operator", "Operator", None, HASH)
        self.permission_set = AdminPermissionSet(permissions or {})
        self.locked = locked
        self.calls = []

    def get_by_username(self, username):
        self.calls.append(("get_by_username", username))
        return self.admin if self.admin.username == username else None

    def permissions(self, admin_id):
        self.calls.append(("permissions", admin_id))
        return self.permission_set

    def require_unlocked(self, admin_id):
        self.calls.append(("require_unlocked", admin_id))
        if self.locked:
            raise AdminLockedError("administrator is locked")


def test_native_admin_authenticates_password_and_returns_identity():
    repo = FakeAdminRepository()
    admin = AdminAuthenticator(repo).authenticate("operator", "password", "192.0.2.9")
    assert admin.admin_id == 7
    assert repo.calls == [
        ("get_by_username", "operator"),
        ("permissions", 7),
        ("require_unlocked", 7),
    ]


def test_invalid_password_fails_before_permissions_or_lock_queries():
    repo = FakeAdminRepository()
    with pytest.raises(AdminAuthenticationError):
        AdminAuthenticator(repo).authenticate("operator", "wrong", "192.0.2.9")
    assert repo.calls == [("get_by_username", "operator")]


def test_login_address_permission_accepts_exact_ip_and_dotted_netmask():
    repo = FakeAdminRepository(permissions={"LIMIT LOGIN ADDR": "192.0.2.9,198.51.100.0/255.255.255.0"})
    auth = AdminAuthenticator(repo)
    assert auth.authenticate("operator", "password", "192.0.2.9").admin_id == 7
    assert auth.authenticate("operator", "password", "198.51.100.42").admin_id == 7


def test_login_address_permission_denies_nonmatching_or_empty_value():
    for value in ("192.0.2.1/255.255.255.255", ""):
        repo = FakeAdminRepository(permissions={"LIMIT LOGIN ADDR": value})
        with pytest.raises(AdminAddressDeniedError):
            AdminAuthenticator(repo).authenticate("operator", "password", "192.0.2.9")
        assert ("require_unlocked", 7) not in repo.calls


def test_locked_admin_is_rejected_after_password_and_address_checks():
    repo = FakeAdminRepository(locked=True)
    with pytest.raises(AdminLockedError, match="administrator is locked"):
        AdminAuthenticator(repo).authenticate("operator", "password", "192.0.2.9")
    assert repo.calls[-1] == ("require_unlocked", 7)


def test_missing_admin_is_rejected_without_creating_identity():
    repo = FakeAdminRepository()
    with pytest.raises(AdminAuthenticationError):
        AdminAuthenticator(repo).authenticate("missing", "password", "192.0.2.9")
