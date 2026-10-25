"""Native PostgreSQL adapter for A1.24 periodic-accounting attributes."""
from __future__ import annotations

from collections.abc import Mapping

from atd_radius.infrastructure import UserRepository


class NativePeriodicAccountingAttributes:
    """Read effective group+user quota settings; write only user-owned counters.

    Quota definitions may be inherited from groups. Usage/reset are per-user
    state and therefore always persist to user_attrs, never group_attrs.
    """

    def __init__(self, users: UserRepository) -> None:
        self.users = users
        self.conn = users.conn

    def load(self, user_id: int) -> Mapping[str, str]:
        return dict(self.users.policy_attributes(user_id))

    def save(self, user_id: int, values: Mapping[str, str]) -> None:
        allowed = {
            f"{key}_{suffix}"
            for key in (
                "time_periodic_accounting_daily",
                "time_periodic_accounting_monthly",
                "traffic_periodic_accounting_daily",
                "traffic_periodic_accounting_monthly",
            )
            for suffix in ("usage", "reset")
        }
        unknown = set(values) - allowed
        if unknown:
            raise ValueError("unsupported periodic-accounting state attributes: " + ", ".join(sorted(unknown)))
        # The caller owns the packet transaction. No commit is performed here.
        for name, value in values.items():
            self.users.set_attribute(user_id, name, str(value))
