"""Source-derived native IBSng administrator authentication.

This service is deliberately not mounted as an HTTP endpoint yet. The canonical
A1.24 login RPC checks the password, then the remote-address restriction, then
admin locks. Session/token issuance and API integration remain separate work.
"""
from __future__ import annotations

import ipaddress
from typing import Protocol

from atd_radius.domain.ibsng_password import verify_ibsng_password
from atd_radius.infrastructure.admin_repository import (
    AdminLockedError,
    AdminRepository,
    NativeAdminRecord,
)


class AdminAuthenticationError(PermissionError):
    """Credentials do not identify a valid native administrator."""


class AdminAddressDeniedError(PermissionError):
    """The administrator's source-defined login-address restriction rejected the client."""


class _AdminRepository(Protocol):
    def get_by_username(self, username: str) -> NativeAdminRecord | None: ...
    def permissions(self, admin_id: int): ...
    def require_unlocked(self, admin_id: int) -> None: ...


def _address_allowed(remote_addr: str, permission_value: str | None) -> bool:
    try:
        remote = ipaddress.ip_address(remote_addr)
    except ValueError:
        return False

    # A1.24 stores this MULTIVALUE permission as comma-separated IP[/netmask]
    # entries. An empty value grants no source addresses.
    entries = [] if not permission_value else permission_value.split(",")
    for entry in entries:
        try:
            if "/" in entry:
                network = ipaddress.ip_network(entry, strict=False)
            else:
                network = ipaddress.ip_network(entry + ("/32" if remote.version == 4 else "/128"), strict=False)
            if network.version == remote.version and remote in network:
                return True
        except ValueError:
            # Invalid legacy permission values must not broaden access.
            continue
    return False


class AdminAuthenticator:
    """Authenticate against native admins/admin_perms/admin_locks records."""

    def __init__(self, repository: AdminRepository | _AdminRepository) -> None:
        self.repository = repository

    def authenticate(self, username: str, password: str, remote_addr: str) -> NativeAdminRecord:
        admin = self.repository.get_by_username(username)
        if admin is None or admin.password_hash is None:
            raise AdminAuthenticationError("invalid administrator credentials")
        if not verify_ibsng_password(password, admin.password_hash):
            raise AdminAuthenticationError("invalid administrator credentials")

        permissions = self.repository.permissions(admin.admin_id)
        if permissions.has_perm("LIMIT LOGIN ADDR"):
            if not _address_allowed(remote_addr, permissions.values["LIMIT LOGIN ADDR"]):
                raise AdminAddressDeniedError("administrator login address is not permitted")

        # Source order: password check -> canLogin(address, lock) -> success.
        self.repository.require_unlocked(admin.admin_id)
        return admin


__all__ = [
    "AdminAddressDeniedError",
    "AdminAuthenticationError",
    "AdminAuthenticator",
    "AdminLockedError",
]
