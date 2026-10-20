from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from atd_radius.application.radius_runtime import NativeRadiusPacketHandler, NativeRadiusRuntimeState
from atd_radius.domain.radius_runtime import SessionKey, SessionState
from atd_radius.domain.ras import RAS


class Store:
    def __init__(self, states):
        self.states = states
        self.saved = []
    def list_active(self):
        return list(self.states)
    def save(self, state):
        self.saved.append(state)


def test_recovery_restores_durable_charge_state_before_legacy_open_log_fallback():
    state = NativeRadiusRuntimeState()
    started = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    snapshot = SessionState(
        key=SessionKey(7, 3, "without-history"),
        attributes={"User-Name": "alice", "no_connection_log": "1"},
        started=True, input_octets=100, output_octets=200, started_at=started,
        charge_id=12, charge_kind="internet", charge_rule_id=44,
        charge_rule_started_at=started, charge_rule_input_octets=90,
        charge_rule_output_octets=190, charge_accrued=Decimal("3.25"),
    )
    store = Store([snapshot])
    handler = NativeRadiusPacketHandler.__new__(NativeRadiusPacketHandler)
    handler.state = state
    handler._logger = Mock()
    conn = Mock()
    ras = RAS(3, "192.0.2.3", "router", "MikroTik", "secret")
    ras_registry = Mock()
    ras_registry.get.return_value = ras
    pools = Mock()
    charge = Mock()

    recovered_users = handler._recover_open_sessions(conn, charge, ras_registry, pools, store)

    restored = state.sessions.get(SessionKey(7, 3, "without-history"))
    assert restored is snapshot
    assert restored.charge_rule_id == 44
    assert restored.charge_rule_started_at == started
    assert restored.charge_accrued == Decimal("3.25")
    assert recovered_users == {7}
    charge.start.assert_not_called()
    assert state.sessions_recovered is True
