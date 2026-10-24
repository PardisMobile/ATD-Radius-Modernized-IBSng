"""Production composition for the native RADIUS runtime."""
from __future__ import annotations

from typing import Callable, Protocol
from dataclasses import replace
from datetime import datetime, timezone
import logging

from atd_radius.domain.aaa import PluginPipeline, PluginSpec
from atd_radius.domain.accounting_session import AccountingSessionService
from atd_radius.domain.accounting_lifecycle import AccountingEvent, AccountingStatus, event_from_attributes
from atd_radius.domain.accounting_charge import InternetChargeSettlement, VoipChargeSettlement, UserChargeSettlement, VoipLimitPlan
from atd_radius.domain.radius import RadiusCode, RadiusPacket
from atd_radius.domain.radius_dispatch import DispatchResult, RadiusDispatcher
from atd_radius.domain.session_policy import ActiveSessionView
from atd_radius.domain.session_control import RegistrySessionControl
from atd_radius.domain.user_policies import (
    AbsoluteExpiryPolicy,
    RelativeExpiryPolicy,
    AuthenticationPolicy,
    LockPolicy,
    MultiLoginPolicy,
    TimeoutPolicy,
)
from atd_radius.domain.ras import RASRuntimeRegistry
from atd_radius.domain.ip_pool import IPPoolRuntimeRegistry
from atd_radius.domain.ip_pool_policy import IPPoolAllocationPolicy
from atd_radius.domain.radius_runtime import SessionKey, SessionRegistry, SessionState
from atd_radius.domain.ras_provider import (
    normalize_ras_type,
    provider_accounting_should_apply,
    provider_session_id,
    provider_service_for_accounting,
    provider_accounting_username,
 )
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
from atd_radius.application.online_expiry_loop import OnlineSessionExpiryLoop, plan_online_expiry
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

    def expire_pending(self) -> int:
        return self.pools.expire_pending()

    def accounting_start(self, event, ras_id: int) -> None:
        ip = event.remote_ip
        if not ip:
            return
        ras_record = self.ras.get(ras_id)
        if ras_record is None:
            return
        pool_id = self.pools.find_pool(ras_record.ippool_ids, ip)
        if pool_id is None:
            return
        reservation = self.pools.consume_pending(ras_id, ip, event.username)
        if reservation is False:
            # Do not adopt an address reserved for a different login. The
            # pending lease will expire normally and the mismatch is visible
            # in logs rather than silently transferring ownership.
            logging.getLogger(__name__).warning(
                "Ignoring Accounting-Start for IP %s on RAS %s: pending lease belongs to another username",
                ip, ras_id,
            )
            return
        if reservation is None:
            self.pools.ensure_claimed(pool_id, ip)

    def accounting_stop(self, event, ras_id: int) -> None:
        self.release_ip(ras_id, event.remote_ip)

    def release_ip(self, ras_id: int, ip: str | None) -> None:
        if not ip:
            return
        self.pools.release_pending(ras_id, ip)
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
        cisco_voip_auth_h323_ids: dict[int, set[str]] | None = None,
        cisco_online_status: dict[int, dict[str, dict[str, object]]] | None = None,
        login_reservations=None,
    ) -> None:
        self.dispatcher = dispatcher
        self.accounting_sessions = (
            AccountingSessionService(accounting_sessions.registry, persistence)
            if persistence is not None and accounting_sessions.persistence is None
            else accounting_sessions
        )
        self.identities = identities
        self.login_reservations = login_reservations
        self.ip_pool_sessions = ip_pool_sessions
        self.bandwidth_snapshots = bandwidth_snapshots
        # A1.24 keeps successful Cisco VoIP authorization IDs in RAS-local
        # memory until a VoIP Accounting Start consumes them.
        self.cisco_voip_auth_h323_ids = (
            cisco_voip_auth_h323_ids if cisco_voip_auth_h323_ids is not None else {}
        )
        self.cisco_online_status = cisco_online_status if cisco_online_status is not None else {}
        if self.dispatcher.session_control is None:
            self.dispatcher.session_control = RegistrySessionControl(accounting_sessions.registry)

    def _record_cisco_online_status(
        self, ras_id: int, service: str, event: AccountingEvent,
        session_id: str | None, username: str,
    ) -> None:
        """Mirror CiscoRas's process-local online tracker without billing Alive packets."""
        if not session_id:
            return
        sessions = self.cisco_online_status.setdefault(ras_id, {})
        now = event.observed_at.timestamp()
        if service == "internet":
            if event.status is AccountingStatus.START:
                sessions[session_id] = {
                    "username": username, "last_update": now,
                    "in_bytes": 0, "out_bytes": 0,
                }
            elif event.status in (AccountingStatus.STOP, AccountingStatus.ALIVE):
                current = sessions.get(session_id)
                if current is None or current.get("username") != username:
                    return
                current["last_update"] = now
                if "Acct-Output-Octets" in event.attributes:
                    current["in_bytes"] = event.attributes["Acct-Output-Octets"]
                if "Acct-Input-Octets" in event.attributes:
                    current["out_bytes"] = event.attributes["Acct-Input-Octets"]
            return
        call_leg_is_voip_originate = provider_accounting_should_apply(
            "Cisco", "voip", "Start", event.attributes
        )
        if not call_leg_is_voip_originate:
            return
        if event.status is AccountingStatus.START:
            sessions[session_id] = {"username": username, "last_update": now}
        elif event.status is AccountingStatus.ALIVE:
            current = sessions.get(session_id)
            if current is not None:
                current["last_update"] = now
        elif event.status is AccountingStatus.STOP:
            sessions.pop(session_id, None)

    def __call__(self, packet: RadiusPacket, peer: tuple[str, int]) -> RadiusPacket:
        if self.ip_pool_sessions:
            self.ip_pool_sessions.expire_pending()
        if packet.code in (RadiusCode.DISCONNECT_REQUEST, RadiusCode.COA_REQUEST):
            registry = self.accounting_sessions.registry
            # Keep selection, state transition, settlement and IP release atomic
            # relative to concurrent Accounting packets. The control adapter
            # marks matches stopped; reopen each under this lock so the normal
            # accounting lifecycle performs charge settlement and closes the
            # native connection_log before the session is finally stopped.
            with registry.synchronized():
                # A control packet is authenticated against the RAS secret
                # selected by peer IP. Never let a username-only selector affect
                # a similarly named session attached to a different RAS.
                source_ras_id = self.identities.ras_id(peer[0])
                if source_ras_id is not None:
                    self.accounting_sessions.refresh_ras_sessions(source_ras_id)
                matches = (
                    registry.matching(packet.attributes, ras_id=source_ras_id)
                    if packet.code is RadiusCode.DISCONNECT_REQUEST and source_ras_id is not None
                    else ()
                )
                coa_matches = (
                    registry.matching(packet.attributes, ras_id=source_ras_id)
                    if packet.code is RadiusCode.COA_REQUEST and source_ras_id is not None
                    else ()
                )
                if source_ras_id is None:
                    response_code = (
                        RadiusCode.DISCONNECT_NAK
                        if packet.code is RadiusCode.DISCONNECT_REQUEST
                        else RadiusCode.COA_NAK
                    )
                    response = RadiusPacket(
                        response_code,
                        packet.identifier,
                        {"Error-Cause": "503"},
                        packet.authenticator,
                    )
                else:
                    response = self.dispatcher.control(packet, ras_id=source_ras_id)
                if response.code is RadiusCode.COA_ACK:
                    for state in coa_matches:
                        self.accounting_sessions.persist_state(state)
                if response.code is RadiusCode.DISCONNECT_ACK:
                    for state in matches:
                        if state.stopped:
                            state.stopped = False
                        attrs = {
                            str(name): str(value)
                            for name, value in state.attributes.items()
                            if not str(name).startswith("__")
                        }
                        attrs.update({
                            str(name): str(value)
                            for name, value in packet.attributes.items()
                        })
                        event = AccountingEvent(
                            status=AccountingStatus.STOP,
                            username=attrs.get("User-Name", ""),
                            session_id=state.key.unique_id,
                            input_octets=state.input_octets,
                            output_octets=state.output_octets,
                            terminate_cause="Admin-Reset",
                            attributes=attrs,
                            observed_at=datetime.now(timezone.utc),
                        )
                        self.accounting_sessions.apply(
                            event, state.key.user_id, state.key.ras_id
                        )
                    if self.ip_pool_sessions:
                        self.ip_pool_sessions.release_states(matches)
                return response
        if packet.code is RadiusCode.ACCOUNTING_REQUEST:
            with self.accounting_sessions.registry.synchronized():
                result: DispatchResult = self.dispatcher.accounting(packet)
                event = result.accounting
                if event is not None:
                    ras_id = self.identities.ras_id(peer[0])
                    ras_record = (
                        self.identities.ras.get(ras_id)
                        if ras_id is not None and getattr(self.identities, "ras", None) is not None
                        else None
                    )
                    if ras_record is not None:
                        ras_attributes = ras_record.all_attributes()
                        service = provider_service_for_accounting(
                            ras_record.ras_type, event.attributes
                        )
                        # Reject source-inapplicable Cisco call legs before user
                        # lookup or any charging/session side effect.
                        auth_ids = self.cisco_voip_auth_h323_ids.get(ras_id, set())
                        session_id = provider_session_id(
                            ras_record.ras_type, event.attributes, service
                        )
                        username = provider_accounting_username(
                            ras_record.ras_type, service, event.username, ras_attributes
                        )
                        should_apply = provider_accounting_should_apply(
                            ras_record.ras_type, service, event.status.value,
                            event.attributes, auth_ids,
                        )
                        if normalize_ras_type(ras_record.ras_type) == "cisco":
                            if event.status is AccountingStatus.ALIVE:
                                # The source updates only Cisco's online tracker for
                                # Alive; no native charge/session update is dispatched.
                                if (
                                    service == "internet"
                                    or provider_accounting_should_apply(
                                        "Cisco", "voip", "Start", event.attributes
                                    )
                                ):
                                    self._record_cisco_online_status(
                                        ras_id, service, event, session_id, username
                                    )
                                return result.response
                            if not should_apply:
                                return result.response
                            self._record_cisco_online_status(
                                ras_id, service, event, session_id, username
                            )
                            if service == "voip" and event.status is AccountingStatus.START and session_id:
                                # CiscoRas.__voipAcctStart consumes this ID from the
                                # authorization-without-accounting list before VOIP_UPDATE.
                                auth_ids.discard(session_id)
                        elif not should_apply:
                            return result.response
                        ras_allowed = ras_allows_multi_login(
                            ras_record.ras_type, ras_attributes, service
                        )
                        event = replace(
                            event,
                            username=username,
                            session_id=session_id or event.session_id,
                            ras_multi_login_allowed=ras_allowed,
                            service=service,
                        )
                    user_id = self.identities.user_id(event.username)
                    if user_id is not None and ras_id is not None:
                        if self.login_reservations is not None:
                            # Serialize every accounting transition with limit
                            # planning and login admission. This also keeps Stop
                            # from inverting the registry/session-lock order.
                            self.login_reservations.lock_user(user_id)
                        accounting_result = self.accounting_sessions.apply(event, user_id, ras_id)
                        if (
                            self.login_reservations is not None
                            and accounting_result.created
                            and event.status in (AccountingStatus.START, AccountingStatus.INTERIM)
                        ):
                            self.login_reservations.consume_one(user_id, ras_id)
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
        reservation_user_id = None
        reservation_ras_id = None
        reservation_request_key = None
        if self.login_reservations is not None:
            username = str(packet.attributes.get("User-Name", ""))
            user_source = getattr(self.identities, "users", None)
            lookup = getattr(user_source, "get_authentication_record", None)
            record = lookup(username) if callable(lookup) and username else None
            resolved_ras_id = self.identities.ras_id(peer[0])
            if record is not None and resolved_ras_id is not None:
                reservation_user_id = int(record[0])
                reservation_ras_id = int(resolved_ras_id)
                reservation_request_key = self.login_reservations.request_key(packet, peer)
                self.login_reservations.lock_user(reservation_user_id)
                self.accounting_sessions.refresh_user_sessions(reservation_user_id)
        response = self.dispatcher.access(packet, source_ip=peer[0])
        if (
            response.code is RadiusCode.ACCESS_ACCEPT
            and self.login_reservations is not None
            and reservation_user_id is not None
            and reservation_ras_id is not None
            and reservation_request_key is not None
        ):
            ras_registry = getattr(self.identities, "ras", None)
            ras_record = ras_registry.get_by_ip(peer[0]) if ras_registry is not None else None
            if ras_record is not None:
                service = provider_service_for_accounting(ras_record.ras_type, packet.attributes)
                self.login_reservations.reserve(
                    reservation_user_id,
                    reservation_ras_id,
                    reservation_request_key,
                    str(packet.attributes.get("User-Name", "")),
                    ras_allows_multi_login(
                        ras_record.ras_type, ras_record.all_attributes(), service
                    ),
                )
        # CiscoRas._postAuth records the H.323 ID only after a successful
        # VOIP_AUTHORIZE (Called-Station-Id present); this is process-local
        # source state and deliberately is not persisted across a RAS restart.
        if response.code is RadiusCode.ACCESS_ACCEPT and "Called-Station-Id" in packet.attributes:
            ras_registry = getattr(self.identities, "ras", None)
            ras_record = ras_registry.get_by_ip(peer[0]) if ras_registry is not None else None
            if ras_record is not None:
                service = provider_service_for_accounting(ras_record.ras_type, packet.attributes)
                if normalize_ras_type(ras_record.ras_type) == "cisco" and service == "voip":
                    conf_id = provider_session_id("Cisco", packet.attributes, "voip")
                    if conf_id:
                        self.cisco_voip_auth_h323_ids.setdefault(ras_record.ras_id, set()).add(conf_id)
        if (
            response.code is RadiusCode.ACCESS_REJECT
            and self.login_reservations is not None
            and reservation_request_key is not None
        ):
            # A rejected retry/policy re-evaluation must not leave a phantom
            # login consuming the user's MultiLogin capacity. Release only the
            # reservation for this exact RADIUS request, never all user rows.
            self.login_reservations.release(reservation_request_key)
        if self.ip_pool_sessions and response.code is RadiusCode.ACCESS_REJECT:
            # A later policy may reject after an IP allocation policy ran.
            # Release only an explicitly pending allocation; never release an
            # already adopted active-session lease through this path.
            ras_record = self.identities.ras.get_by_ip(peer[0])
            ip = response.attributes.get("Framed-IP-Address")
            if ras_record is not None and ip:
                self.ip_pool_sessions.pools.release_pending(ras_record.ras_id, str(ip))
        return response


class NativeRadiusRuntimeState:
    """Long-lived in-memory state shared by packet-scoped database runtimes."""

    def __init__(self, type_defaults=None) -> None:
        self.sessions = SessionRegistry()
        self.ras: RASRuntimeRegistry | None = None
        self.pools: IPPoolRuntimeRegistry | None = None
        self.type_defaults = type_defaults
        self.sessions_recovered = False
        self.cisco_voip_auth_h323_ids: dict[int, set[str]] = {}
        self.cisco_online_status: dict[int, dict[str, dict[str, object]]] = {}

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
        expiry_scheduler = VoipLimitScheduler(on_error=self._expiry_scheduler_error, name="atd-online-expiry")
        self.online_expiry_loop = OnlineSessionExpiryLoop(
            expiry_scheduler, self._check_online_expiry, self._terminate_voip_session,
            on_error=self._expiry_error,
        )
        self.online_expiry_loop.start()

    def _scheduler_error(self, key, exc: Exception) -> None:
        self._logger.error("VoIP timer callback failed for %r: %s", key, exc)

    def _limit_error(self, user_id: int, exc: Exception) -> None:
        self._logger.error("VoIP limit enforcement failed for user %s: %s", user_id, exc)

    def _expiry_scheduler_error(self, key, exc: Exception) -> None:
        self._logger.error("Online-expiry timer callback failed for %r: %s", key, exc)

    def _expiry_error(self, user_id: int, exc: Exception) -> None:
        self._logger.error("A1.24 expiry enforcement failed for user %s: %s", user_id, exc)

    def close(self) -> None:
        """Stop timer workers during normal process shutdown."""
        self.voip_limit_loop.close()
        self.online_expiry_loop.close()

    def _refresh_online_expiry_schedule(self, user_id: int) -> None:
        with self.state.sessions.synchronized():
            active = self.state.sessions.active_for_user(user_id)
        if active:
            self.online_expiry_loop.schedule(user_id, 1)
        else:
            self.online_expiry_loop.cancel(user_id)

    def _check_online_expiry(self, user_id: int):
        with self.connection_factory() as conn:
            self._refresh_durable_user_sessions(conn, user_id)
            users = UserRepository(conn)
            attrs = dict(users.policy_attributes(user_id))
            with self.state.sessions.synchronized():
                active = tuple(self.state.sessions.active_for_user(user_id))
            plan = plan_online_expiry(
                attrs, tuple(state.key for state in active),
                datetime.now(timezone.utc).timestamp(),
            )
            if plan.kill_reasons:
                self._logger.warning(
                    "A1.24 expiry reached for user %s; requesting termination of %s live sessions",
                    user_id, len(plan.kill_reasons),
                )
            return plan

    def _refresh_voip_limit_schedule(self, user_id: int) -> None:
        ras_registry = self.state.ras
        if ras_registry is None:
            self.voip_limit_loop.cancel(user_id)
            return
        with self.state.sessions.synchronized():
            active = self.state.sessions.active_for_user(user_id)
            has_voip_charge = any(
                state.charge_id is not None
                and state.charge_kind in {"voip", "internet"}
                and ras_registry.get(state.key.ras_id) is not None
                for state in active
            )
        if has_voip_charge:
            # Re-evaluate after accounting mutations rather than retaining a
            # deadline calculated from a stale credit/rule snapshot.
            self.voip_limit_loop.schedule(user_id, 1)
        else:
            self.voip_limit_loop.cancel(user_id)

    def _refresh_durable_user_sessions(self, conn, user_id: int) -> None:
        """Refresh the full user's session set while holding deterministic DB locks."""
        if not callable(getattr(conn, "execute", None)):
            return
        from atd_radius.infrastructure.live_radius_sessions import PostgresLiveRadiusSessionRepository
        from atd_radius.infrastructure.login_reservations import PostgresLoginReservationRepository

        # Share the login/Accounting handoff lock so a new session cannot
        # appear between durable enumeration and deadline calculation.
        PostgresLoginReservationRepository(conn).lock_user(user_id)
        store = PostgresLiveRadiusSessionRepository(conn)
        durable = [state for state in store.list_active() if state.key.user_id == user_id]
        with self.state.sessions.synchronized():
            local = self.state.sessions.all_for_user(user_id)
        keys = {state.key for state in durable}
        keys.update(state.key for state in local)
        for key in sorted(keys, key=lambda item: (item.user_id, item.ras_id, item.unique_id)):
            store.lock(key)
            state = store.get(key)
            with self.state.sessions.synchronized():
                if state is None or not state.started or state.stopped:
                    self.state.sessions.remove(key)
                else:
                    self.state.sessions.replace(state)

    def _check_voip_limits(self, user_id: int) -> VoipLimitPlan:
        with self.connection_factory() as conn:
            # The timer may run in a worker that did not receive the latest
            # Accounting packet. Plan against durable cross-worker state, not
            # only the worker-local cache.
            self._refresh_durable_user_sessions(conn, user_id)
            ras_registry = build_ras_runtime(RASRepository(conn), self.state.type_defaults)
            users = UserRepository(conn)
            credits = UserCreditRepository(conn)
            available_credit = credits.get(user_id)
            if available_credit is None:
                return VoipLimitPlan(None)
            with self.state.sessions.synchronized():
                active = tuple(
                    state
                    for state in self.state.sessions.active_for_user(user_id)
                    if state.charge_id is not None
                    and state.charge_kind in {"internet", "voip"}
                    and ras_registry.get(state.key.ras_id) is not None
                )
                if not active:
                    return VoipLimitPlan(None)
                # Accounting's UserChargeSettlement assigned this native
                # charge kind using the A1.24 normal-user/VoIP-user boundary.
                # Keep the planner consistent with the actual active state.
                charge_kinds = {state.charge_kind for state in active}
                if len(charge_kinds) != 1:
                    raise ValueError("user has mixed Internet and VoIP charge sessions")
                charge_kind = next(iter(charge_kinds))
                when = datetime.now().astimezone()
                context = lambda state: (
                    state.key.ras_id,
                    state.attributes.get("NAS-Port") or state.attributes.get("NAS-Port-Id"),
                )
                if charge_kind == "internet":
                    settlement = InternetChargeSettlement(
                        PostgresInternetChargeRuleRepository(conn), users, credits
                    )
                else:
                    settlement = VoipChargeSettlement(
                        PostgresVoipChargeRuleRepository(conn), users,
                        PostgresVoipTariffRepository(conn), credits,
                    )
                return settlement.plan_limits(active, when, available_credit, context)

    def _terminate_voip_session(self, session_key: SessionKey, reason: str) -> None:
        with self.state.sessions.synchronized():
            local = self.state.sessions.get(session_key)
            if local is None or local.stopped:
                return
            local_pending = bool(getattr(local, "termination_requested_reason", None))
            snapshot = replace(local, attributes=dict(local.attributes))
        try:
            with self.connection_factory() as conn:
                if callable(getattr(conn, "execute", None)):
                    # The transaction-scoped session lock serializes the durable
                    # claim across workers until the provider request returns.
                    from atd_radius.infrastructure.live_radius_sessions import PostgresLiveRadiusSessionRepository

                    durable_sessions = PostgresLiveRadiusSessionRepository(conn)
                    durable_sessions.lock(session_key)
                    durable = durable_sessions.get(session_key)
                    if durable is None or durable.stopped:
                        with self.state.sessions.synchronized():
                            self.state.sessions.remove(session_key)
                        return
                    if durable.termination_requested_reason:
                        with self.state.sessions.synchronized():
                            self.state.sessions.replace(durable)
                        return
                    durable.termination_requested_reason = reason
                    durable.termination_requested_at = datetime.now(timezone.utc)
                    durable_sessions.save(durable)
                    snapshot = replace(durable, attributes=dict(durable.attributes))
                    with self.state.sessions.synchronized():
                        self.state.sessions.replace(snapshot)
                else:
                    # Non-PostgreSQL test adapters retain process-local idempotency.
                    with self.state.sessions.synchronized():
                        current = self.state.sessions.get(session_key)
                        if (
                            current is None or current.stopped
                            or current.termination_requested_reason or local_pending
                        ):
                            return
                        current.termination_requested_reason = reason
                        current.termination_requested_at = datetime.now(timezone.utc)
                        snapshot = replace(current, attributes=dict(current.attributes))

                ras_registry = build_ras_runtime(RASRepository(conn), self.state.type_defaults)
                ras = ras_registry.get(session_key.ras_id)
                if ras is None:
                    raise PermanentRASTerminationError("session RAS is missing or inactive")
                provider = ras.ras_type.strip().lower().replace("-", "_").replace(" ", "_")
                if provider in {"mvts", "gnugk", "gnu_gatekeeper", "gnugatekeeper"}:
                    # A1.24 MVTS and GnuGk killUser both target the user's native
                    # voip_username, which may differ from the inbound login.
                    credentials = UserRepository(conn).voip_credentials(session_key.user_id)
                    if credentials is None or not credentials[0].strip():
                        raise PermanentRASTerminationError(
                            f"{ras.ras_type} session user has no configured voip_username"
                        )
                    if provider == "mvts":
                        snapshot = replace(
                            snapshot,
                            attributes={**snapshot.attributes, "User-Name": credentials[0]},
                        )
                    else:
                        snapshot = replace(
                            snapshot,
                            attributes={**snapshot.attributes, "voip_username": credentials[0]},
                        )
                if provider in {"mikrotik", "cisco_vpdn"}:
                    credentials = UserRepository(conn).normal_credentials(session_key.user_id)
                    if credentials is None or not credentials[0].strip():
                        raise PermanentRASTerminationError(
                            f"{ras.ras_type} session user has no configured normal_username"
                        )
                    snapshot = replace(
                        snapshot,
                        attributes={**snapshot.attributes, "normal_username": credentials[0]},
                    )
                self._ras_terminator.terminate(ras, snapshot, reason)
        except Exception:
            with self.state.sessions.synchronized():
                current = self.state.sessions.get(session_key)
                if (
                    current is not None and not current.stopped
                    and current.termination_requested_reason == reason
                ):
                    current.termination_requested_reason = None
                    current.termination_requested_at = None
            raise

    def _recover_open_sessions(self, conn, charge, ras_registry, pools, session_store=None) -> set[int]:
        """Rehydrate open rows and return users needing restored VoIP timers.

        This deliberately uses the existing A1.24 connection_log/details tables.
        Charging baselines are restarted at recovery time because the legacy
        schema does not persist the in-memory rule-transition accumulator; prior
        counters and the original login timestamp are retained for accounting
        and MultiLogin views.
        """
        if self.state.sessions_recovered:
            return set()
        repository = ConnectionLogRepository(conn)
        recovered = 0
        recovered_voip_users: set[int] = set()
        durable_log_ids: set[int] = set()
        now = datetime.now().astimezone()
        # Restore full snapshots first, including sessions intentionally omitted
        # from connection_log by A1.24 no_connection_log RAS messages.
        if session_store is not None:
            for state in session_store.list_active():
                log_id = state.attributes.get("__connection_log_id")
                if log_id:
                    try:
                        durable_log_ids.add(int(log_id))
                    except ValueError:
                        self._logger.warning("Skipping malformed durable connection-log identity %r", log_id)
                ras = ras_registry.get(state.key.ras_id)
                if ras is None:
                    self._logger.warning(
                        "Skipping durable session %s because RAS %s is unavailable",
                        state.key.unique_id, state.key.ras_id,
                    )
                    continue
                if not self.state.sessions.restore(state):
                    continue
                ip = state.attributes.get("Framed-IP-Address")
                if ip:
                    pool_id = pools.find_pool(ras.ippool_ids, ip)
                    if pool_id is not None:
                        pools.ensure_claimed(pool_id, ip)
                if state.charge_kind in {"voip", "internet"} and state.charge_id is not None:
                    recovered_voip_users.add(state.key.user_id)
                recovered += 1
        for record in repository.list_open():
            if record.connection_log_id in durable_log_ids:
                continue
            if record.user_id is None or record.ras_id is None:
                self._logger.warning(
                    "Skipping open connection_log %s without user/RAS identity",
                    record.connection_log_id,
                )
                continue
            ras = ras_registry.get(record.ras_id)
            if ras is None:
                self._logger.warning(
                    "Skipping open connection_log %s because RAS %s is unavailable",
                    record.connection_log_id, record.ras_id,
                )
                continue
            details = dict(record.details)
            # A1.24 does not use Acct-Session-Id as the online-instance
            # identity for every RAS. Restore using the same provider-specific
            # key used by live Accounting (port, h323_conf_id, call_id, etc.).
            # Only providers with no source-defined key fall back to the
            # standard Acct-Session-Id.
            service = provider_service_for_accounting(ras.ras_type, details)
            session_id = provider_session_id(ras.ras_type, details, service)
            if not session_id:
                self._logger.warning(
                    "Skipping open connection_log %s without a source-resolvable session identity",
                    record.connection_log_id,
                )
                continue
            try:
                input_octets = max(0, int(details.get("Acct-Input-Octets", "0") or "0"))
                output_octets = max(0, int(details.get("Acct-Output-Octets", "0") or "0"))
            except (TypeError, ValueError):
                self._logger.warning(
                    "Skipping open connection_log %s with invalid octet counters",
                    record.connection_log_id,
                )
                continue
            key = SessionKey(record.user_id, record.ras_id, session_id)
            attrs = {str(name): str(value) for name, value in details.items()}
            attrs["__connection_log_id"] = str(record.connection_log_id)
            state = SessionState(
                key=key,
                attributes=attrs,
                started=True,
                stopped=False,
                input_octets=input_octets,
                output_octets=output_octets,
                started_at=record.login_time,
                ras_multi_login_allowed=ras_allows_multi_login(
                    ras.ras_type, ras.all_attributes(), service,
                ),
            )
            if not self.state.sessions.restore(state):
                continue
            port = attrs.get("NAS-Port") or attrs.get("NAS-Port-Id")
            # Rebuild the current charge/rule baseline from native policy tables.
            # Historical accrued rule transitions cannot be reconstructed from
            # connection_log alone, so we never fabricate an old accumulator.
            charge.start(state, now, record.ras_id, port)
            if session_store is not None:
                session_store.save(state)
            if state.charge_kind in {"voip", "internet"} and state.charge_id is not None:
                recovered_voip_users.add(record.user_id)
            ip = attrs.get("Framed-IP-Address")
            if ip:
                pool_id = pools.find_pool(ras.ippool_ids, ip)
                if pool_id is not None:
                    pools.ensure_claimed(pool_id, ip)
            recovered += 1
        self.state.sessions_recovered = True
        self._logger.info("Recovered %s open native RADIUS sessions", recovered)
        return recovered_voip_users

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
            from atd_radius.infrastructure.live_radius_sessions import PostgresLiveRadiusSessionRepository
            from atd_radius.infrastructure.login_reservations import PostgresLoginReservationRepository
            session_store = PostgresLiveRadiusSessionRepository(conn)
            login_reservations = PostgresLoginReservationRepository(conn)
            recovered_voip_users = self._recover_open_sessions(conn, charge, ras, pools, session_store)
            for recovered_user_id in recovered_voip_users:
                self._refresh_voip_limit_schedule(recovered_user_id)
            for recovered_state in session_store.list_active():
                self._refresh_online_expiry_schedule(recovered_state.key.user_id)
            accounting = AccountingSessionService(self.state.sessions, persistence, charge, session_store)
            dispatcher = build_radius_dispatcher(
                users,
                active_sessions_provider=session_views(
                    self.state.sessions,
                    login_reservations,
                    login_reservations.request_key(packet, peer)
                    if packet.code is RadiusCode.ACCESS_REQUEST else None,
                ),
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
                cisco_voip_auth_h323_ids=self.state.cisco_voip_auth_h323_ids,
                cisco_online_status=self.state.cisco_online_status,
                login_reservations=login_reservations,
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
                    self._refresh_online_expiry_schedule(user_id)
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
    policies.append(PluginSpec(4, "absolute_expiry", AbsoluteExpiryPolicy()))
    policies.append(PluginSpec(5, "relative_expiry", RelativeExpiryPolicy()))
    if ip_pools is not None:
        policies.append(PluginSpec(6, "ip_pool", IPPoolAllocationPolicy(ip_pools)))
    policies.append(PluginSpec(7, "timeout", TimeoutPolicy()))
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


def session_views(registry, reservation_source=None, exclude_request_key=None) -> callable:
    """Return active sessions plus accepted login reservations for MultiLogin."""
    def provider(user_id: int) -> tuple[ActiveSessionView, ...]:
        views = [
            ActiveSessionView(
                state.key.unique_id,
                state.started_at,
                ras_multi_login_allowed=state.ras_multi_login_allowed,
            )
            for state in registry.active_for_user(user_id)
        ]
        if reservation_source is not None:
            for reservation in reservation_source.list_active(user_id, exclude_request_key):
                views.append(
                    ActiveSessionView(
                        f"login:{reservation.request_key}",
                        reservation.created_at,
                        ras_multi_login_allowed=reservation.ras_multi_login_allowed,
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
