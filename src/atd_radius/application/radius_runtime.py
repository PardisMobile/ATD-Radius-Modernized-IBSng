"""Production composition for the native RADIUS runtime."""
from __future__ import annotations

from typing import Callable, Protocol
from dataclasses import replace
from datetime import datetime, timezone
import logging

from atd_radius.domain.aaa import PluginPipeline, PluginSpec
from atd_radius.domain.accounting_session import AccountingSessionService
from atd_radius.domain.accounting_lifecycle import event_from_attributes
from atd_radius.domain.accounting_charge import InternetChargeSettlement, VoipChargeSettlement, UserChargeSettlement, VoipLimitPlan
from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_dispatch import DispatchResult, RadiusDispatcher
from atd_radius.domain.session_policy import ActiveSessionView
from atd_radius.domain.session_control import RegistrySessionControl
from atd_radius.domain.user_policies import AuthenticationPolicy, LockPolicy, MultiLoginPolicy, TimeoutPolicy
from atd_radius.domain.ras import RASRuntimeRegistry
from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry
from atd_radius.domain.ip_pool_policy import IPPoolAllocationPolicy
from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry
from atd_radius.domain.ras_provider import provider_session_id, provider_service_for_ras
from atd_radius.domain.user_policies import ras_allows_multi_login
from atd_radius.infrastructure.accounting_persistence import NativeAccountingPersistence
from atd_radius.infrastructure.connection_log_repository import ConnectionLogRepository
from atd_radius.infrastructure.bandwidth_snapshot_repository import PostgresBandwidthSnapshotRepository
from atd_radius.infrastructure.billing_rules import PostgresInternetChargeRuleRepository
from atd_radius.infrastructure.voip_charge_rules import PostgresVoipChargeRuleRepository
from atd_radius.infrastructure.voip_tariff_repository import PostgresVoipTariffRepository
from atd_radius.infrastructure.credit_repository import UserCreditRepository
from atd_radius.infrastructure.ip_pool_repository import PostgresIPPoolRepository
from atd_radius.infrastructure.ras import RASRepository
from atd_radius.infrastructure import UserRepository
from atd_radius.application.voip_limit_scheduler import VoipLimitScheduler
from atd_radius.application.voip_limit_loop import VoipLimitCheckLoop
from atd_radius.infrastructure.ras_termination import SourceRASDisconnectClient, PermanentRASTerminationError


class UserSource(Protocol):
    def get_authentication_record(self, username: str) -> tuple[int, str, bool] | None: ...
    def attributes(self, user_id: int) -> list[tuple[str, str]]: ...
    def is_normal_user(self, user_id: int) -> bool: ...
    def policy_attributes(self, user_id: int) -> list[tuple[str, str]]: ...


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
        bandwidth_snapshots: PostgresBandwidthSnapshotRepository | None = None,
    ) -> None:
        self.dispatcher = dispatcher
        self.accounting_sessions = (
            AccountingSessionService(accounting_sessions.registry, persistence)
            if persistence is not None and accounting_sessions.persistence is None
            else accounting_sessions
        )
        self.identities = identities
        self.ip_pool_sessions = ip_pool_sessions
        self.bandwidth_snapshots = bandwidth_snapshots
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
            with self.accounting_sessions.registry.synchronized():
                result: DispatchResult = self.dispatcher.accounting(packet)
                event = result.accounting
                if event is not None:
                    user_id = self.identities.user_id(event.username)
                    ras_id = self.identities.ras_id(peer[0])
                    if user_id is not None and ras_id is not None:
                        ras_record = self.identities.ras.get(ras_id)
                        if ras_record is not None:
                            session_id = provider_session_id(ras_record.ras_type, event.attributes)
                            if session_id is not None:
                                event = replace(event, session_id=session_id)
                            service = provider_service_for_ras(ras_record.ras_type)
                            ras_allowed = ras_allows_multi_login(
                                ras_record.ras_type, ras_record.all_attributes(), service
                            )
                            event = replace(
                                event,
                                ras_multi_login_allowed=ras_allowed,
                            )
                        accounting_result = self.accounting_sessions.apply(event, user_id, ras_id)
                        # A1.24 BWSnapShotOnlinesLoopClient only records normal
                        # users with the effective save_bw_usage marker. RADIUS
                        # counter deltas are aggregated into the native snapshot
                        # table by the configured snapshot interval bucket.
                        if self.bandwidth_snapshots is not None:
                            users = getattr(self.identities, "users", None)
                            if (
                                accounting_result.delta_input_octets > 0
                                or accounting_result.delta_output_octets > 0
                            ) and users is not None:
                                is_normal_user = getattr(users, "is_normal_user", None)
                                policy_attributes = getattr(users, "policy_attributes", None)
                                if callable(is_normal_user) and callable(policy_attributes):
                                    normal_user = is_normal_user(user_id)
                                    effective_attrs = dict(policy_attributes(user_id))
                                    if normal_user and "save_bw_usage" in effective_attrs:
                                        self.bandwidth_snapshots.record_usage(
                                            event.observed_at,
                                            user_id,
                                            accounting_result.delta_input_octets,
                                            accounting_result.delta_output_octets,
                                        )
                        if self.ip_pool_sessions:
                            if event.status.value == "Start":
                                self.ip_pool_sessions.accounting_start(event, ras_id)
                            elif event.status.value == "Stop":
                                self.ip_pool_sessions.accounting_stop(event, ras_id)
                return result.response
        return self.dispatcher.access(packet, source_ip=peer[0])


class NativeRadiusRuntimeState:
    """Long-lived in-memory state shared by packet-scoped database runtimes."""

    def __init__(self, type_defaults=None) -> None:
        self.sessions = SessionRegistry()
        self.ras: RASRuntimeRegistry | None = None
        self.pools: IPPoolRuntimeRegistry | None = None
        self.type_defaults = type_defaults

    def initialize(self, ras_repository, pool_repository) -> None:
        self.ras = build_ras_runtime(ras_repository, self.type_defaults)
        self.pools = IPPoolRuntimeRegistry(pool_repository)
        self.pools.reload()


class NativeRadiusPacketHandler:
    """Create a fresh DB transaction for each packet while retaining runtime state."""

    def __init__(
        self,
        state: NativeRadiusRuntimeState,
        connection_factory: Callable[[], object],
    ) -> None:
        self.state = state
        self.connection_factory = connection_factory
        self._logger = logging.getLogger(__name__)
        self._ras_terminator = SourceRASDisconnectClient()
        scheduler = VoipLimitScheduler(on_error=self._scheduler_error)
        self.voip_limit_loop = VoipLimitCheckLoop(
            scheduler,
            self._check_voip_limits,
            self._terminate_voip_session,
            on_error=self._limit_error,
        )
        self.voip_limit_loop.start()

    def _scheduler_error(self, key, exc: Exception) -> None:
        self._logger.error("VoIP timer callback failed for %r: %s", key, exc)

    def _limit_error(self, user_id: int, exc: Exception) -> None:
        self._logger.error("VoIP limit enforcement failed for user %s: %s", user_id, exc)

    def close(self) -> None:
        """Stop the timer worker during normal process shutdown."""
        self.voip_limit_loop.close()

    def _refresh_voip_limit_schedule(self, user_id: int) -> None:
        ras_registry = self.state.ras
        if ras_registry is None:
            self.voip_limit_loop.cancel(user_id)
            return
        with self.state.sessions.synchronized():
            active = self.state.sessions.active_for_user(user_id)
            has_voip_charge = any(
                state.charge_id is not None
                and state.charge_kind == "voip"
                and ras_registry.get(state.key.ras_id) is not None
                for state in active
            )
        if has_voip_charge:
            # Re-evaluate after accounting mutations rather than retaining a
            # deadline calculated from a stale credit/rule snapshot.
            self.voip_limit_loop.schedule(user_id, 1)
        else:
            self.voip_limit_loop.cancel(user_id)

    def _check_voip_limits(self, user_id: int) -> VoipLimitPlan:
        with self.connection_factory() as conn:
            ras_registry = build_ras_runtime(RASRepository(conn), self.state.type_defaults)
            users = UserRepository(conn)
            credits = UserCreditRepository(conn)
            available_credit = credits.get(user_id)
            if available_credit is None:
                return VoipLimitPlan(None)
            settlement = VoipChargeSettlement(
                PostgresVoipChargeRuleRepository(conn),
                users,
                PostgresVoipTariffRepository(conn),
                credits,
            )
            with self.state.sessions.synchronized():
                active = tuple(
                    state
                    for state in self.state.sessions.active_for_user(user_id)
                    if state.charge_id is not None
                    and state.charge_kind == "voip"
                    and ras_registry.get(state.key.ras_id) is not None
                )
                if not active:
                    return VoipLimitPlan(None)
                when = datetime.now(timezone.utc)
                return settlement.plan_limits(
                    active,
                    when,
                    available_credit,
                    lambda state: (
                        state.key.ras_id,
                        state.attributes.get("NAS-Port") or state.attributes.get("NAS-Port-Id"),
                    ),
                )

    def _terminate_voip_session(self, session_key: SessionKey, reason: str) -> None:
        with self.state.sessions.synchronized():
            state = self.state.sessions.get(session_key)
            if state is None or state.stopped:
                return
            # Successful provider requests stay marked until Accounting-Stop;
            # this prevents duplicate Disconnect-Requests on repeated Interim.
            if getattr(state, "termination_requested_reason", None):
                return
            state.termination_requested_reason = reason
            state.termination_requested_at = datetime.now(timezone.utc)
            snapshot = replace(state, attributes=dict(state.attributes))
        try:
            with self.connection_factory() as conn:
                ras_registry = build_ras_runtime(RASRepository(conn), self.state.type_defaults)
                ras = ras_registry.get(session_key.ras_id)
                if ras is None:
                    raise PermanentRASTerminationError("session RAS is missing or inactive")
                if ras.ras_type.strip().lower() == "mvts":
                    # A1.24 MVTS.killUser uses user_obj.getUserAttrs()["voip_username"],
                    # not the RADIUS User-Name (which may be the IBSng login).
                    credentials = UserRepository(conn).voip_credentials(session_key.user_id)
                    if credentials is None or not credentials[0].strip():
                        raise PermanentRASTerminationError(
                            "MVTS session user has no configured voip_username"
                        )
                    snapshot = replace(
                        snapshot,
                        attributes={**snapshot.attributes, "User-Name": credentials[0]},
                    )
                self._ras_terminator.terminate(ras, snapshot, reason)
        except Exception:
            with self.state.sessions.synchronized():
                current = self.state.sessions.get(session_key)
                if current is state and not current.stopped:
                    current.termination_requested_reason = None
                    current.termination_requested_at = None
            raise

    def __call__(self, packet: RadiusPacket, peer: tuple[str, int]) -> RadiusPacket:
        with self.connection_factory() as conn:
            if self.state.ras is None or self.state.pools is None:
                self.state.initialize(RASRepository(conn), PostgresIPPoolRepository(conn))
            else:
                self.state.ras.repository = RASRepository(conn)
                self.state.pools.repository = PostgresIPPoolRepository(conn)
                self.state.ras.reload()
                self.state.pools.reload()

            users = UserRepository(conn)
            ras = self.state.ras
            pools = self.state.pools
            persistence = NativeAccountingPersistence(ConnectionLogRepository(conn))
            credits = UserCreditRepository(conn)
            internet_charge = InternetChargeSettlement(
                PostgresInternetChargeRuleRepository(conn), users, credits,
            )
            voip_charge = VoipChargeSettlement(
                PostgresVoipChargeRuleRepository(conn), users,
                PostgresVoipTariffRepository(conn), credits,
            )
            charge = UserChargeSettlement(users, internet_charge, voip_charge)
            accounting = AccountingSessionService(self.state.sessions, persistence, charge)
            dispatcher = build_radius_dispatcher(
                users,
                active_sessions_provider=session_views(self.state.sessions),
                ras=ras,
                ip_pools=pools,
            )
            identities = NativeAccountingIdentityResolver(users, ras)
            handler = RadiusRuntimeHandler(
                dispatcher,
                accounting,
                identities,
                ip_pool_sessions=IPPoolSessionManager(pools, ras),
                bandwidth_snapshots=PostgresBandwidthSnapshotRepository(conn),
            )
            response = handler(packet, peer)
            if packet.code is RadiusCode.ACCOUNTING_REQUEST:
                try:
                    event = event_from_attributes(packet.attributes)
                except (TypeError, ValueError):
                    return response
                user_id = identities.user_id(event.username)
                if user_id is not None:
                    self._refresh_voip_limit_schedule(user_id)
            return response


class PostgresRadiusSecretResolver:
    """Resolve active NAS/RAS secrets from PostgreSQL for each incoming packet."""

    def __init__(self, connection_factory: Callable[[], object]) -> None:
        self.connection_factory = connection_factory

    def secret_for_ip(self, source_ip: str) -> str | None:
        with self.connection_factory() as conn:
            return RASRepository(conn).get_secret_by_ip(source_ip)


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
        # A1.24 keeps normal and VoIP usernames in separate namespaces.
        # Accounting can arrive under either identity; Access authentication
        # continues to use get_authentication_record in its own boundary.
        accounting_lookup = getattr(self.users, "accounting_user_id", None)
        if callable(accounting_lookup):
            return accounting_lookup(username)
        record = self.users.get_authentication_record(username)
        return int(record[0]) if record else None

    def ras_id(self, source_ip: str) -> int | None:
        record = self.ras.get_by_ip(source_ip)
        return int(record.ras_id) if record else None


def session_views(registry) -> callable:
    """Return policy views including each active session's source RAS capability."""
    def provider(user_id: int) -> tuple[ActiveSessionView, ...]:
        views = []
        for state in registry.active_for_user(user_id):
            ras_allowed = state.ras_multi_login_allowed
            views.append(
                ActiveSessionView(
                    state.key.unique_id,
                    state.started_at,
                    ras_multi_login_allowed=ras_allowed,
                )
            )
        return tuple(views)

    return provider


def build_ras_runtime(repository, type_defaults=None) -> RASRuntimeRegistry:
    """Build and load the source-compatible RAS runtime with mutation reloads."""
    registry = RASRuntimeRegistry(repository, type_defaults)
    registry.reload()
    if getattr(repository, "on_change", None) is None:
        repository.on_change = registry.on_repository_change
    return registry


def build_native_radius_runtime(
    conn,
    type_defaults=None,
    users=None,
    ras_repository=None,
    pool_repository=None,
    state: NativeRadiusRuntimeState | None = None,
):
    """Compose the native RADIUS runtime over the A1.24 PostgreSQL schema.

    The connection is intentionally supplied by the caller so this function
    remains useful for tests and one-transaction composition. Production UDP
    wiring should use NativeRadiusPacketHandler so each packet owns a short
    transaction while runtime session/pool state remains process-local.
    """
    users = users or UserRepository(conn)
    ras_repository = ras_repository or RASRepository(conn)
    pool_repository = pool_repository or PostgresIPPoolRepository(conn)

    state = state or NativeRadiusRuntimeState(type_defaults)
    if state.ras is None or state.pools is None:
        state.initialize(ras_repository, pool_repository)
    else:
        state.ras.repository = ras_repository
        state.pools.repository = pool_repository
        state.ras.reload()
        state.pools.reload()

    persistence = NativeAccountingPersistence(ConnectionLogRepository(conn))
    credits = UserCreditRepository(conn)
    internet_charge = InternetChargeSettlement(PostgresInternetChargeRuleRepository(conn), users, credits)
    voip_charge = VoipChargeSettlement(
        PostgresVoipChargeRuleRepository(conn), users,
        PostgresVoipTariffRepository(conn), credits,
    )
    charge = UserChargeSettlement(users, internet_charge, voip_charge)
    accounting = AccountingSessionService(state.sessions, persistence, charge)
    dispatcher = build_radius_dispatcher(
        users,
        active_sessions_provider=session_views(state.sessions),
        ras=state.ras,
        ip_pools=state.pools,
    )
    identities = NativeAccountingIdentityResolver(users, state.ras)
    return RadiusRuntimeHandler(
        dispatcher,
        accounting,
        identities,
        ip_pool_sessions=IPPoolSessionManager(state.pools, state.ras),
        bandwidth_snapshots=PostgresBandwidthSnapshotRepository(conn),
    )
