from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError


class Argon2PasswordService:
    """Password hashing boundary for user and administrator credentials."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        if not password:
            raise ValueError("password is required")
        return self._hasher.hash(password)

    def verify(self, supplied: str, stored: str | None) -> bool:
        if not supplied or not stored:
            return False
        try:
            return self._hasher.verify(stored, supplied)
        except (VerifyMismatchError, InvalidHashError):
            return False
