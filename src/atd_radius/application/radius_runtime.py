"""Production composition for the native RADIUS runtime."""
from __future__ import annotations

from typing import Protocol

from atd_radius.domain.aaa import PluginPipeline, PluginSpec
from atd_radius.domain.accounting_session import AccountingSessionService
from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_dispatch import DispatchResult, RadiusDispatcher
from atd_radius.domain.session_policy import ActiveSessionView
from atd_radius.domain.user_policies import AuthenticationPolicy, LockPolicy, MultiLoginPolicy, TimeoutPolicy


class UserSource(Protocol):
    def get_authentication_record(self, username: str) -> tuple[int, str, bool] | None: ...
    def attributes(self, user_id: int) -> list[tuple[str, str]]: ...


class AccountingIdentityResolver(Protocol):
    def user_id(self, username: str) -> int | None: ...
    def ras_id(self, source_ip: str) -> int | None: ...


class RadiusRuntimeHandler:
    """Adapt domain dispatch to the UDP transport and execute accounting lifecycle."""

    def __init__(
        self,
        dispatcher: RadiusDispatcher,
        accounting_sessions: AccountingSessionService,
        identities: AccountingIdentityResolver,
    ) -> None:
        self.dispatcher = dispatcher
        self.accounting_sessions = accounting_sessions
        self.identities = identities

    def __call__(self, packet: RadiusPacket, peer: tuple[str, int]) -> RadiusPacket:
        if packet.code is RadiusCode.ACCOUNTING_REQUEST:
            result: DispatchResult = self.dispatcher.accounting(packet)
            event = result.accounting
            if event is not None:
                user_id = self.identities.user_id(event.username)
                ras_id = self.identities.ras_id(peer[0])
                if user_id is not None and ras_id is not None:
                    self.accounting_sessions.apply(event, user_id, ras_id)
            return result.response
        return self.dispatcher.access(packet, source_ip=peer[0])


def build_radius_dispatcher(users: UserSource, active_sessions_provider=None, ras=None) -> RadiusDispatcher:
    """Build the native authentication boundary without inventing a new schema."""
    from atd_radius.infrastructure.access_context import NativeAccessContext

    pipeline = PluginPipeline(
        [
            PluginSpec(1, "authentication", AuthenticationPolicy()),
            PluginSpec(2, "lock", LockPolicy()),
            PluginSpec(3, "multi_login", MultiLoginPolicy(active_sessions_provider=active_sessions_provider)),
            PluginSpec(5, "timeout", TimeoutPolicy()),
        ]
    )
    return RadiusDispatcher(pipeline, access_context=NativeAccessContext(users, ras))


class NativeAccountingIdentityResolver:
    """Resolve Accounting-Request identities through native User/RAS repositories."""

    def __init__(self, users: UserSource, ras) -> None:
        self.users = users
        self.ras = ras

    def user_id(self, username: str) -> int | None:
        record = self.users.get_authentication_record(username)
        return int(record[0]) if record else None

    def ras_id(self, source_ip: str) -> int | None:
        record = self.ras.get_by_ip(source_ip)
        return int(record.ras_id) if record else None


def session_views(registry) -> callable:
    """Return native policy views backed by the live runtime session registry."""
    def provider(user_id: int) -> tuple[ActiveSessionView, ...]:
        return tuple(
            ActiveSessionView(state.key.unique_id)
            for state in registry.active_for_user(user_id)
        )
    return provider
