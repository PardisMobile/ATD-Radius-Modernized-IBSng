"""Credential semantics preserved from IBSng A1.24 normal/VoIP users."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Iterable


class CredentialKind(StrEnum):
    NORMAL = "normal"
    VOIP = "voip"


class CredentialError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CredentialSet:
    kind: CredentialKind
    usernames: tuple[str, ...]
    password: str | None = None
    save_usernames: bool = True
    generate_password: bool = False
    password_character: str | None = None
    password_digit: str | None = None
    username_from_file: bool = False

    def validate(self) -> None:
        if not self.usernames:
            raise CredentialError("at least one username is required")
        if any(not _valid_username(name) for name in self.usernames):
            raise CredentialError("one or more usernames contain invalid characters")
        if len(set(self.usernames)) != len(self.usernames):
            raise CredentialError("duplicate usernames are not allowed")
        if self.generate_password and self.password:
            raise CredentialError("generated and explicit passwords are mutually exclusive")
        if self.generate_password and self.password_character is not None and len(self.password_character) != 1:
            raise CredentialError("password_character must be a single character")
        if self.generate_password and self.password_digit is not None and len(self.password_digit) != 1:
            raise CredentialError("password_digit must be a single character")


def _valid_username(value: str) -> bool:
    return bool(value) and re.fullmatch(r"[A-Za-z0-9_.@:+\-]+", value) is not None


def normalize_usernames(values: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        values = re.split(r"[\s,]+", values)
    result = tuple(v.strip() for v in values if v and v.strip())
    return result


def find_duplicate_usernames(credentials: Iterable[CredentialSet]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for credential in credentials:
        credential.validate()
        for username in credential.usernames:
            if username in seen:
                duplicates.add(username)
            seen.add(username)
    return duplicates
