from dataclasses import dataclass
from decimal import Decimal

from atd_radius.domain.entities import User


@dataclass(slots=True)
class UserService:
    """Application boundary for user operations.

    Persistence is intentionally injected later; protocol adapters must never
    contain SQL or user policy logic.
    """

    repository: object | None = None

    def create(self, username: str, credit: Decimal = Decimal("0")) -> User:
        username = username.strip()
        if not username:
            raise ValueError("username is required")
        if self.repository is not None:
            return self.repository.create(username, credit)
        return User(id=None, username=username, credit=credit)
