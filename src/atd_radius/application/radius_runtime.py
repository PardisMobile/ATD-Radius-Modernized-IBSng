"""Production composition for the native RADIUS runtime."""
from __future__ import annotations
from typing import Protocol
from atd_radius.domain.aaa import PluginPipeline, PluginSpec
from atd_radius.domain.accounting_session import AccountingSessionService
from atd_radius.domain.accounting_charge import InternetChargeSettlement
from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_dispatch import DispatchResult, RadiusDispatcher
from atd_radius.domain.session_policy import ActiveSessionView
from atd_radius.domain.session_control import RegistrySessionControl
from atd_radius.domain.user_policies import AuthenticationPolicy, LockPolicy, MultiLoginPolicy, TimeoutPolicy
from atd_radius.domain.ras import RASRuntimeRegistry
from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry
from atd_radius.domain.ip_pool_policy import IPPoolAllocationPolicy
from atd_radius.domain.radius_runtime import SessionRegistry
from atd_radius.infrastructure.accounting_persistence import NativeAccountingPersistence
from atd_radius.infrastructure.connection_log_repository import ConnectionLogRepository
from atd_radius.infrastructure.billing_rules import PostgresInternetChargeRuleRepository
from atd_radius.infrastructure.credit_repository import UserCreditRepository
from atd_radius.infrastructure.ip_pool_repository import PostgresIPPoolRepository
from atd_radius.infrastructure.ras import RASRepository
from atd_radius.infrastructure import UserRepository

class UserSource(Protocol):
    def get_authentication_record(self, username: str) -> tuple[int, str, bool] | None: ...
    def attributes(self, user_id: int) -> list[tuple[str, str]]: ...

class AccountingIdentityResolver(Protocol):
    def user_id(self, username: str) -> int | None: ...
    def ras_id(self, source_ip: str) -> int | None: ...

class IPPoolSessionManager:
    """Bind native IP-pool runtime leases to RADIUS session lifecycle."""

    def __init__(self, pools: IPPoolRuntimeRegistry, ras: RASRuntimeRegistry) -> None:
        self.pools = pools
        self.ras = ras

    def accounting_start(self, event, ras_id: int) -> None:
        ip = event.remote_ip
        if not ip:
            return
        ras_record = self.ras.get(ras_id)
        if ras_record is None:
            return
        pool_id = self.pools.find_pool(ras_record.ippool_ids, ip)
        if pool_id is not None:
            self.pools.ensure_claimed(pool_id, ip)

    def accounting_stop(self, event, ras_id: int) -> None:
        self.release_ip(ras_id, event.remote_ip)

    def release_ip(self, ras_id: int, ip: str | None) -> None:
        if not ip:
            return
        ras_record = self.ras.get(ras_id)
        if ras_record is None:
            return
        pool_id = self.pools.find_pool(ras_record.ippool_ids, ip)
        if pool_id is None:
            return
        pool = self.pools.get(pool_id)
        if pool is not None and ip in pool.used_ips:
            self.pools.release(pool_id, ip)

    def release_states(self, states) -> None:
        for state in states:
            self.release_ip(state.key.ras_id, state.attributes.get("Framed-IP-Address"))

class RadiusRuntimeHandler:
    """Adapt domain dispatch to UDP transport and execute accounting lifecycle."""
    def __init__(
        self,
        dispatcher: RadiusDispatcher,
        accounting_sessions: AccountingSessionService,
        identities: AccountingIdentityResolver,
        persistence=None,
        ip_pool_sessions: IPPoolSessionManager | None = None,
    ) -> None:
        self.dispatcher = dispatcher
        self.accounting_sessions = (
            AccountingSessionService(accounting_sessions.registry, persistence)
            if persistence is not None and accounting_sessions.persistence is None
            else accounting_sessions
        )
        self.identities = identities
        self.ip_pool_sessions = ip_pool_sessions
        if self.dispatcher.session_control is None:
            self.dispatcher.session_control = RegistrySessionControl(accounting_sessions.registry)

    def __call__(self, packet: RadiusPacket, peer: tuple[str, int]) -> RadiusPacket:
        if packet.code in (RadiusCode.DISCONNECT_REQUEST, RadiusCode.COA_REQUEST):
            registry = self.accounting_sessions.registry
            matches = registry.matching(packet.attributes) if packet.code is RadiusCode.DISCONNECT_REQUEST else ()
            response = self.dispatcher.control(packet)
            if response.code is RadiusCode.DISCONNECT_ACK and self.ip_pool_sessions:
                self.ip_pool_sessions.release_states(matches)
            return response
        if packet.code is RadiusCode.ACCOUNTING_REQUEST:
            result: DispatchResult = self.dispatcher.accounting(packet)
            event = result.accounting
            if event is not None:
                user_id = self.identities.user_id(event.username)
                ras_id = self.identities.ras_id(peer[0])
                if user_id is not None and ras_id is not None:
                    self.accounting_sessions.apply(event, user_id, ras_id)
                    if self.ip_pool_sessions:
                        if event.status.value == "Start":
                            self.ip_pool_sessions.accounting_start(event, ras_id)
                        elif event.status.value == "Stop":
                            self.ip_pool_sessions.accounting_stop(event, ras_id)
            return result.response
        return self.dispatcher.access(packet, source_ip=peer[0])

def build_radius_dispatcher(
    users: UserSource,
    active_sessions_provider=None,
    ras=None,
    ip_pools: IPPoolRuntimeRegistry | None = None,
) -> RadiusDispatcher:
    """Build the native authentication boundary without inventing a new schema."""
    from atd_radius.infrastructure.access_context import NativeAccessContext
    policies = [
        PluginSpec(1, "authentication", AuthenticationPolicy()),
        PluginSpec(2, "lock", LockPolicy()),
        PluginSpec(3, "multi_login", MultiLoginPolicy(active_sessions_provider=active_sessions_provider)),
    ]
    if ip_pools is not None:
        policies.append(PluginSpec(4, "ip_pool", IPPoolAllocationPolicy(ip_pools)))
    policies.append(PluginSpec(5, "timeout", TimeoutPolicy()))
    pipeline = PluginPipeline(policies)
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

def build_ras_runtime(repository, type_defaults=None) -> RASRuntimeRegistry:
    """Build and load the source-compatible RAS runtime with mutation reloads."""
    registry = RASRuntimeRegistry(repository, type_defaults)
    registry.reload()
    if getattr(repository, "on_change", None) is None:
        repository.on_change = registry.on_repository_change
    return registry


def build_native_radius_runtime(conn, type_defaults=None, users=None, ras_repository=None, pool_repository=None):
    """Compose the native RADIUS runtime over the A1.24 PostgreSQL schema.

    The connection is intentionally supplied by the caller so the runtime,
    accounting persistence and repository reads share one transaction boundary.
    """
    users = users or UserRepository(conn)
    ras_repository = ras_repository or RASRepository(conn)
    pool_repository = pool_repository or PostgresIPPoolRepository(conn)

    ras = build_ras_runtime(ras_repository, type_defaults)
    pools = IPPoolRuntimeRegistry(pool_repository)
    pools.reload()

    sessions = SessionRegistry()
    persistence = NativeAccountingPersistence(ConnectionLogRepository(conn))
    charge = InternetChargeSettlement(PostgresInternetChargeRuleRepository(conn), users, UserCreditRepository(conn))
    accounting = AccountingSessionService(sessions, persistence, charge)
    dispatcher = build_radius_dispatcher(
        users,
        active_sessions_provider=session_views(sessions),
        ras=ras,
        ip_pools=pools,
    )
    identities = NativeAccountingIdentityResolver(users, ras)
    ip_pool_sessions = IPPoolSessionManager(pools, ras)
    return RadiusRuntimeHandler(
        dispatcher,
        accounting,
        identities,
        ip_pool_sessions=ip_pool_sessions,
    )
