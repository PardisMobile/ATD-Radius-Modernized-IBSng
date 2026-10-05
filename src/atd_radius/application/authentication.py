"""AAA authentication orchestration.

RADIUS and future REST/XML-RPC adapters call this service; they do not own
credential lookup, status policy, or password verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from atd_radius.domain.models import AttributeSet, User


class UserRepository(Protocol):
    def find_by_username(self, username: str) -> User | None: ...


class PasswordVerifier(Protocol):
    def verify(self, supplied: str, stored: str | None) -> bool: ...


@dataclass(slots=True)
class AuthenticationResult:
    accepted: bool
    user: User | None = None
    attributes: AttributeSet | None = None
    reason: str | None = None


class AuthenticationService:
    def __init__(self, users: UserRepository, verifier: PasswordVerifier):
        self.users = users
        self.verifier = verifier

    def authenticate(self, username: str, password: str) -> AuthenticationResult:
        username = username.strip()
        user = self.users.find_by_username(username)
        if user is None or not user.enabled:
            return AuthenticationResult(False, reason="invalid_credentials")
        if not self.verifier.verify(password, user.password_hash):
            return AuthenticationResult(False, reason="invalid_credentials")
        return AuthenticationResult(True, user=user, attributes=AttributeSet(user.attributes))
